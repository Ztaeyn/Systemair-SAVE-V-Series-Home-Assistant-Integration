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

# List: (Name, Hour_Register, Minute_Register)
VSR_TIME_SETTINGS = [
    ("Free Cooling Start Time", 4105, 4106),
    ("Free Cooling End Time", 4107, 4108),
    # Weekly Schedule
    ("Monday Period 1 Start", 5002, 5003), ("Monday Period 1 End", 5004, 5005),
    ("Monday Period 2 Start", 5006, 5007), ("Monday Period 2 End", 5008, 5009),
    ("Tuesday Period 1 Start", 5010, 5011), ("Tuesday Period 1 End", 5012, 5013),
    ("Tuesday Period 2 Start", 5014, 5015), ("Tuesday Period 2 End", 5016, 5017),
    ("Wednesday Period 1 Start", 5018, 5019), ("Wednesday Period 1 End", 5020, 5021),
    ("Wednesday Period 2 Start", 5022, 5023), ("Wednesday Period 2 End", 5024, 5025),
    ("Thursday Period 1 Start", 5026, 5027), ("Thursday Period 1 End", 5028, 5029),
    ("Thursday Period 2 Start", 5030, 5031), ("Thursday Period 2 End", 5032, 5033),
    ("Friday Period 1 Start", 5034, 5035), ("Friday Period 1 End", 5036, 5037),
    ("Friday Period 2 Start", 5038, 5039), ("Friday Period 2 End", 5040, 5041),
    ("Saturday Period 1 Start", 5042, 5043), ("Saturday Period 1 End", 5044, 5045),
    ("Saturday Period 2 Start", 5046, 5047), ("Saturday Period 2 End", 5048, 5049),
    ("Sunday Period 1 Start", 5050, 5051), ("Sunday Period 1 End", 5052, 5053),
    ("Sunday Period 2 Start", 5054, 5055), ("Sunday Period 2 End", 5056, 5057),
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR time entities."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found for time setup", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    entities = [SaveVSRTime(hub, model, slave, *t) for t in VSR_TIME_SETTINGS]
    async_add_entities(entities, True)

class SaveVSRTime(TimeEntity):
    """Representation of a SaveVSR Time setting (Hour/Minute registers)."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name, hr_reg, min_reg):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._hr_reg = hr_reg
        self._min_reg = min_reg
        
        self._attr_name = name
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
            await asyncio.sleep(0.3) # Wait for unit to process
            await self._hub.async_pb_call(self._slave, self._min_reg, value.minute, CALL_TYPE_WRITE_REGISTER)
            
            self._attr_native_value = value
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("SaveVSR: Failed to set %s: %s", self._attr_name, e)

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
            _LOGGER.error("SaveVSR: Time update failed for %s: %s", self._attr_name, e)
            self._attr_native_value = None