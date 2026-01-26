import asyncio
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTER
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# Action Mapping: (Name, 1161_Mode, 1130_Speed or None)
VENT_ACTIONS = {
    "Activate Normal Mode": (2, 3),
    "Activate Low Speed": (2, 2),
    "Activate High Speed": (2, 4),
    "Activate Fireplace": (5, None),
    "Activate Refresh": (4, None),
    "Activate Crowded": (3, None),
    "Activate Away": (6, None),
    "Activate Auto": (1, None),
    "Activate Stop": (0, None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the buttons using the working hub lookup."""
    hub = get_hub(hass, "VSR300")
    if hub is None:
        _LOGGER.error("Hub VSR300 not found during button setup")
        return

    entities = []
    for name, (mode, speed) in VENT_ACTIONS.items():
        entities.append(VSR300Button(hub, entry.data, name, mode, speed))
    
    # Filter Reset (Register 12122)
    entities.append(VSR300Button(hub, entry.data, "Reset Filter Timer", 1, None, 12122))
    
    async_add_entities(entities)

class VSR300Button(ButtonEntity):
    def __init__(self, hub, config, name, mode_val, speed_val, custom_reg=1161):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._attr_name = name
        self._mode_val = mode_val
        self._speed_val = speed_val
        self._register = custom_reg
        self._attr_unique_id = f"vsr300_{self._slave}_{name.lower().replace(' ', '_')}"

    @property
    def device_info(self):
        """Link this entity to the VSR300 Device."""
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_press(self) -> None:
        """Handle button press using the proven Select/Climate logic."""
        try:
            # 1. Write Primary Register
            _LOGGER.debug("VSR300 Button: Writing %s to %s", self._mode_val, self._register)
            await self._hub.async_pb_call(
                self._slave, 
                self._register, 
                self._mode_val, 
                CALL_TYPE_WRITE_REGISTER
            )
            
            # 2. Write Speed if required
            if self._speed_val is not None:
                await asyncio.sleep(1.5)
                _LOGGER.debug("VSR300 Button: Writing Speed %s to 1130", self._speed_val)
                await self._hub.async_pb_call(
                    self._slave, 
                    1130, 
                    self._speed_val, 
                    CALL_TYPE_WRITE_REGISTER
                )
        except Exception as e:
            _LOGGER.error("VSR300 Button '%s' failed: %s", self._attr_name, e)