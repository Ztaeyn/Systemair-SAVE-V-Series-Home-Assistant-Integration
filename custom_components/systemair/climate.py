import asyncio
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
    CONF_MODEL
)
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# --- MATCHING YOUR SELECT.PY MAPPINGS ---
PRESET_MAP = {
    "Manual Low": (1, 2),
    "Manual Normal": (1, 3), # This is PRESET_HOME
    "Manual High": (1, 4),   # This is PRESET_BOOST
    "Auto": (0, None),      
    "Crowded": (2, None),
    "Refresh": (3, None),
    "Fireplace": (4, None),
    "Away": (5, None),       # This is PRESET_AWAY
    "Holiday": (6, None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR climate platform."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    if hub is None: return
    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)
    async_add_entities([SaveVSRClimate(hub, model, slave)], True)

class SaveVSRClimate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.FAN_ONLY, HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
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
        self._attr_hvac_mode = HVACMode.FAN_ONLY
        self._attr_hvac_action = HVACAction.IDLE

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"{self._model}_{self._slave}")}, "name": f"Systemair {self._model}", "manufacturer": "Systemair", "model": f"SAVE {self._model}"}

    async def async_set_hvac_mode(self, hvac_mode):
        reg_val = 1 if hvac_mode == HVACMode.OFF else 3 
        await self._hub.async_pb_call(self._slave, 1130, reg_val, CALL_TYPE_WRITE_REGISTER)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Set the mode exactly like select.py does."""
        if preset_mode not in PRESET_MAP: return
        mode_val, speed_val = PRESET_MAP[preset_mode]
        await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
        if speed_val is not None:
            await asyncio.sleep(1.0)
            await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._hub.async_pb_call(self._slave, 2000, int(temp * 10), CALL_TYPE_WRITE_REGISTER)
            self._attr_target_temperature = temp
            self.async_write_ha_state()

    async def async_update(self):
        try:
            # 1. READ REGS
            res_curr = await self._hub.async_pb_call(self._slave, 12102, 1, CALL_TYPE_REGISTER_INPUT)
            res_target = await self._hub.async_pb_call(self._slave, 2000, 1, CALL_TYPE_REGISTER_HOLDING)
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)
            res_triac = await self._hub.async_pb_call(self._slave, 2148, 1, CALL_TYPE_REGISTER_HOLDING)

            # 2. TEMPERATURES
            if res_curr and hasattr(res_curr, 'registers'):
                val = res_curr.registers[0]
                if val > 32767: val -= 65536
                if val != 0: self._attr_current_temperature = val / 10.0
            if res_target and hasattr(res_target, 'registers'):
                if res_target.registers[0] != 0:
                    self._attr_target_temperature = res_target.registers[0] / 10.0

            # 3. PRESET SYNC (Matching your select.py logic)
            if res_mode and hasattr(res_mode, 'registers'):
                m_val = res_mode.registers[0]
                s_val = res_speed.registers[0] if res_speed and hasattr(res_speed, 'registers') else None
                
                if m_val == 0: self._attr_preset_mode = "Auto"
                elif m_val == 1:
                    self._attr_preset_mode = {2: "Manual Low", 3: "Manual Normal", 4: "Manual High"}.get(s_val, "Manual Normal")
                else:
                    self._attr_preset_mode = {2: "Crowded", 3: "Refresh", 4: "Fireplace", 5: "Away", 6: "Holiday"}.get(m_val)

            # 4. HEATING ACTION
            is_heating = (res_triac.registers[0] > 0) if res_triac and hasattr(res_triac, 'registers') else False

            if is_heating:
                self._attr_hvac_action = HVACAction.HEATING
                self._attr_hvac_mode = HVACMode.HEAT
            else:
                self._attr_hvac_action = HVACAction.IDLE if self._attr_hvac_mode != HVACMode.OFF else HVACAction.OFF
                if self._attr_hvac_mode == HVACMode.HEAT:
                    self._attr_hvac_mode = HVACMode.FAN_ONLY

        except Exception as e:
            _LOGGER.error("SaveVSR Climate Update failed: %s", e)