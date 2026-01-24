import logging
from homeassistant.components.number import NumberEntity
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import (
    CALL_TYPE_WRITE_REGISTER, 
    CALL_TYPE_REGISTER_HOLDING
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (Name, Register, Min, Max, Step, Unit, Scale, Icon)
VSR300_NUMBERS = [
    # Fan Speed Setpoints (Normal Mode - Percentage)
    ("Supply Fan Normal Setpoint", 1414, 20, 100, 1, "%", 1, "mdi:fan-plus"),
    ("Exhaust Fan Normal Setpoint", 1415, 20, 100, 1, "%", 1, "mdi:fan-minus"),

    # Fan Mode RPM Setpoints (Direct RPM Control)
    ("Holiday Supply Fan Setpoint", 1220, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow"),
    ("Holiday Exhaust Fan Setpoint", 1221, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow"),
    ("Cooker Hood Supply Fan Setpoint", 1222, 500, 4500, 10, "rpm", 1, "mdi:speedometer"),
    ("Cooker Hood Exhaust Fan Setpoint", 1223, 500, 4500, 10, "rpm", 1, "mdi:speedometer"),
    ("Vacuum Supply Fan Setpoint", 1224, 500, 4500, 10, "rpm", 1, "mdi:vacuum"),
    ("Vacuum Exhaust Fan Setpoint", 1225, 500, 4500, 10, "rpm", 1, "mdi:vacuum"),

    # Mode Durations (Minutes/Days)
    ("Holiday Mode Duration", 1100, 1, 365, 1, "days", 1, "mdi:airplane-takeoff"),
    ("Away Mode Duration", 1101, 1, 120, 1, "min", 1, "mdi:exit-run"),
    ("Fireplace Mode Duration", 1102, 1, 120, 1, "min", 1, "mdi:fireplace"),
    ("Refresh Mode Duration", 1103, 1, 120, 1, "min", 1, "mdi:air-filter"),
    
    # Filter Maintenance
    ("Filter Change Interval", 7000, 1, 12, 1, "mo", 1, "mdi:calendar-clock"),

    # Temperature Offsets (Scale 10)
    ("Eco Mode Offset", 2503, 0, 10, 0.5, "°C", 10, "mdi:leaf"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the VSR300 number entities."""
    hub = get_hub(hass, "VSR300")
    config = entry.data

    entities = []
    for name, register, min_val, max_val, step, unit, scale, icon in VSR300_NUMBERS:
        entities.append(
            VSR300NumberSetpoint(hub, config, name, register, min_val, max_val, step, unit, scale, icon)
        )
    async_add_entities(entities, True)

class VSR300NumberSetpoint(NumberEntity):
    def __init__(self, hub, config, name, register, min_val, max_val, step, unit, scale, icon):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._register = register
        self._scale = scale
        
        self._attr_name = name
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"vsr300_number_{self._slave}_{register}"
        self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Write the value to the Modbus register."""
        modbus_value = int(value * self._scale)
        
        result = await self._hub.async_pb_call(
            self._slave, self._register, modbus_value, CALL_TYPE_WRITE_REGISTER
        )
        
        if result:
            self._attr_native_value = value
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to write value %s to register %s", modbus_value, self._register)

    async def async_update(self):
        """Read the current value from the unit."""
        try:
            result = await self._hub.async_pb_call(
                self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING
            )
            
            if result and hasattr(result, 'registers'):
                # Divide by scale to get the human-friendly float (e.g. 25 -> 2.5)
                self._attr_native_value = result.registers[0] / self._scale
            else:
                self._attr_native_value = None
        except Exception as e:
            _LOGGER.error("Error updating number entity %s: %s", self._attr_name, e)
            self._attr_native_value = None