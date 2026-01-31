import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_ECO,
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

# Preset mapping - Keeping standard constants for built-in HA support
PRESET_MAP = {
    "Auto": (0, None),
    "Manual Low": (1, 2),
    PRESET_HOME: (1, 3),       
    PRESET_BOOST: (1, 4),      
    "Crowded": (2, None),
    "Refresh": (3, None),
    "Fireplace": (4, None),
    PRESET_AWAY: (5, None),    
    PRESET_ECO: (6, None),     
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR climate platform."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)
    async_add_entities([SaveVSRClimate(hub, model, slave)], True)

class SaveVSRClimate(ClimateEntity):
    """Generic SaveVSR Climate Control."""

    _attr_has_entity_name = True
    _attr_hvac_mode = HVACMode.FAN_ONLY
    _attr_hvac_modes = [HVACMode.FAN_ONLY, HVACMode.HEAT, HVACMode.OFF]
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
        self._attr_hvac_action = HVACAction.IDLE
        self._triac_signal = 0

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    @property
    def extra_state_attributes(self):
        """Attributes for secondary info like Wattage."""
        return {
            "heater_power_w": round(self._triac_signal * 16.7, 1),
            "triac_level_percent": self._triac_signal
        }

    async def async_set_hvac_mode(self, hvac_mode):
        reg_val = 1 if hvac_mode == HVACMode.OFF else 3 
        await self._hub.async_pb_call(self._slave, 1130, reg_val, CALL_TYPE_WRITE_REGISTER)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode not in PRESET_MAP: return
        mode_val, speed_val = PRESET_MAP[preset_mode]
        await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
        if speed_val is not None:
            await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Write Target Temp to Register 2000."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._hub.async_pb_call(self._slave, 2000, int(temp * 10), CALL_TYPE_WRITE_REGISTER)
            self._attr_target_temperature = temp
            self.async_write_ha_state()

    @property
    def icon(self):
        """Return custom icons for non-standard modes."""
        icon_map = {
            "Fireplace": "mdi:fire",
            "Crowded": "mdi:account-group",
            "Refresh": "mdi:air-filter",
            "Auto": "mdi:robot",
            "Manual Low": "mdi:fan-speed-1",
        }
        # HA handles constants (Home/Away/Boost/Eco) automatically if we return None
        # but we provide the map for your specific custom strings.
        return icon_map.get(self._attr_preset_mode)

    async def async_update(self):
        """Update climate state from Modbus."""
        try:
            # 1. READ REGS
            res_curr = await self._hub.async_pb_call(self._slave, 12102, 1, CALL_TYPE_REGISTER_INPUT)
            res_target = await self._hub.async_pb_call(self._slave, 2000, 1, CALL_TYPE_REGISTER_HOLDING)
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            res_triac = await self._hub.async_pb_call(self._slave, 12108, 1, CALL_TYPE_REGISTER_INPUT)
            res_exch = await self._hub.async_pb_call(self._slave, 12101, 1, CALL_TYPE_REGISTER_INPUT)

            # 2. PROCESS SUPPLY AIR (Current Temp)
            if res_curr and hasattr(res_curr, 'registers'):
                val = res_curr.registers[0]
                if val > 32767: val -= 65536
                # Only update if reading is non-zero to prevent UI glitches
                if val != 0:
                    self._attr_current_temperature = val / 10.0

            # 3. PROCESS USER SETPOINT (Target Temp 2000)
            if res_target and hasattr(res_target, 'registers'):
                target_val = res_target.registers[0]
                if target_val != 0:
                    self._attr_target_temperature = target_val / 10.0

            # 4. PROCESS PRESET
            if res_mode and hasattr(res_mode, 'registers'):
                mode_val = res_mode.registers[0]
                for label, values in PRESET_MAP.items():
                    if values[0] == mode_val:
                        self._attr_preset_mode = label
                        break
            # 5. PROCESS ACTION & MODE (Red Arc vs Blue Arc)
            is_heating = False
            if res_triac and hasattr(res_triac, 'registers'):
                self._triac_signal = float(res_triac.registers[0])
                if self._triac_signal > 0: 
                    is_heating = True
            
            # Fallback check for Heat Exchanger efficiency
            if not is_heating and res_exch and hasattr(res_exch, 'registers'):
                if res_exch.registers[0] > 10: 
                    is_heating = True

            if is_heating:
                self._attr_hvac_action = HVACAction.HEATING
                self._attr_hvac_mode = HVACMode.HEAT
            else:
                self._attr_hvac_action = HVACAction.FAN_ONLY
                self._attr_hvac_mode = HVACMode.FAN_ONLY

            # Trigger the UI update
            self.async_write_ha_state()
            
            # Fallback to heat exchanger efficiency for active heating state
            if not is_heating and res_exch and hasattr(res_exch, 'registers'):
                if res_exch.registers[0] > 10: 
                    is_heating = True

            self._attr_hvac_action = HVACAction.HEATING if is_heating else HVACAction.FAN_ONLY

        except Exception as e:
            _LOGGER.error("SaveVSR Climate Update failed: %s", e)