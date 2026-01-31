import asyncio
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# --- MAPPINGS ---
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

AIRFLOW_LEVELS = {"Normal": 3, "High": 4, "Maximum": 5}
AWAY_LEVELS = {"Off": 0, "Minimum": 1, "Low": 2, "Normal": 3}
SCHEDULE_LEVELS = {"Off": 1, "Low": 2, "Normal": 3, "High": 4, "Demand": 5}
TEMP_CONTROL_MODES = {"Supply": 0, "Room": 1, "Extract": 2}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR select entities."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found for select", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)
        
    async_add_entities([
        SaveVSRVentModeSelect(hub, model, slave, "Ventilation Mode"),

        # Crowded & Refresh
        SaveVSRGeneralSelect(hub, model, slave, "Crowded Airflow Supply Level", 1134, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Crowded Airflow Extract Level", 1135, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Refresh Airflow Supply Level", 1136, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Refresh Airflow Extract Level", 1137, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        
        # Fireplace & Free Cooling
        SaveVSRGeneralSelect(hub, model, slave, "Fireplace Airflow Supply Level", 1138, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Fireplace Airflow Extract Level", 1139, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Free Cooling Supply Level", 4111, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Free Cooling Extract Level", 4112, AIRFLOW_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG),
        
        # Away & Holiday
        SaveVSRGeneralSelect(hub, model, slave, "Away Airflow Supply Level", 1140, AWAY_LEVELS, "mdi:fan-minus", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Away Airflow Extract Level", 1141, AWAY_LEVELS, "mdi:fan-minus", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Holiday Airflow Supply Level", 1142, AWAY_LEVELS, "mdi:fan-off", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Holiday Airflow Extract Level", 1143, AWAY_LEVELS, "mdi:fan-off", EntityCategory.CONFIG),

        # System
        SaveVSRGeneralSelect(hub, model, slave, "Temp Control Mode", 2030, TEMP_CONTROL_MODES, "mdi:tune-vertical", EntityCategory.CONFIG),
        SaveVSRGeneralSelect(hub, model, slave, "Scheduled Airflow Fan Level", 5059, SCHEDULE_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG), 
        SaveVSRGeneralSelect(hub, model, slave, "Unscheduled Airflow Fan Level", 5060, SCHEDULE_LEVELS, "mdi:gauge-full", EntityCategory.CONFIG) 
    ], True)

class SaveVSRGeneralSelect(SelectEntity):
    """Generic Select for single-register mappings."""
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name, register, mapping, icon, category=None):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = register
        self._mapping = mapping
        self._inv_mapping = {v: k for k, v in mapping.items()}
        
        self._attr_name = name
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
                self._attr_current_option = self._inv_mapping.get(res.registers[0], "Unknown")
        except Exception as e:
            _LOGGER.error("SaveVSR: Select update failed for %s: %s", self._attr_name, e)

class SaveVSRVentModeSelect(SelectEntity):
    """Combined Mode (1161) and Speed (1130) control."""
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._attr_name = name
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
            await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
            if speed_val is not None:
                await asyncio.sleep(1.0) 
                await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("SaveVSR: Failed to set ventilation mode %s: %s", option, e)

    async def async_update(self):
        try:
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)

            if res_mode and hasattr(res_mode, 'registers'):
                m_val = res_mode.registers[0]
                s_val = res_speed.registers[0] if res_speed and hasattr(res_speed, 'registers') else None

                if m_val == 0: self._attr_current_option = "Auto"
                elif m_val == 1:
                    self._attr_current_option = {2: "Manual Low", 3: "Manual Normal", 4: "Manual High"}.get(s_val, "Manual Normal")
                else:
                    self._attr_current_option = {2: "Crowded", 3: "Refresh", 4: "Fireplace", 5: "Away", 6: "Holiday"}.get(m_val)
        except Exception as e:
            _LOGGER.error("SaveVSR: Vent mode update failed: %s", e)