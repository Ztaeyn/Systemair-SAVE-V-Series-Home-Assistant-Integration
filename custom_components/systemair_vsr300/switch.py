import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER, 
    CALL_TYPE_REGISTER_HOLDING
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    hub = get_hub(hass, "VSR300")
    config = entry.data
    
    # List: (Name, Register, Icon, Category)
    # Eco Mode has category None so it stays on the main card.
    switches = [
        ("Eco Mode", 2504, "mdi:leaf", None),
        ("Free Cooling", 4100, "mdi:snowflake-thermometer", None),
        ("Fan Manual Stop Allowed", 1352, "mdi:fan-off", EntityCategory.CONFIG),
    ]

    entities = [VSR300Switch(hub, config, *s) for s in switches]
    async_add_entities(entities, True)

class VSR300Switch(SwitchEntity):
    """Representation of a VSR300 Modbus Switch."""

    def __init__(self, hub, config, name, register, icon, category):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._register = register
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"vsr300_switch_{self._slave}_{register}"
        self._attr_is_on = False

    @property
    def device_info(self):
        """Link this entity to the VSR300 Device."""
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_turn_on(self, **kwargs):
        """Write 1 to enable."""
        result = await self._hub.async_pb_call(
            self._slave, self._register, 1, CALL_TYPE_WRITE_REGISTER
        )
        if result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Write 0 to disable."""
        result = await self._hub.async_pb_call(
            self._slave, self._register, 0, CALL_TYPE_WRITE_REGISTER
        )
        if result:
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_update(self):
        """Verify the state of the switch from the register."""
        try:
            result = await self._hub.async_pb_call(
                self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING
            )
            if result and hasattr(result, 'registers'):
                self._attr_is_on = result.registers[0] == 1
            else:
                self._attr_is_on = None
        except Exception as e:
            _LOGGER.error("Error updating switch %s: %s", self._attr_name, e)
            self._attr_is_on = None