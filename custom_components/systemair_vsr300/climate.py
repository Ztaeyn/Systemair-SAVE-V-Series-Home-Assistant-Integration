import logging
import asyncio
from homeassistant.components.climate import (
    ClimateEntity, 
    ClimateEntityFeature, 
    HVACMode
)
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# Dictionary for Writing to Register 1161
# Keys must match the new naming convention for consistency
VENTILATION_MODES = {
    "Manual Low": (1, 2),    
    "Manual Normal": (1, 3),
    "Manual High": (1, 4),
    "Auto": (0, None),      
    "Crowded": (2, None),
    "Refresh": (3, None),
    "Fireplace": (4, None),
    "Away": (5, None),
    "Holiday": (6, None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    from homeassistant.components.modbus import get_hub
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
        
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | 
            ClimateEntityFeature.PRESET_MODE
        )
        self._attr_preset_modes = list(VENTILATION_MODES.keys())
        self._attr_preset_mode = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_min_temp = 12.0
        self._attr_max_temp = 30.0

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_set_temperature(self, **kwargs):
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            modbus_temp = int(temp * 10)
            await self._hub.async_pb_call(self._slave, 2000, modbus_temp, CALL_TYPE_WRITE_REGISTER)
            self._attr_target_temperature = temp
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set target temperature: %s", e)

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode not in VENTILATION_MODES:
            return
        mode_val, speed_val = VENTILATION_MODES[preset_mode]
        try:
            await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
            if speed_val is not None:
                await asyncio.sleep(0.5) 
                await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set preset mode %s: %s", preset_mode, e)

    async def async_update(self):
        try:
            # 1. Supply Air Temp (Holding 12102)
            res_temp = await self._hub.async_pb_call(self._slave, 12102, 1, CALL_TYPE_REGISTER_HOLDING)
            if res_temp and hasattr(res_temp, 'registers'):
                val = res_temp.registers[0]
                if val > 32767: val -= 65536
                self._attr_current_temperature = round(val * 0.1, 1)

            # 2. Target Setpoint (Holding 2000)
            res_target = await self._hub.async_pb_call(self._slave, 2000, 1, CALL_TYPE_REGISTER_HOLDING)
            if res_target and hasattr(res_target, 'registers'):
                self._attr_target_temperature = round(res_target.registers[0] * 0.1, 1)

            # 3. Mode (Input 1160) and Speed (Holding 1130)
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)
            
            if res_mode and hasattr(res_mode, 'registers'):
                mode_val = res_mode.registers[0]
                cmd_val = res_speed.registers[0] if (res_speed and hasattr(res_speed, 'registers')) else None

                if mode_val == 0:
                    self._attr_preset_mode = "Auto"
                elif mode_val == 1:
                    speed_map = {2: "Manual Low", 3: "Manual Normal", 4: "Manual High"}
                    self._attr_preset_mode = speed_map.get(cmd_val, "Manual Normal")
                else:
                    status_map = {2: "Crowded", 3: "Refresh", 4: "Fireplace", 5: "Away", 6: "Holiday"}
                    self._attr_preset_mode = status_map.get(mode_val)
                        
        except Exception as e:
            _LOGGER.error("Climate update failed: %s", e)