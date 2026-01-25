import asyncio
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_REGISTER_HOLDING,
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# Mapping: "Friendly Name": (Register 1161 Command, Register 1130 Speed or None)
VENTILATION_MODES = {
    "Low": (1, 2),    # Manual Mode (1) + Speed 2
    "Normal": (1, 3), # Manual Mode (1) + Speed 3
    "High": (1, 4),   # Manual Mode (1) + Speed 4
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
        """Link this entity to the VSR300 Device."""
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_select_option(self, option: str) -> None:
        """Set Mode and Speed using working Modbus constants."""
        mode_val, speed_val = VENTILATION_MODES[option]

        try:
            # 1. Write User Mode (1161)
            await self._hub.async_pb_call(
                self._slave, 1161, mode_val, CALL_TYPE_WRITE_REGISTER
            )
            
            # 2. Write Fan Speed (1130) if required
            if speed_val is not None:
                await asyncio.sleep(1.0) # Small delay for the unit to process mode change
                await self._hub.async_pb_call(
                    self._slave, 1130, speed_val, CALL_TYPE_WRITE_REGISTER
                )
            
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set select mode %s: %s", option, e)

    async def async_update(self):
        """Sync the select list with status register 1160."""
        try:
            # Read Current Status (1160) and Current Speed (1130)
            res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_HOLDING)
            res_speed = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)

            if res_mode and hasattr(res_mode, 'registers'):
                curr_mode = res_mode.registers[0]
                
                # Check if we are in Manual Status (usually 1 on register 1160)
                if curr_mode == 1:
                    if res_speed and hasattr(res_speed, 'registers'):
                        curr_speed = res_speed.registers[0]
                        speed_map = {2: "Low", 3: "Normal", 4: "High"}
                        self._attr_current_option = speed_map.get(curr_speed, "Low")
                else:
                    # Map the other status codes to your list options
                    # Note: These must match the KEYS in VENTILATION_MODES exactly
                    mode_map = {
                        0: "Auto",
                        2: "Crowded",
                        3: "Refresh",
                        4: "Fireplace",
                        5: "Away",
                        6: "Holiday"
                    }
                    self._attr_current_option = mode_map.get(curr_mode)

            # If the current option is still None, it means the unit is in a state
            # not represented in our simple list (like 'Cooker Hood' or 'Fire')
            
        except Exception as e:
            _LOGGER.error("Select update failed: %s", e)