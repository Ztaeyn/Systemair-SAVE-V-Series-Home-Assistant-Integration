import asyncio
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
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

# --- MAPPING FOR SKRIVING (Register 1161) ---
PRESET_MAP = {
    "auto": (1, None),          # Skriver 1 -> Leser 0
    "manual_low": (2, 2),       # Skriver 2 -> Leser 1
    "manual_normal": (2, 3),    # Skriver 2 -> Leser 1
    "manual_high": (2, 4),      # Skriver 2 -> Leser 1
    "crowded": (3, None),       # Skriver 3 -> Leser 2
    "refresh": (4, None),       # Skriver 4 -> Leser 3
    "fireplace": (5, None),     # Skriver 5 -> Leser 4
    "away": (6, None),          # Skriver 6 -> Leser 5
    "holiday": (7, None),       # Skriver 7 -> Leser 6
}

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, config.get("hub_name", "modbus_hub"))
    if hub is None: return
    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)
    async_add_entities([SystemAirClimate(hub, model, slave)], True)

class SystemAirClimate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "systemair_climate" 
    
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
        # 1 = Off, 3 = Normal (Viftehastighet register 1130)
        reg_val = 1 if hvac_mode == HVACMode.OFF else 3 
        await self._hub.async_pb_call(self._slave, 1130, reg_val, CALL_TYPE_WRITE_REGISTER)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode not in PRESET_MAP: return
        mode_val, speed_val = PRESET_MAP[preset_mode]
        
        # Skriv til User Mode (1161)
        await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
        
        # Hvis det er en manuell modus, må vi også sette viftehastighet (1130)
        if speed_val is not None:
            await asyncio.sleep(1.0) # Modbus trenger ofte litt tid mellom to skriv
            await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._hub.async_pb_call(self._slave, 2000, int(temp * 10), CALL_TYPE_WRITE_REGISTER)
            self._attr_target_temperature = temp
            self.async_write_ha_state()

    async def async_update(self):
        """Hent data fra anlegget og synkroniser status."""
        try:
            res_curr = await self._hub.async_pb_call(self._slave, 12102, 1, CALL_TYPE_REGISTER_INPUT)
            res_target = await self._hub.async_pb_call(self._slave, 2000, 1, CALL_TYPE_REGISTER_HOLDING)
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)
            res_triac = await self._hub.async_pb_call(self._slave, 2148, 1, CALL_TYPE_REGISTER_HOLDING)

            # 1. Temperaturer
            if res_curr and hasattr(res_curr, 'registers'):
                val = res_curr.registers[0]
                if val > 32767: val -= 65536
                if val != 0: self._attr_current_temperature = val / 10.0

            if res_target and hasattr(res_target, 'registers'):
                self._attr_target_temperature = res_target.registers[0] / 10.0

            # 2. Synkroniser Modus (Basert på din fungerende fan_mode sensor)
            if res_mode and hasattr(res_mode, 'registers'):
                m_val = res_mode.registers[0]
                s_val = res_speed.registers[0] if res_speed and hasattr(res_speed, 'registers') else 3
                
                if m_val == 0: 
                    self._attr_preset_mode = "auto"
                elif m_val == 1: # Manual
                    # Sjekker viftehastighet (1130) for å skille mellom low/normal/high
                    if s_val == 2: self._attr_preset_mode = "manual_low"
                    elif s_val == 4: self._attr_preset_mode = "manual_high"
                    else: self._attr_preset_mode = "manual_normal"
                elif m_val == 2: self._attr_preset_mode = "crowded"
                elif m_val == 3: self._attr_preset_mode = "refresh"
                elif m_val == 4: self._attr_preset_mode = "fireplace"
                elif m_val == 5: self._attr_preset_mode = "away"
                elif m_val == 6: self._attr_preset_mode = "holiday"
       
            # 3. Varme-action og HVAC Mode
            is_heating = (res_triac.registers[0] > 0) if res_triac and hasattr(res_triac, 'registers') else False

            if is_heating:
                self._attr_hvac_action = HVACAction.HEATING
                self._attr_hvac_mode = HVACMode.HEAT
            else:
                self._attr_hvac_action = HVACAction.IDLE if s_val > 1 else HVACAction.OFF
                self._attr_hvac_mode = HVACMode.OFF if s_val <= 1 else HVACMode.FAN_ONLY

        except Exception as e:
            _LOGGER.error("SystemAir Climate Update failed: %s", e)