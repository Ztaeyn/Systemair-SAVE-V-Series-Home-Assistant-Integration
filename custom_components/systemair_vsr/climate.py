import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
    CONF_MODEL,
    CONF_NAME
)
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# Preset mapping for Systemair SAVE Modes
# (Mode Register Value, Fan Speed Register Value)
PRESET_MAP = {
    PRESET_HOME: (1, 3),   # Manual Mode, Normal Speed
    PRESET_AWAY: (5, None), # Away Mode
    PRESET_BOOST: (1, 4),  # Manual Mode, High Speed
    "Fireplace": (4, None),
    "Crowded": (2, None),
    "Refresh": (3, None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR climate platform."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found for climate", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    async_add_entities([SaveVSRClimate(hub, model, slave)], True)

class SaveVSRClimate(ClimateEntity):
    """Generic SaveVSR Climate Control."""

    _attr_has_entity_name = True
    _attr_name = None  # Becomes the Device Name
    _attr_hvac_mode = HVACMode.FAN_ONLY
    _attr_hvac_modes = [HVACMode.FAN_ONLY, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | 
        ClimateEntityFeature.PRESET_MODE
    )
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 12.0
    _attr_max_temp = 30.0
    _attr_preset_modes = list(PRESET_MAP.keys())

    def __init__(self, hub, model, slave):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._attr_unique_id = f"{DOMAIN}_{slave}_climate"
        
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_preset_mode = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_set_hvac_mode(self, hvac_mode):
        """Standard SAVE units usually stay in Fan Only. Off stops the unit."""
        reg_val = 1 if hvac_mode == HVACMode.OFF else 0 # 1 is Stop on many models
        await self._hub.async_pb_call(self._slave, 1130, reg_val, CALL_TYPE_WRITE_REGISTER)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Set unit to a specific ventilation mode."""
        if preset_mode not in PRESET_MAP:
            return
            
        mode_val, speed_val = PRESET_MAP[preset_mode]
        # Write Mode Command (1161)
        await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
        
        if speed_val is not None:
            # Write Fan Speed if manual mode selected
            await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            # SAVE units usually use 0.1 scaling (22.0 -> 220)
            await self._hub.async_pb_call(self._slave, 1211, int(temp * 10), CALL_TYPE_WRITE_REGISTER)
            self._attr_target_temperature = temp
            self.async_write_ha_state()

    async def async_update(self):
        """Update climate state from Modbus."""
        try:
            # Current Temp (Supply Air) - Input Register 12102
            res_curr = await self._hub.async_pb_call(self._slave, 12102, 1, CALL_TYPE_REGISTER_INPUT)
            # Target Temp - Holding Register 1211
            res_target = await self._hub.async_pb_call(self._slave, 1211, 1, CALL_TYPE_REGISTER_HOLDING)
            # Current Mode - Input Register 1160
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)

            if res_curr and hasattr(res_curr, 'registers'):
                val = res_curr.registers[0]
                if val > 32767: val -= 65536
                self._attr_current_temperature = val / 10.0

            if res_target and hasattr(res_target, 'registers'):
                self._attr_target_temperature = res_target.registers[0] / 10.0

            if res_mode and hasattr(res_mode, 'registers'):
                mode_val = res_mode.registers[0]
                # Map Modbus mode back to Preset
                inv_map = {v[0]: k for k, v in PRESET_MAP.items()}
                self._attr_preset_mode = inv_map.get(mode_val, "Unknown")

        except Exception as e:
            _LOGGER.error("SaveVSR Climate Update failed: %s", e)