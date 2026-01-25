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
    # --- Temperature & Humidity Setpoints (Scale 10 or 1) ---
    ("Supply Air Setpoint", 2000, 12, 30, 0.5, "°C", 10, "mdi:thermometer-lines"),
    ("Exhaust Air Setpoint", 2012, 12, 30, 0.5, "°C", 10, "mdi:thermometer-low"),
    ("Exhaust Air Minimum Setpoint", 2020, 10, 20, 0.5, "°C", 10, "mdi:thermometer-chevron-down"),
    ("Exhaust Air Maximum Setpoint", 2021, 20, 40, 0.5, "°C", 10, "mdi:thermometer-chevron-up"),
    ("Moisture Extraction Setpoint", 2202, 10, 90, 1, "%", 1, "mdi:water-percent"),
    ("Eco Mode Heat Offset", 2503, 0, 10, 0.5, "°C", 10, "mdi:leaf"),
    
    # --- Winter Compensation Settings ---
    ("Fan Speed Comp Read", 1254, -50, 50, 1, "%", 1, "mdi:fan-alert"),
    ("Fan Speed Comp Winter", 1251, -50, 50, 1, "%", 1, "mdi:snowflake-alert"),
    ("Winter Comp Checked Temp", 1252, -20, 20, 0.5, "°C", 10, "mdi:thermometer-check"),
    ("Winter Comp Start Temp", 1255, -20, 10, 0.5, "°C", 10, "mdi:snowflake-thermometer"),
    ("Winter Comp Max Temp", 1253, -20, 20, 0.5, "°C", 10, "mdi:thermometer-chevron-up"),

# --- Summer Compensation Settings ---
    ("Fan Speed Comp Summer", 1258, -50, 50, 1, "%", 1, "mdi:sun-angle"),
    ("Summer Comp Start Temp", 1256, 15, 40, 0.5, "°C", 10, "mdi:sun-thermometer"),
    ("Summer Comp Max Temp", 1257, 20, 50, 0.5, "°C", 10, "mdi:thermometer-chevron-up"),

    # --- System Configuration ---
    # 0: Supply, 1: Room, 2: Extract
    ("Temp Control Mode", 2030, 0, 2, 1, None, 1, "mdi:tune-vertical"),

    # --- Fan Speed Settings (RPM Based) ---
    ("Supply Fan Minimum RPM", 1410, 500, 4500, 10, "rpm", 1, "mdi:fan-minus"),
    ("Exhaust Fan Minimum RPM", 1411, 500, 4500, 10, "rpm", 1, "mdi:fan-minus"),
    ("Supply Fan Low RPM", 1302, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-1"),
    ("Exhaust Fan Low RPM", 1303, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-1"),
    ("Supply Fan Normal RPM", 1414, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-2"),
    ("Exhaust Fan Normal RPM", 1415, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-2"),
    ("Supply Fan High RPM", 1416, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-3"),
    ("Exhaust Fan High RPM", 1417, 500, 4500, 10, "rpm", 1, "mdi:fan-speed-3"),
    ("Supply Fan Maximum RPM", 1418, 500, 4500, 10, "rpm", 1, "mdi:fan-chevron-up"),
    ("Exhaust Fan Maximum RPM", 1419, 500, 4500, 10, "rpm", 1, "mdi:fan-chevron-up"),

    # --- Mode Setpoints (Direct RPM Control) ---
    ("Holiday Supply Fan Setpoint", 1220, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow"),
    ("Holiday Exhaust Fan Setpoint", 1221, 500, 3500, 10, "rpm", 1, "mdi:speedometer-slow"),
    ("Cooker Hood Supply Fan Setpoint", 1222, 500, 4500, 10, "rpm", 1, "mdi:speedometer"),
    ("Cooker Hood Exhaust Fan Setpoint", 1223, 500, 4500, 10, "rpm", 1, "mdi:speedometer"),
    ("Vacuum Supply Fan Setpoint", 1224, 500, 4500, 10, "rpm", 1, "mdi:vacuum"),
    ("Vacuum Exhaust Fan Setpoint", 1225, 500, 4500, 10, "rpm", 1, "mdi:vacuum"),

    # --- Mode Durations ---
    ("Holiday Mode Duration", 1100, 1, 365, 1, "days", 1, "mdi:airplane-takeoff"),
    ("Away Mode Duration", 1101, 1, 72, 1, "h", 1, "mdi:exit-run"),
    ("Fireplace Mode Duration", 1102, 1, 60, 1, "min", 1, "mdi:fireplace"),
    ("Refresh Mode Duration", 1103, 1, 240, 1, "min", 1, "mdi:air-filter"),
    ("Crowded Mode Duration", 1104, 1, 8, 1, "h", 1, "mdi:account-multiple-plus"),
    
    # --- Maintenance ---
    ("Filter Change Interval", 7000, 1, 12, 1, "mo", 1, "mdi:calendar-clock"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the VSR300 number entities."""
    hub = get_hub(hass, "VSR300")
    config = entry.data

    entities = [VSR300NumberSetpoint(hub, config, *s) for s in VSR300_NUMBERS]
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
        
        # Handle negative values for Modbus (Two's Complement)
        if modbus_value < 0:
            modbus_value += 65536

        result = await self._hub.async_pb_call(
            self._slave, self._register, modbus_value, CALL_TYPE_WRITE_REGISTER
        )
        if result:
            self._attr_native_value = value
            self.async_write_ha_state()

    async def async_update(self):
        """Read current value from Modbus."""
        try:
            result = await self._hub.async_pb_call(
                self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING
            )
            if result and hasattr(result, 'registers'):
                val = result.registers[0]
                # Convert back from unsigned to signed if necessary
                if val > 32767:
                    val -= 65536
                self._attr_native_value = float(val) / self._scale
            else:
                self._attr_native_value = None
        except Exception as e:
            _LOGGER.error("Update failed for %s: %s", self._attr_name, e)
            self._attr_native_value = None