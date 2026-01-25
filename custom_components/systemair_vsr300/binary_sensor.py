import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (Name, Register, DeviceClass, Icon)
# Setting DeviceClass automatically changes how "On/Off" is displayed (e.g., Problem/OK, Running/Stopped)
VSR300_BOOLEANS = [
    # ALARMS (Problem class turns red when 'On')
    ("A Alarm", 15900, BinarySensorDeviceClass.PROBLEM, "mdi:alert-octagon"),
    ("B Alarm", 15901, BinarySensorDeviceClass.PROBLEM, "mdi:alert-circle"),
    ("C Alarm", 15902, BinarySensorDeviceClass.PROBLEM, "mdi:alert"),
    ("Filter Alarm", 15543, BinarySensorDeviceClass.PROBLEM, "mdi:air-filter"),
    ("Supply Air Temp Low Alarm", 15176, BinarySensorDeviceClass.PROBLEM, "mdi:thermometer-alert"),
    
    # STATUS / INPUTS
    ("Extractor Hood Status", 12305, BinarySensorDeviceClass.RUNNING, "mdi:stove"),
    ("TRIAC Control Signal", 14380, BinarySensorDeviceClass.POWER, "mdi:sine-wave"),
    ("Maintenance Mode Active", 15000, None, "mdi:wrench-clock"), # Example generic boolean
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the VSR300 binary sensors."""
    hub = get_hub(hass, "VSR300")
    if hub is None:
        _LOGGER.error("Hub VSR300 not found during binary sensor setup")
        return

    # Pass the full tuple into the class
    entities = [VSR300BooleanSensor(hub, entry.data, *b) for b in VSR300_BOOLEANS]
    async_add_entities(entities, True)

class VSR300BooleanSensor(BinarySensorEntity):
    """Representation of a VSR300 Binary State (Alarm or Status)."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, config, name, address, device_class, icon):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._register = address
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_icon = icon
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
                # Modbus standard: 0 is Off/False, 1 is On/True
                # Some units use bitmasking, but usually these status registers are 0 or 1.
                self._attr_is_on = bool(val > 0)
            else:
                self._attr_is_on = None
        except Exception as e:
            _LOGGER.error("Failed to update boolean register %s: %s", self._register, e)
            self._attr_is_on = None