import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (Name, Register, DeviceClass, Icon, Category)
VSR300_BOOLEANS = [
    # ALARMS (Diagnostic category)
    ("A Alarm", 15900, BinarySensorDeviceClass.PROBLEM, "mdi:alert-octagon", EntityCategory.DIAGNOSTIC),
    ("B Alarm", 15901, BinarySensorDeviceClass.PROBLEM, "mdi:alert-circle", EntityCategory.DIAGNOSTIC),
    ("C Alarm", 15902, BinarySensorDeviceClass.PROBLEM, "mdi:alert", EntityCategory.DIAGNOSTIC),
    ("Filter Alarm", 15543, BinarySensorDeviceClass.PROBLEM, "mdi:air-filter", EntityCategory.DIAGNOSTIC),
    ("Supply Air Temp Low Alarm", 15176, BinarySensorDeviceClass.PROBLEM, "mdi:thermometer-alert", EntityCategory.DIAGNOSTIC),
    
    # STATUS / INPUTS (Main Card)
    ("Extractor Hood Status", 12305, BinarySensorDeviceClass.RUNNING, "mdi:stove", None),
    ("Free Cooling Active", 4110, BinarySensorDeviceClass.RUNNING, "mdi:snowflake-check", None),
    
    # SYSTEM STATUS (Diagnostic category)
    ("TRIAC Control Signal", 14380, BinarySensorDeviceClass.POWER, "mdi:sine-wave", EntityCategory.DIAGNOSTIC),
    ("Maintenance Mode Active", 15000, None, "mdi:wrench-clock", EntityCategory.DIAGNOSTIC), 
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the VSR300 binary sensors."""
    hub = get_hub(hass, "VSR300")
    if hub is None:
        _LOGGER.error("Hub VSR300 not found during binary sensor setup")
        return

    entities = [VSR300BooleanSensor(hub, entry.data, *b) for b in VSR300_BOOLEANS]
    async_add_entities(entities, True)

class VSR300BooleanSensor(BinarySensorEntity):
    """Representation of a VSR300 Binary State (Alarm or Status)."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, config, name, address, device_class, icon, category):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._register = address
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"vsr300_{self._slave}_bool_{address}"
        self._attr_is_on = None

    @property
    def device_info(self):
        """Link this entity to the VSR300 Device."""
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_update(self):
        """Fetch status from the register."""
        try:
            result = await self._hub.async_pb_call(
                self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING
            )
            
            if result and hasattr(result, 'registers'):
                val = result.registers[0]
                self._attr_is_on = bool(val > 0)
            else:
                self._attr_is_on = None
        except Exception as e:
            _LOGGER.error("Failed to update boolean register %s: %s", self._register, e)
            self._attr_is_on = None