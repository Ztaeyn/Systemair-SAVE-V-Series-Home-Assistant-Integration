import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER, 
    CALL_TYPE_REGISTER_HOLDING
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (TranslationKey, Register, Min, Max, Step, Unit, Scale, Icon, Category)
SYSTEMAIR_NUMBERS = [
    # --- Main Controls ---
    ("supply_air_setpoint", 2000, 12, 30, 0.5, "°C", 10, "mdi:thermometer-lines", None),
    ("holiday_duration", 1100, 1, 365, 1, "days", 1, "mdi:airplane-takeoff", None),
    ("away_duration", 1101, 1, 72, 1, "h", 1, "mdi:exit-run", None),
    ("fireplace_duration", 1102, 1, 60, 1, "min", 1, "mdi:fireplace", None),
    ("refresh_duration", 1103, 1, 240, 1, "min", 1, "mdi:air-filter", None),
    ("crowded_duration", 1104, 1, 8, 1, "h", 1, "mdi:account-multiple-plus", None),
    ("eco_offset", 2503, 0, 10, 0.5, "°C", 10, "mdi:leaf", None),
 
    # --- Temperature Configuration ---
    ("exhaust_setpoint", 2012, 12, 30, 0.5, "°C", 10, "mdi:thermometer-low", EntityCategory.CONFIG),
    ("exhaust_min_setpoint", 2020, 10, 20, 0.5, "°C", 10, "mdi:thermometer-chevron-down", EntityCategory.CONFIG),
    ("exhaust_max_setpoint", 2021, 20, 40, 0.5, "°C", 10, "mdi:thermometer-chevron-up", EntityCategory.CONFIG),
   
    # --- Winter Compensation ---
    ("fan_comp_read", 1254, -50, 50, 1, "%", 1, "mdi:fan-alert", EntityCategory.CONFIG),
    ("fan_comp_winter", 1251, -50, 50, 1, "%", 1, "mdi:snowflake-alert", EntityCategory.CONFIG),
    ("winter_comp_temp", 1252, -20, 20, 0.5, "°C", 10, "mdi:thermometer-check", EntityCategory.CONFIG),
    ("winter_comp_start", 1255, -20, 10, 0.5, "°C", 10, "mdi:snowflake-thermometer", EntityCategory.CONFIG),
    ("winter_comp_max", 1253, -20, 20, 0.5, "°C", 10, "mdi:thermometer-chevron-up", EntityCategory.CONFIG),

    # --- Summer Compensation ---
    ("fan_comp_summer", 1258, -50, 50, 1, "%", 1, "mdi:sun-angle", EntityCategory.CONFIG),
    ("summer_comp_start", 1256, 15, 40, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("summer_comp_max", 1257, 20, 50, 0.5, "°C", 10, "mdi:thermometer-chevron-up", EntityCategory.CONFIG),

    # --- Fan Speed Settings ---
    ("sf_min_rpm", 1410, 500, 4500, 10, "rpm", 1, "mdi:fan-minus", EntityCategory.CONFIG),
    ("ef_min_rpm", 1411, 500, 4500, 10, "rpm", 1, "mdi:fan-minus", EntityCategory.CONFIG),
    ("sf_low_rpm", 1302, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-1", EntityCategory.CONFIG),
    ("ef_low_rpm", 1303, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-1", EntityCategory.CONFIG),
    ("sf_normal_rpm", 1414, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-2", EntityCategory.CONFIG),
    ("ef_normal_rpm", 1415, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-2", EntityCategory.CONFIG),
    ("sf_high_rpm", 1416, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-3", EntityCategory.CONFIG),
    ("ef_high_rpm", 1417, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-3", EntityCategory.CONFIG),
    ("sf_max_rpm", 1418, 500, 4500, 10, "rpm", 1, "mdi:fan-chevron-up", EntityCategory.CONFIG),
    ("ef_max_rpm", 1419, 500, 4500, 10, "rpm", 1, "mdi:fan-chevron-up", EntityCategory.CONFIG),

    # --- Mode Setpoints ---
    ("sf_holiday_setpoint", 1220, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow", EntityCategory.CONFIG),
    ("ef_holiday_setpoint", 1221, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow", EntityCategory.CONFIG),
    ("sf_hood_setpoint", 1222, 500, 4500, 10, "rpm", 1, "mdi:speedometer", EntityCategory.CONFIG),
    ("ef_hood_setpoint", 1223, 500, 4500, 10, "rpm", 1, "mdi:speedometer", EntityCategory.CONFIG),
    ("sf_vacuum_setpoint", 1224, 500, 4500, 10, "rpm", 1, "mdi:vacuum", EntityCategory.CONFIG),
    ("ef_vacuum_setpoint", 1225, 500, 4500, 10, "rpm", 1, "mdi:vacuum", EntityCategory.CONFIG),
    ("moisture_setpoint", 2202, 10, 90, 1, "%", 1, "mdi:water-percent", EntityCategory.CONFIG),

    # --- System / Maintenance ---
    ("filter_interval", 7000, 1, 12, 1, "months", 1, "mdi:calendar-clock", EntityCategory.CONFIG),

    # --- Free Cooling ---
    ("fc_outdoor_day_min", 4101, 12.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("fc_outdoor_night_high", 4102, 7.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("fc_outdoor_night_low", 4103, 7.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("fc_indoor_low_limit", 4104, 12.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),

    # --- Weekly Schedule ---
    ("sched_active_offset", 5000, -10.0, 0.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG), 
    ("sched_inactive_offset", 5001, -10.0, 0.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG), 
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SystemAir numbers from a config entry."""
    config = entry.data
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, config.get("hub_name", "modbus_hub"))
    
    if hub is None:
        _LOGGER.error("SystemAir: Modbus hub not found for numbers")
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    async_add_entities([SystemAirNumber(hub, model, slave, *s) for s in SYSTEMAIR_NUMBERS], True)

class SystemAirNumber(NumberEntity):
    """Representation of a Systemair Modbus number entity."""
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(self, hub, model, slave, translation_key, register, min_val, max_val, step, unit, scale, icon, category):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = register
        self._scale = scale
        
        self._attr_translation_key = translation_key
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"{DOMAIN}_{slave}_num_{register}_{translation_key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value on Modbus."""
        try:
            modbus_val = int(value * self._scale)
            # Handle signed integers (2's complement)
            if modbus_val < 0:
                modbus_val += 65536
            
            result = await self._hub.async_pb_call(self._slave, self._register, modbus_val, CALL_TYPE_WRITE_REGISTER)
            if result:
                self._attr_native_value = value
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("SystemAir: Set failed for %s: %s", self._attr_translation_key, e)

    async def async_update(self):
        """Fetch new state data for the entity."""
        try:
            res = await self._hub.async_pb_call(self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING)
            if res and hasattr(res, 'registers'):
                val = res.registers[0]
                # Handle signed integers
                if val > 32767:
                    val -= 65536
                self._attr_native_value = float(val) / self._scale
        except Exception as e:
            _LOGGER.error("SystemAir: Update failed for %s: %s", self._attr_translation_key, e)