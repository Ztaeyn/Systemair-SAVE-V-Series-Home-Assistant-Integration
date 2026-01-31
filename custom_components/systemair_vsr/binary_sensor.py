import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (Name, Register, DeviceClass, Icon, Category)
VSR_BOOLEANS = [
    # ALARMS (Diagnostic category)
    ("A Alarm", 15900, BinarySensorDeviceClass.PROBLEM, "mdi:alert-octagon", EntityCategory.DIAGNOSTIC),
    ("B Alarm", 15901, BinarySensorDeviceClass.PROBLEM, "mdi:alert-circle", EntityCategory.DIAGNOSTIC),
    ("C Alarm", 15902, BinarySensorDeviceClass.PROBLEM, "mdi:alert", EntityCategory.DIAGNOSTIC),
    ("Filter Alarm", 15543, BinarySensorDeviceClass.PROBLEM, "mdi:air-filter", EntityCategory.DIAGNOSTIC),
    ("Supply Air Temp Low Alarm", 15176, BinarySensorDeviceClass.PROBLEM, "mdi:thermometer-alert", EntityCategory.DIAGNOSTIC),
    
    # STATUS / INPUTS
    ("Extractor Hood Status", 12305, BinarySensorDeviceClass.RUNNING, "mdi:stove", None),
    ("Free Cooling Active", 4110, BinarySensorDeviceClass.RUNNING, "mdi:snowflake-check", None),

    # SYSTEM STATUS (Diagnostic category)
    ("TRIAC Control Signal", 14380, BinarySensorDeviceClass.POWER, "mdi:sine-wave", EntityCategory.DIAGNOSTIC),
    ("Maintenance Mode Active", 15000, None, "mdi:wrench-clock", EntityCategory.DIAGNOSTIC), 
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR binary sensors from a config entry."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found for binary sensors", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    entities = [
        SaveVSRBinarySensor(hub, model, slave, *b) 
        for b in VSR_BOOLEANS
    ]
    async_add_entities(entities, True)

class SaveVSRBinarySensor(BinarySensorEntity):
    """Generic SaveVSR Binary Sensor (Alarms and Status)."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name, address, device_class, icon, category):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = address
        
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"{DOMAIN}_{slave}_bin_{address}"

    @property
    def device_info(self):
        """Link to the shared SaveVSR Device."""
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_update(self):
        """Fetch binary status from Modbus."""
        try:
            result = await self._hub.async_pb_call(
                self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING
            )
            
            if result and hasattr(result, 'registers'):
                # Modbus registers are 16-bit; anything > 0 is considered 'On'
                self._attr_is_on = bool(result.registers[0] > 0)
            else:
                self._attr_is_on = None
        except Exception as e:
            _LOGGER.error("SaveVSR: Failed to update binary register %s: %s", self._register, e)
            self._attr_is_on = None