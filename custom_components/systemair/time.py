import asyncio
import logging
from datetime import time
from homeassistant.components.time import TimeEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER, 
    CALL_TYPE_REGISTER_HOLDING
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (TranslationKey, Hour_Register, Minute_Register)
TIME_SETTINGS = [
    ("fc_start", 4105, 4106),
    ("fc_end", 4107, 4108),
    # Weekly Schedule - Fixed the mon_p1_end typo here
    ("mon_p1_start", 5002, 5003), ("mon_p1_end", 5004, 5005), 
    ("mon_p2_start", 5006, 5007), ("mon_p2_end", 5008, 5009),
    ("tue_p1_start", 5010, 5011), ("tue_p1_end", 5012, 5013),
    ("tue_p2_start", 5014, 5015), ("tue_p2_end", 5016, 5017),
    ("wed_p1_start", 5018, 5019), ("wed_p1_end", 5020, 5021),
    ("wed_p2_start", 5022, 5023), ("wed_p2_end", 5024, 5025),
    ("thu_p1_start", 5026, 5027), ("thu_p1_end", 5028, 5029),
    ("thu_p2_start", 5030, 5031), ("thu_p2_end", 5032, 5033),
    ("fri_p1_start", 5034, 5035), ("fri_p1_end", 5036, 5037),
    ("fri_p2_start", 5038, 5039), ("fri_p2_end", 5040, 5041),
    ("sat_p1_start", 5042, 5043), ("sat_p1_end", 5044, 5045),
    ("sat_p2_start", 5046, 5047), ("sat_p2_end", 5048, 5049),
    ("sun_p1_start", 5050, 5051), ("sun_p1_end", 5052, 5053),
    ("sun_p2_start", 5054, 5055), ("sun_p2_end", 5056, 5057),
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up time entities."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("Systemair: Modbus hub '%s' not found for time setup", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    entities = [SaveTime(hub, model, slave, *t) for t in TIME_SETTINGS]
    async_add_entities(entities, True)

class SaveTime(TimeEntity):
    """Representation of Time setting (Hour/Minute registers)."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, translation_key, hr_reg, min_reg):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._hr_reg = hr_reg
        self._min_reg = min_reg
        
        # Changed from self._attr_name to self._attr_translation_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{slave}_time_{hr_reg}"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_value = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_set_value(self, value: time) -> None:
        """Write hour and minute registers."""
        try:
            await self._hub.async_pb_call(self._slave, self._hr_reg, value.hour, CALL_TYPE_WRITE_REGISTER)
            await asyncio.sleep(0.3) 
            await self._hub.async_pb_call(self._slave, self._min_reg, value.minute, CALL_TYPE_WRITE_REGISTER)
            
            self._attr_native_value = value
            self.async_write_ha_state()
        except Exception as e:
            # Updated to use translation_key for logging
            _LOGGER.error("Systemair: Failed to set %s: %s", self._attr_translation_key, e)

    async def async_update(self):
        """Read time registers."""
        try:
            res_hr = await self._hub.async_pb_call(self._slave, self._hr_reg, 1, CALL_TYPE_REGISTER_HOLDING)
            res_min = await self._hub.async_pb_call(self._slave, self._min_reg, 1, CALL_TYPE_REGISTER_HOLDING)

            if res_hr and res_min and hasattr(res_hr, 'registers') and hasattr(res_min, 'registers'):
                h, m = res_hr.registers[0], res_min.registers[0]
                if 0 <= h <= 23 and 0 <= m <= 59:
                    self._attr_native_value = time(hour=h, minute=m)
                else:
                    self._attr_native_value = None
        except Exception as e:
            # Updated to use translation_key for logging
            _LOGGER.error("Systemair: Time update failed for %s: %s", self._attr_translation_key, e)
            self._attr_native_value = None