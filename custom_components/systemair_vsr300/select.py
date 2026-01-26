import asyncio
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT, # Added for 1160
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# Mapping: "Friendly Name": (Register 1161 Command, Register 1130 Speed or None)
# Note: These keys are what the user sees in the dropdown
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
        _LOGGER.error("Hub VSR300 not found during select setup")
        return
        
    async_add_entities([VSR300Select(hub, entry.data, "Ventilation Mode")])

class VSR300Select(SelectEntity):
    def __init__(self, hub, config, name):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._attr_name = name
        self._attr_options = list(VENTILATION_MODES.keys())
        self._attr_current_option = None
        self._attr_unique_id = f"vsr300_{self._slave}_vent_mode"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_select_option(self, option: str) -> None:
        """Set Mode and Speed."""
        mode_val, speed_val = VENTILATION_MODES[option]
        try:
            # 1. Write User Mode Command (1161)
            await self._hub.async_pb_call(self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER)
            
            # 2. Write Fan Speed (1130) if required
            if speed_val is not None:
                await asyncio.sleep(0.5) 
                await self._hub.async_pb_call(self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER)
            
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set select mode %s: %s", option, e)

    async def async_update(self):
        """Sync the select list with status register 1160 and speed 1130."""
        try:
            # 1160 is an INPUT register on VSR300
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
            # 1130 is a HOLDING register
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)

            if res_mode and hasattr(res_mode, 'registers'):
                mode_val = res_mode.registers[0]
                cmd_val = res_speed.registers[0] if res_speed and hasattr(res_speed, 'registers') else None

                # Logic to map hardware state back to one of our dropdown options
                if mode_val == 0:
                    self._attr_current_option = "Auto"
                elif mode_val == 1:
                    speed_map = {2: "Manual Low", 3: "Manual Normal", 4: "Manual High"}
                    self._attr_current_option = speed_map.get(cmd_val, "Manual Normal")
                else:
                    mode_map = {
                        2: "Crowded", 3: "Refresh", 4: "Fireplace", 
                        5: "Away", 6: "Holiday"
                    }
                    self._attr_current_option = mode_map.get(mode_val)

        except Exception as e:
            _LOGGER.error("Select update failed: %s", e)