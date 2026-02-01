import asyncio
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTER
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

VENT_ACTIONS = {
    "Normal Mode": (2, 3),
    "Low Speed": (2, 2),
    "High Speed": (2, 4),
    "Fireplace": (5, None),
    "Refresh": (4, None),
    "Crowded": (3, None),
    "Away": (6, None),
    "Auto": (1, None),
    "Stop Unit": (0, None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR buttons from a config entry."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found for buttons", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    entities = [
        SaveVSRButton(hub, model, slave, name, mode, speed)
        for name, (mode, speed) in VENT_ACTIONS.items()
    ]
    
    async_add_entities(entities)

class SaveVSRButton(ButtonEntity):
    """Generic SaveVSR Action Button."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name, mode_val, speed_val):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._mode_val = mode_val
        self._speed_val = speed_val
        
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{slave}_btn_{name.lower().replace(' ', '_')}"
        self._attr_icon = "mdi:play-box-outline"

    @property
    def device_info(self):
        """Unified device info to match all other SaveVSR entities."""
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_press(self) -> None:
        """Handle the button press to trigger ventilation modes."""
        try:
            # 1. Write the Mode Register (1161)
            _LOGGER.debug("SaveVSR Button: Writing Mode %s to 1161", self._mode_val)
            await self._hub.async_pb_call(
                self._slave, 
                1161, 
                self._mode_val, 
                CALL_TYPE_WRITE_REGISTER
            )
            
            # 2. Write Fan Speed (1130) if a specific speed is required for this action
            if self._speed_val is not None:
                # Modbus often needs a small breath between sequential writes
                await asyncio.sleep(1.0)
                _LOGGER.debug("SaveVSR Button: Writing Speed %s to 1130", self._speed_val)
                await self._hub.async_pb_call(
                    self._slave, 
                    1130, 
                    self._speed_val, 
                    CALL_TYPE_WRITE_REGISTER
                )
        except Exception as e:
            _LOGGER.error("SaveVSR Button '%s' failed: %s", self._attr_name, e)