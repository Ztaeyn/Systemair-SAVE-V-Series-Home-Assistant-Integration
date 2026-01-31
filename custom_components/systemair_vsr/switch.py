import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER, 
    CALL_TYPE_REGISTER_HOLDING
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (Name, Register, Icon, Category)
VSR_SWITCHES = [
    ("Eco Mode", 2504, "mdi:leaf", None),
    ("Free Cooling", 4100, "mdi:snowflake-thermometer", None),
    ("Fan Manual Stop Allowed", 1352, "mdi:fan-off", EntityCategory.CONFIG),

    # Weekly Schedule Toggle
    ("Monday Period 1", 5100, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Monday Period 2", 5101, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Tuesday Period 1", 5102, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Tuesday Period 2", 5103, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Wednesday Period 1", 5104, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Wednesday Period 2", 5105, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Thursday Period 1", 5106, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Thursday Period 2", 5107, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Friday Period 1", 5108, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Friday Period 2", 5109, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Saturday Period 1", 5110, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Saturday Period 2", 5111, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Sunday Period 1", 5112, "mdi:calendar-check", EntityCategory.CONFIG),
    ("Sunday Period 2", 5113, "mdi:calendar-check", EntityCategory.CONFIG),  
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR switches."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found for switches", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    entities = [SaveVSRSwitch(hub, model, slave, *s) for s in VSR_SWITCHES]
    async_add_entities(entities, True)

class SaveVSRSwitch(SwitchEntity):
    """Generic SaveVSR Modbus Switch."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name, register, icon, category):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = register
        
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"{DOMAIN}_{slave}_sw_{register}"
        self._attr_is_on = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_turn_on(self, **kwargs):
        """Write 1 to enable the feature."""
        result = await self._hub.async_pb_call(self._slave, self._register, 1, CALL_TYPE_WRITE_REGISTER)
        if result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Write 0 to disable the feature."""
        result = await self._hub.async_pb_call(self._slave, self._register, 0, CALL_TYPE_WRITE_REGISTER)
        if result:
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_update(self):
        """Read current state from Modbus register."""
        try:
            result = await self._hub.async_pb_call(self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING)
            if result and hasattr(result, 'registers'):
                self._attr_is_on = (result.registers[0] == 1)
        except Exception as e:
            _LOGGER.error("SaveVSR: Update failed for switch %s: %s", self._attr_name, e)