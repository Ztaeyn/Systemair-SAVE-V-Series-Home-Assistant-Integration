import asyncio
import logging
from homeassistant.components.sensor import (
    SensorEntity, 
    SensorDeviceClass, 
    SensorStateClass
)
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

# List: (Name, Register, DeviceClass, Unit, Scale, Icon, StateClass)
VSR300_SENSORS = [
    # Temperature
    ("Outdoor Temperature", 12101, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),
    ("Supply Air Temperature", 12102, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),
    ("Overheat Temperature", 12107, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),      
    ("Exhaust Air Temperature", 12543, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),

    # Moisture
    ("Relative Moisture Extraction", 12135, SensorDeviceClass.HUMIDITY, "%", 1.0, None, SensorStateClass.MEASUREMENT),
    ("Calculated Moisture Extraction", 2210, SensorDeviceClass.HUMIDITY, "%", 1.0, None, SensorStateClass.MEASUREMENT),
    ("Calculated Moisture Intake", 2211, SensorDeviceClass.HUMIDITY, "%", 1.0, None, SensorStateClass.MEASUREMENT),

    # Fan Speed and RPM
    ("Supply Air Fan RPM", 12400, None, "rpm", 1.0, "mdi:speedometer", SensorStateClass.MEASUREMENT),
    ("Extractor Air Fan RPM", 12401, None, "rpm", 1.0, "mdi:speedometer", SensorStateClass.MEASUREMENT),
    ("Supply Air Fan Speed", 14000, None, "%", 1.0, "mdi:fan", SensorStateClass.MEASUREMENT),
    ("Extractor Air Fan Speed", 14001, None, "%", 1.0, "mdi:fan", SensorStateClass.MEASUREMENT),

    # Other
    ("Heat Recovery", 14102, None, "%", 1.0, "mdi:sync", SensorStateClass.MEASUREMENT),
    ("Current Fan Mode", 1160, None, None, 1.0, "mdi:air-conditioner", None),
    ("Mode Time Remaining", 1111, None, None, 1.0, "mdi:timer-sand", None), 
    ("Summer Winter Operation", 1038, None, None, 1, "mdi:sun-snowflake-variant", None),
    ("TRIAC Manual Override", 2148, None, "%", 1.0, "mdi:heating-coil", SensorStateClass.MEASUREMENT),
    ("Filter Time Remaining", 7005, None, None, 1.0, "mdi:clock-end", SensorStateClass.MEASUREMENT),
    ("Filter Alarm Code", 7006, None, None, 1.0, "mdi:alert-circle", None),
    ("Manual Fan Speed Setting", 1130, None, None, 1.0, "mdi:cog-clockwise", None),
]

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    hub = None
    for i in range(30):
        hub = get_hub(hass, "VSR300")
        if hub: break
        await asyncio.sleep(1)

    if hub is None:
        _LOGGER.error("Modbus hub 'VSR300' not found.")
        return

    entities = [VSR300GenericSensor(hub, config, *s) for s in VSR300_SENSORS]
    async_add_entities(entities, True)

class VSR300GenericSensor(SensorEntity):
    def __init__(self, hub, config, name, register, device_class, unit, scale, icon, state_class=None):
        self._hub = hub
        self._slave = config.get(CONF_SLAVE, 1)
        self._register = register
        self._scale = scale
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = state_class
        self._attr_unique_id = f"vsr300_{self._slave}_{register}"
        self._state = None

    @property
    def device_info(self):
        """Link this entity to the VSR300 Device."""
        return {
            "identifiers": {(DOMAIN, f"vsr300_{self._slave}")},
            "name": "Systemair VSR300",
            "manufacturer": "Systemair",
            "model": "SAVE VSR300",
        }

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        try:
            # --- Handle INPUT Registers (Function 04) ---
            if self._register == 1111:
                res_l = await self._hub.async_pb_call(self._slave, 1110, 1, CALL_TYPE_REGISTER_INPUT)
                res_h = await self._hub.async_pb_call(self._slave, 1111, 1, CALL_TYPE_REGISTER_INPUT)
                if res_l and res_h and hasattr(res_l, 'registers'):
                    total_seconds = (res_h.registers[0] << 16) + res_l.registers[0]
                    if total_seconds > 0:
                        h, m = total_seconds // 3600, (total_seconds % 3600) // 60
                        self._state = f"{h} h {m} min" if h > 0 else f"{m} min"
                    else:
                        self._state = "Inactive"
                return

            if self._register == 1160:
                res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
                if res_mode and hasattr(res_mode, 'registers'):
                    mode_val = res_mode.registers[0]
                    
                    # Fetch 1130 for context (Holding)
                    res_cmd = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)
                    cmd_val = res_cmd.registers[0] if res_cmd and hasattr(res_cmd, 'registers') else None

                    if mode_val == 0:  # Auto
                        auto_map = {2: "Auto - Low", 3: "Auto - Normal", 4: "Auto - High", 0: "Auto - Normal"}
                        self._state = auto_map.get(cmd_val, "Auto")
                    elif mode_val == 1:  # Manual
                        if cmd_val == 0: self._state = "Manual STOP"
                        elif cmd_val == 1: self._state = "Some error"
                        elif cmd_val == 2: self._state = "Manual Low"
                        elif cmd_val == 3: self._state = "Manual Normal"
                        elif cmd_val == 4: self._state = "Manual High"
                        else: self._state = "Manual"
                    else:
                        mode_map = {
                            2: "Crowded", 3: "Refresh", 4: "Fireplace", 5: "Away",
                            6: "Holiday", 7: "Cooker Hood", 8: "Vacuum Cleaner",
                            9: "CDI1", 10: "CDI2", 11: "CDI3", 12: "Pressure Guard"
                        }
                        self._state = mode_map.get(mode_val, "invalid state")
                return

            # --- Handle Filter Time ---
            if self._register == 7005:
                res_high = await self._hub.async_pb_call(self._slave, 7005, 1, CALL_TYPE_REGISTER_HOLDING)
                res_low = await self._hub.async_pb_call(self._slave, 7006, 1, CALL_TYPE_REGISTER_HOLDING)
                if res_high and res_low and hasattr(res_high, 'registers'):
                    total_seconds = (res_high.registers[0] << 16) + res_low.registers[0]
                    days = total_seconds / 86400
                    if days > 30:
                        self._state = round(days / 30.4, 1)
                        self._attr_native_unit_of_measurement = "mo"
                    else:
                        self._state = int(days)
                        self._attr_native_unit_of_measurement = "days"
                return

            # --- Standard Update (Holding Registers) ---
            result = await self._hub.async_pb_call(self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING)
            if result and hasattr(result, 'registers'):
                val = result.registers[0]
                if self._register == 1038: 
                    self._state = "Summer" if val == 0 else "Winter"
                elif self._register == 1130:
                    speed_map = {1: "Off", 2: "Low", 3: "Normal", 4: "High"}
                    self._state = speed_map.get(val, f"Level {val}")
                elif self._register == 7006: 
                    self._state = {0: "No Alarm", 1: "Warning", 2: "Overdue"}.get(val, val)
                else:
                    float_val = float(val)
                    if 12000 <= self._register <= 13000 and self._register not in [12400, 12401, 12135]:
                        if float_val > 32767: float_val -= 65536
                    self._state = round(float_val * self._scale, 1)
            else:
                self._state = None
        except Exception as e:
            _LOGGER.error("Update failed for %s: %s", self._attr_name, e)
            self._state = None