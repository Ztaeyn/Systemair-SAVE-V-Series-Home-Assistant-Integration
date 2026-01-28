import asyncio
import logging
from homeassistant.components.select import SelectEntity
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

AIRFLOW_LEVELS = {
    "Normal": 3,
    "High": 4,
    "Maximum": 5
}

TEMP_CONTROL_MODES = {
    "Supply": 0,
    "Room": 1,
    "Extract": 2
}

# 0: Off (requires OFF switch enabled), 1: Min, 2: Low, 3: Normal
AWAY_LEVELS = {
    "Off": 0,
    "Minimum": 1,
    "Low": 2,
    "Normal": 3
}

# --- SETUP ---

async def async_setup_entry(hass, entry, async_add_entities):
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, "VSR300")
    
    if hub is None:
        _LOGGER.error("Hub VSR300 not found during select setup")
        return
        
    # We create three different select entities here
    async_add_entities([
        VSR300VentModeSelect(hub, entry.data, "Ventilation Mode"),
        #Airflow levels
        VSR300GeneralSelect(hub, entry.data, "Crowded Airflow Supply Level", 1134, AIRFLOW_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Crowded Airflow Extract Level", 1135, AIRFLOW_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Refresh Airflow Supply Level", 1136, AIRFLOW_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Refresh Airflow Extract Level", 1137, AIRFLOW_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Fireplace Airflow Supply Level", 1138, AIRFLOW_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Fireplace Airflow Extract Level", 1139, AIRFLOW_LEVELS, "mdi:gauge-full"),
        #Airflow "away"
        VSR300GeneralSelect(hub, entry.data, "Away Airflow Supply Level", 1140, AWAY_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Away Airflow Extract Level", 1141, AWAY_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Holiday Airflow Supply Level", 1142, AWAY_LEVELS, "mdi:gauge-full"),
        VSR300GeneralSelect(hub, entry.data, "Holiday Airflow Extract Level", 1143, AWAY_LEVELS, "mdi:gauge-full"),


        VSR300GeneralSelect(hub, entry.data, "Temp Control Mode", 2030, TEMP_CONTROL_MODES, "mdi:tune-vertical")
    ])

# --- ENTITY CLASSES ---

class VSR300GeneralSelect(SelectEntity):
    """Generic Select for single-register mappings (Crowded Level, Temp Control)."""
    def __init__(self, hub, config, name, register, mapping, icon):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._register = register
        self._mapping = mapping
        self._inv_mapping = {v: k for k, v in mapping.items()}
        
        self._attr_name = name
        self._attr_options = list(mapping.keys())
        self._attr_icon = icon
        self._attr_unique_id = f"vsr300_{self._slave}_select_{register}"
        self._attr_current_option = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"vsr300_{self._slave}")}, "name": "Systemair VSR300"}

    async def async_select_option(self, option: str) -> None:
        val = self._mapping.get(option)
        if val is not None:
            await self._hub.async_pb_call(self._slave, self._register, val, CALL_TYPE_WRITE_REGISTER)
            self._attr_current_option = option
            self.async_write_ha_state()

    async def async_update(self):
        res = await self._hub.async_pb_call(self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING)
        if res and hasattr(res, 'registers'):
            self._attr_current_option = self._inv_mapping.get(res.registers[0], "Unknown")

class VSR300VentModeSelect(SelectEntity):
    """Your original complex Mode + Speed select."""
    def __init__(self, hub, config, name):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._attr_name = name
        self._attr_options = list(VENTILATION_MODES.keys())
        self._attr_current_option = None
        self._attr_unique_id = f"vsr300_{self._slave}_vent_mode"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"vsr300_{self._slave}")}, "name": "Systemair VSR300"}

    async def async_select_option(self, option: str) -> None:
        mode_val, speed_val = VENTILATION_MODES[option]
        try:
            await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
            if speed_val is not None:
                await asyncio.sleep(0.5) 
                await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set select mode %s: %s", option, e)

    async def async_update(self):
        try:
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)

            if res_mode and hasattr(res_mode, 'registers'):
                mode_val = res_mode.registers[0]
                cmd_val = res_speed.registers[0] if res_speed and hasattr(res_speed, 'registers') else None

                if mode_val == 0:
                    self._attr_current_option = "Auto"
                elif mode_val == 1:
                    speed_map = {2: "Manual Low", 3: "Manual Normal", 4: "Manual High"}
                    self._attr_current_option = speed_map.get(cmd_val, "Manual Normal")
                else:
                    mode_map = {2: "Crowded", 3: "Refresh", 4: "Fireplace", 5: "Away", 6: "Holiday"}
                    self._attr_current_option = mode_map.get(mode_val)
        except Exception as e:
            _LOGGER.error("Select update failed: %s", e)