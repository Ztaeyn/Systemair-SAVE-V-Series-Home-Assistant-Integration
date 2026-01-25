import logging
import asyncio
from homeassistant.components.climate import (
    ClimateEntity, 
    ClimateEntityFeature, 
    HVACMode
)
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# Dictionary for Writing to Register 1161
VENTILATION_MODES = {
    "Away": (6, None),
    "Low": (2, 2),    
    "Normal": (2, 3),
    "High": (2, 4),
    "Auto": (1, None),      
    "Crowded": (3, None),
    "Refresh": (4, None),
    "Fireplace": (5, None),
    "Holiday": (7, None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    hub = get_hub(hass, "VSR300")
    if hub is None:
        _LOGGER.error("Hub VSR300 not found during climate setup")
        return
    async_add_entities([VSR300Climate(hub, entry.data)], True)

class VSR300Climate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = "Ventilation"

    def __init__(self, hub, config):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._attr_unique_id = f"vsr300_{self._slave}_climate"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.FAN_ONLY, HVACMode.OFF]
        self._attr_hvac_mode = HVACMode.FAN_ONLY
        
        # Features: Added TARGET_TEMPERATURE
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | 
            ClimateEntityFeature.PRESET_MODE
        )
        self._attr_preset_modes = list(VENTILATION_MODES.keys())
        self._attr_preset_mode = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        # Standard limits for VSR300 heating setpoint
        self._attr_min_temp = 12.0
        self._attr_max_temp = 30.0

    @property
    def device_info(self):
        """Link this entity to the VSR300 Device."""
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature (Register 12108)."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        try:
            # Convert float (e.g. 21.5) to Modbus int (215)
            modbus_temp = int(temp * 10)
            _LOGGER.debug("VSR300: Setting target temperature to %s", modbus_temp)
            
            await self._hub.async_pb_call(
                self._slave, 2000, modbus_temp, CALL_TYPE_WRITE_REGISTER
            )
            self._attr_target_temperature = temp
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set target temperature: %s", e)

    async def async_set_preset_mode(self, preset_mode):
        """Set new ventilation preset mode (Register 1161)."""
        if preset_mode not in VENTILATION_MODES:
            return
        mode_val, speed_val = VENTILATION_MODES[preset_mode]
        try:
            await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
            if speed_val is not None:
                await asyncio.sleep(1.5) 
                await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set preset mode %s: %s", preset_mode, e)

    async def async_update(self):
        """Update climate entity state: Reading Status from 1160 and Temps."""
        try:
            # 1. Update Current Temperature (Supply Air)
            res_temp = await self._hub.async_pb_call(self._slave, 12102, 1, CALL_TYPE_REGISTER_HOLDING)
            if res_temp and hasattr(res_temp, 'registers'):
                val = res_temp.registers[0]
                if val > 32767: val -= 65536
                self._attr_current_temperature = round(val * 0.1, 1)

            # 2. Update Target Temperature (Setpoint)
            res_target = await self._hub.async_pb_call(self._slave, 2000, 1, CALL_TYPE_REGISTER_HOLDING)
            if res_target and hasattr(res_target, 'registers'):
                self._attr_target_temperature = round(res_target.registers[0] * 0.1, 1)

            # 3. Read status from 1160 (Status) and 1130 (Speed)
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_HOLDING)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)
            
            if res_mode and hasattr(res_mode, 'registers'):
                current_mode_status = res_mode.registers[0]
                current_speed_val = res_speed.registers[0] if (res_speed and hasattr(res_speed, 'registers')) else 0
                
                if current_mode_status == 1: # Manual status on 1160
                    speed_map = {2: "Low", 3: "Normal", 4: "High"}
                    self._attr_preset_mode = speed_map.get(current_speed_val, "Manual")
                else:
                    status_map = {0: "Auto", 2: "Crowded", 3: "Refresh", 4: "Fireplace", 5: "Away", 6: "Holiday"}
                    self._attr_preset_mode = status_map.get(current_mode_status, f"Mode {current_mode_status}")
                        
        except Exception as e:
            _LOGGER.error("Climate update failed: %s", e)