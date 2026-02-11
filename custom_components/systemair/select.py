import asyncio
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# --- MAPPINGS (Basert på dine testede verdier) ---
# Register 1161: 0=Manual/Stop, 1=Auto, 3=Crowded, 4=Refresh, 5=Fireplace, 6=Away, 7=Holiday
VENTILATION_MODES = {
    "auto": (1, None),
    "manual_low": (2, 2),
    "manual_normal": (2, 3),
    "manual_high": (2, 4),
    "crowded": (3, None),
    "refresh": (4, None),
    "fireplace": (5, None),
    "away": (6, None),
    "holiday": (7, None),
}

AIRFLOW_LEVELS = {"normal": 3, "high": 4, "maximum": 5}
AWAY_LEVELS = {"off": 0, "minimum": 1, "low": 2, "normal": 3}
SCHEDULE_LEVELS = {"off": 1, "low": 2, "normal": 3, "high": 4, "demand": 5}
TEMP_CONTROL_MODES = {"supply": 0, "room": 1, "extract": 2}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Systemair select entities."""
    config = entry.data
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, config.get("hub_name", "modbus_hub"))
    
    if hub is None:
        _LOGGER.error("Systemair: Modbus hub not found for select")
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)
        
    async_add_entities([
        SystemairVentModeSelect(hub, model, slave, "ventilation_mode"),

        # Crowded & Refresh
        SystemairGeneralSelect(hub, model, slave, "crowded_supply_level", 1134, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "crowded_extract_level", 1135, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "refresh_supply_level", 1136, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "refresh_extract_level", 1137, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        
        # Fireplace & Free Cooling
        SystemairGeneralSelect(hub, model, slave, "fireplace_supply_level", 1138, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "fireplace_extract_level", 1139, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "free_cooling_supply", 4111, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "free_cooling_extract", 4112, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        
        # Away & Holiday
        SystemairGeneralSelect(hub, model, slave, "away_supply_level", 1140, AWAY_LEVELS, "mdi:fan-minus", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "away_extract_level", 1141, AWAY_LEVELS, "mdi:fan-minus", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "holiday_supply_level", 1142, AWAY_LEVELS, "mdi:fan-off", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "holiday_extract_level", 1143, AWAY_LEVELS, "mdi:fan-off", EntityCategory.CONFIG),

        # System
        SystemairGeneralSelect(hub, model, slave, "temp_control_mode", 2030, TEMP_CONTROL_MODES, "mdi:tune-vertical", EntityCategory.CONFIG),
        SystemairGeneralSelect(hub, model, slave, "sched_airflow_level", 5059, SCHEDULE_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG), 
        SystemairGeneralSelect(hub, model, slave, "unsched_airflow_level", 5060, SCHEDULE_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG) 
    ], True)

class SystemairGeneralSelect(SelectEntity):
    """Generic Select for single-register mappings using translation keys."""
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, translation_key, register, mapping, icon, category=None):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = register
        self._mapping = mapping
        self._inv_mapping = {v: k for k, v in mapping.items()}
        
        self._attr_translation_key = translation_key
        self._attr_options = list(mapping.keys())
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"{DOMAIN}_{slave}_select_{register}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_select_option(self, option: str) -> None:
        if (val := self._mapping.get(option)) is not None:
            if await self._hub.async_pb_call(self._slave, self._register, val, CALL_TYPE_WRITE_REGISTER):
                self._attr_current_option = option
                self.async_write_ha_state()

    async def async_update(self):
        try:
            res = await self._hub.async_pb_call(self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING)
            if res and hasattr(res, 'registers'):
                self._attr_current_option = self._inv_mapping.get(res.registers[0])
        except Exception as e:
            _LOGGER.error("Systemair: Select update failed for %s: %s", self._attr_translation_key, e)

class SystemairVentModeSelect(SelectEntity):
    """Combined Mode control using translation keys."""
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, translation_key):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._attr_translation_key = translation_key
        self._attr_options = list(VENTILATION_MODES.keys())
        self._attr_unique_id = f"{DOMAIN}_{slave}_vent_mode"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_select_option(self, option: str) -> None:
        mode_val, speed_val = VENTILATION_MODES[option]
        try:
            # 1. Sett User Mode (1161)
            await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
            
            # 2. Sett Viftehastighet hvis relevant (1130)
            if speed_val is not None:
                await asyncio.sleep(1.0) 
                await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Systemair: Failed to set ventilation mode %s: %s", option, e)

    async def async_update(self):
        """Leser status fra 1160 og 1130 for å oppdatere menyen."""
        try:
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)

            if res_mode and hasattr(res_mode, 'registers'):
                m_val = res_mode.registers[0]
                s_val = res_speed.registers[0] if res_speed and hasattr(res_speed, 'registers') else 3
                
                if m_val == 0: 
                    self._attr_current_option = "auto"
                elif m_val == 1: 
                    self._attr_current_option = {2: "manual_low", 4: "manual_high"}.get(s_val, "manual_normal")
                elif m_val == 2: self._attr_current_option = "crowded"
                elif m_val == 3: self._attr_current_option = "refresh"
                elif m_val == 4: self._attr_current_option = "fireplace"
                elif m_val == 5: self._attr_current_option = "away"
                elif m_val == 6: self._attr_current_option = "holiday"
        except Exception as e:
            _LOGGER.error("Systemair: Vent mode update failed: %s", e)