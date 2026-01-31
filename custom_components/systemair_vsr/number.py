import logging
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER, 
    CALL_TYPE_REGISTER_HOLDING
)
# We assume Platform constants are used in __init__, but strings work for setup
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (Name, Register, Min, Max, Step, Unit, Scale, Icon, Category)
VSR_NUMBERS = [
    # --- Main Controls (Category: None) ---
    ("Supply Air Setpoint", 2000, 12, 30, 0.5, "°C", 10, "mdi:thermometer-lines", None),
    ("Holiday Mode Duration", 1100, 1, 365, 1, "days", 1, "mdi:airplane-takeoff", None),
    ("Away Mode Duration", 1101, 1, 72, 1, "h", 1, "mdi:exit-run", None),
    ("Fireplace Mode Duration", 1102, 1, 60, 1, "min", 1, "mdi:fireplace", None),
    ("Refresh Mode Duration", 1103, 1, 240, 1, "min", 1, "mdi:air-filter", None),
    ("Crowded Mode Duration", 1104, 1, 8, 1, "h", 1, "mdi:account-multiple-plus", None),
    ("Eco Mode Heat Offset", 2503, 0, 10, 0.5, "°C", 10, "mdi:leaf", None),
 
    # --- Temperature Configuration (Category: CONFIG) ---
    ("Exhaust Air Setpoint", 2012, 12, 30, 0.5, "°C", 10, "mdi:thermometer-low", EntityCategory.CONFIG),
    ("Exhaust Air Minimum Setpoint", 2020, 10, 20, 0.5, "°C", 10, "mdi:thermometer-chevron-down", EntityCategory.CONFIG),
    ("Exhaust Air Maximum Setpoint", 2021, 20, 40, 0.5, "°C", 10, "mdi:thermometer-chevron-up", EntityCategory.CONFIG),
   
    # --- Winter Compensation (Category: CONFIG) ---
    ("Fan Speed Comp Read", 1254, -50, 50, 1, "%", 1, "mdi:fan-alert", EntityCategory.CONFIG),
    ("Fan Speed Comp Winter", 1251, -50, 50, 1, "%", 1, "mdi:snowflake-alert", EntityCategory.CONFIG),
    ("Winter Comp Checked Temp", 1252, -20, 20, 0.5, "°C", 10, "mdi:thermometer-check", EntityCategory.CONFIG),
    ("Winter Comp Start Temp", 1255, -20, 10, 0.5, "°C", 10, "mdi:snowflake-thermometer", EntityCategory.CONFIG),
    ("Winter Comp Max Temp", 1253, -20, 20, 0.5, "°C", 10, "mdi:thermometer-chevron-up", EntityCategory.CONFIG),

    # --- Summer Compensation (Category: CONFIG) ---
    ("Fan Speed Comp Summer", 1258, -50, 50, 1, "%", 1, "mdi:sun-angle", EntityCategory.CONFIG),
    ("Summer Comp Start Temp", 1256, 15, 40, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("Summer Comp Max Temp", 1257, 20, 50, 0.5, "°C", 10, "mdi:thermometer-chevron-up", EntityCategory.CONFIG),

    # --- Fan Speed Settings (Category: CONFIG) ---
    ("Supply Fan Minimum RPM", 1410, 500, 4500, 10, "rpm", 1, "mdi:fan-minus", EntityCategory.CONFIG),
    ("Exhaust Fan Minimum RPM", 1411, 500, 4500, 10, "rpm", 1, "mdi:fan-minus", EntityCategory.CONFIG),
    ("Supply Fan Low RPM", 1302, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-1", EntityCategory.CONFIG),
    ("Exhaust Fan Low RPM", 1303, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-1", EntityCategory.CONFIG),
    ("Supply Fan Normal RPM", 1414, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-2", EntityCategory.CONFIG),
    ("Exhaust Fan Normal RPM", 1415, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-2", EntityCategory.CONFIG),
    ("Supply Fan High RPM", 1416, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-3", EntityCategory.CONFIG),
    ("Exhaust Fan High RPM", 1417, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-3", EntityCategory.CONFIG),
    ("Supply Fan Maximum RPM", 1418, 500, 4500, 10, "rpm", 1, "mdi:fan-chevron-up", EntityCategory.CONFIG),
    ("Exhaust Fan Maximum RPM", 1419, 500, 4500, 10, "rpm", 1, "mdi:fan-chevron-up", EntityCategory.CONFIG),

    # --- Mode Setpoints (Category: CONFIG) ---
    ("Holiday Supply Fan Setpoint", 1220, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow", EntityCategory.CONFIG),
    ("Holiday Exhaust Fan Setpoint", 1221, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow", EntityCategory.CONFIG),
    ("Cooker Hood Supply Fan Setpoint", 1222, 500, 4500, 10, "rpm", 1, "mdi:speedometer", EntityCategory.CONFIG),
    ("Cooker Hood Exhaust Fan Setpoint", 1223, 500, 4500, 10, "rpm", 1, "mdi:speedometer", EntityCategory.CONFIG),
    ("Vacuum Supply Fan Setpoint", 1224, 500, 4500, 10, "rpm", 1, "mdi:vacuum", EntityCategory.CONFIG),
    ("Vacuum Exhaust Fan Setpoint", 1225, 500, 4500, 10, "rpm", 1, "mdi:vacuum", EntityCategory.CONFIG),
    ("Moisture Extraction Setpoint", 2202, 10, 90, 1, "%", 1, "mdi:water-percent", EntityCategory.CONFIG),

    # --- System / Maintenance (Category: CONFIG) ---
    ("Filter Change Interval", 7000, 1, 12, 1, "mo", 1, "mdi:calendar-clock", EntityCategory.CONFIG),

    # --- Free Cooling (Category: CONFIG) ---
    ("Free Cooling Outdoor Day Min Temp Start", 4101, 12.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("Free Cooling Outdoor Night High Limit", 4102, 7.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("Free Cooling Outdoor Night Low Limit", 4103, 7.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),
    ("Free Cooling Indoor Day Low Limit", 4104, 12.0, 30.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG),

    # --- Weekly Schedule (Category: CONFIG) ---
    ("Schedule Active - Temp Offset", 5000, -10.0, 0.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG), 
    ("Schedule Inactive - Temp Offset", 5001, -10.0, 0.0, 0.5, "°C", 10, "mdi:sun-thermometer", EntityCategory.CONFIG), 
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR numbers from a config entry."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found for numbers", hub_name)
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)

    entities = [
        SaveVSRNumberSetpoint(hub, model, slave, *s) 
        for s in VSR_NUMBERS
    ]
    async_add_entities(entities, True)

class SaveVSRNumberSetpoint(NumberEntity):
    """Generic SaveVSR Number Entity for setpoints and configurations."""
    
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name, register, min_val, max_val, step, unit, scale, icon, category):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = register
        self._scale = scale
        
        self._attr_name = name
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"{DOMAIN}_{slave}_num_{register}"
        self._attr_native_value = None

    @property
    def device_info(self):
        """Unified device info for SaveVSR."""
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    async def async_set_native_value(self, value: float) -> None:
        """Handle user input from the UI slider."""
        try:
            modbus_value = int(value * self._scale)
            
            # Handle negative values for offsets (2's complement)
            if modbus_value < 0:
                modbus_value += 65536

            await self._hub.async_pb_call(
                self._slave, self._register, modbus_value, CALL_TYPE_WRITE_REGISTER
            )
            self._attr_native_value = value
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("SaveVSR: Set value failed for %s: %s", self._attr_name, e)

    async def async_update(self):
        """Fetch current value from the unit."""
        try:
            result = await self._hub.async_pb_call(
                self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING
            )
            if result and hasattr(result, 'registers'):
                val = result.registers[0]
                
                # Convert back from 2's complement for negative numbers (e.g. offsets)
                if val > 32767:
                    val -= 65536
                    
                self._attr_native_value = float(val) / self._scale
            else:
                self._attr_native_value = None
        except Exception as e:
            _LOGGER.error("SaveVSR: Update failed for %s: %s", self._attr_name, e)
            self._attr_native_value = None