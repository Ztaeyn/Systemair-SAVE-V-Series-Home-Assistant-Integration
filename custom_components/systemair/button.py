import asyncio
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_MODEL
from homeassistant.components.modbus.const import CALL_TYPE_WRITE_REGISTER
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# --- ACTION MAPPINGS ---
# (TranslationKey, ModeValue (1161), SpeedValue (1130))
# Register 1161: 1=Auto, 1=Manual, 3=Crowded, 4=Refresh, 5=Fireplace, 6=Away, 7=Holiday
VENT_ACTIONS = {
    "btn_auto": (1, None),
    "btn_low_speed": (2, 2),    # Skriver 2 -> Leser 1 (Manual)
    "btn_normal_mode": (2, 3),  # Skriver 2 -> Leser 1 (Manual)
    "btn_high_speed": (2, 4),   # Skriver 2 -> Leser 1 (Manual)
    "btn_crowded": (3, None),   # Skriver 3 -> Leser 2
    "btn_refresh": (4, None),   # Skriver 4 -> Leser 3
    "btn_fireplace": (5, None), # Skriver 5 -> Leser 4
    "btn_away": (6, None),      # Skriver 6 -> Leser 5
    "btn_holiday": (7, None),   # Skriver 7 -> Leser 6
#    "btn_stop": (2, 0),         
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SystemAir buttons from a config entry."""
    config = entry.data
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, config.get("hub_name", "modbus_hub"))
    
    if hub is None:
        _LOGGER.error("SystemAir: Modbus hub not found for buttons")
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    entities = [
        SystemAirButton(hub, model, slave, key, mode, speed)
        for key, (mode, speed) in VENT_ACTIONS.items()
    ]
    
    async_add_entities(entities)

class SystemAirButton(ButtonEntity):
    """Generic SystemAir Action Button using translation keys."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, translation_key, mode_val, speed_val):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._mode_val = mode_val
        self._speed_val = speed_val
        
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{slave}_btn_{translation_key}"
        self._attr_icon = "mdi:play-box-outline"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            # 1. Skriv til Modus-register (1161)
            await self._hub.async_pb_call(self._slave, 1161, self._mode_val, CALL_TYPE_WRITE_REGISTER)
            
            # 2. Skriv viftehastighet hvis definert (brukes for Manuelle moduser/Stop)
            if self._speed_val is not None:
                await asyncio.sleep(1.0)
                await self._hub.async_pb_call(self._slave, 1130, self._speed_val, CALL_TYPE_WRITE_REGISTER)
            
            _LOGGER.debug("SystemAir: Button %s pressed, mode %s, speed %s", 
                         self._attr_translation_key, self._mode_val, self._speed_val)
        except Exception as e:
            _LOGGER.error("SystemAir Button '%s' failed: %s", self._attr_translation_key, e)