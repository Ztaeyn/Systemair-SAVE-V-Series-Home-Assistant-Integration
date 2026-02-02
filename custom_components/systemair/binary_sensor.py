import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL
from homeassistant.components.modbus.const import CALL_TYPE_REGISTER_HOLDING
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (TranslationKey, Register, DeviceClass, Icon, Category)
SYSTEMAIR_BOOLEANS = [
    # ALARMS
    ("a_alarm", 15900, BinarySensorDeviceClass.PROBLEM, "mdi:alert-octagon", EntityCategory.DIAGNOSTIC),
    ("b_alarm", 15901, BinarySensorDeviceClass.PROBLEM, "mdi:alert-circle", EntityCategory.DIAGNOSTIC),
    ("c_alarm", 15902, BinarySensorDeviceClass.PROBLEM, "mdi:alert", EntityCategory.DIAGNOSTIC),
    ("filter_alarm", 15543, BinarySensorDeviceClass.PROBLEM, "mdi:air-filter", EntityCategory.DIAGNOSTIC),
    ("temp_low_alarm", 15176, BinarySensorDeviceClass.PROBLEM, "mdi:thermometer-alert", EntityCategory.DIAGNOSTIC),
    
    # STATUS / INPUTS
    ("hood_status", 12305, BinarySensorDeviceClass.RUNNING, "mdi:stove", None),
    ("free_cooling", 4110, BinarySensorDeviceClass.RUNNING, "mdi:snowflake-check", None),

    # SYSTEM STATUS
    ("triac_signal", 14380, BinarySensorDeviceClass.POWER, "mdi:sine-wave", EntityCategory.DIAGNOSTIC),
    ("maintenance_mode", 15000, None, "mdi:wrench-clock", EntityCategory.DIAGNOSTIC), 
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Systemair binary sensors."""
    config = entry.data
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, config.get("hub_name", "modbus_hub"))
    
    if hub is None:
        _LOGGER.error("Systemair: Modbus hub not found for binary sensors")
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    async_add_entities([
        SystemairBinarySensor(hub, model, slave, *b) 
        for b in SYSTEMAIR_BOOLEANS
    ], True)

class SystemairBinarySensor(BinarySensorEntity):
    """Generic Systemair Binary Sensor using translation keys."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, translation_key, address, device_class, icon, category):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = address
        
        self._attr_translation_key = translation_key
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"{DOMAIN}_{slave}_bin_{address}_{translation_key}"

    @property
    def device_info(self):
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
                self._attr_is_on = bool(result.registers[0] > 0)
        except Exception as e:
            _LOGGER.error("Systemair: Failed to update binary sensor %s: %s", self._attr_translation_key, e)