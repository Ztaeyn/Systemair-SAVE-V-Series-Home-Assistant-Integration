import asyncio
import logging
from datetime import time
from homeassistant.components.time import TimeEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER, 
    CALL_TYPE_REGISTER_HOLDING
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, "VSR300")
    
    if hub is None:
        _LOGGER.error("Hub VSR300 not found during time setup")
        return
        
    async_add_entities([
        VSR300Time(hub, entry.data, "Free Cooling Start Time", 4105, 4106),
        VSR300Time(hub, entry.data, "Free Cooling End Time", 4107, 4108)
    ])

class VSR300Time(TimeEntity):
    def __init__(self, hub, config, name, hr_reg, min_reg):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._hr_reg = hr_reg
        self._min_reg = min_reg
        
        self._attr_name = name
        self._attr_unique_id = f"vsr300_{self._slave}_time_{hr_reg}"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_value = None

    @property
    def device_info(self):
        """Unified device info to match your other entities."""
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    async def async_set_value(self, value: time) -> None:
        """Write hour and minute with a safety delay."""
        try:
            # Write Hour
            await self._hub.async_pb_call(self._slave, self._hr_reg, value.hour, CALL_TYPE_WRITE_REGISTER)
            
            # Staggered delay to prevent bus collisions
            await asyncio.sleep(0.5)
            
            # Write Minute
            await self._hub.async_pb_call(self._slave, self._min_reg, value.minute, CALL_TYPE_WRITE_REGISTER)
            
            self._attr_native_value = value
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set %s: %s", self._attr_name, e)

    async def async_update(self):
        """Read registers and handle potential 'None' states gracefully."""
        try:
            res_hr = await self._hub.async_pb_call(self._slave, self._hr_reg, 1, CALL_TYPE_REGISTER_HOLDING)
            # Small gap between reads to prevent bus congestion
            await asyncio.sleep(0.1) 
            res_min = await self._hub.async_pb_call(self._slave, self._min_reg, 1, CALL_TYPE_REGISTER_HOLDING)

            if res_hr and res_min and hasattr(res_hr, 'registers') and hasattr(res_min, 'registers'):
                h = res_hr.registers[0]
                m = res_min.registers[0]
                
                # Validation: VSR300 sometimes returns 65535 on comm error
                if 0 <= h <= 23 and 0 <= m <= 59:
                    self._attr_native_value = time(hour=h, minute=m)
                else:
                    self._attr_native_value = None
            else:
                self._attr_native_value = None
        except Exception as e:
            _LOGGER.error("Time update failed for %s: %s", self._attr_name, e)
            self._attr_native_value = None