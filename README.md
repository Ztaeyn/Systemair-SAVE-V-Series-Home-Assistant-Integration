Systemair VSR300 python integration

Work in progress, beware.

0. Remove the old yaml package, probably deal with lots of dead entities. I cleaned them out with Spook integration.
1. Add the modbus code in configuration.yaml. See the example from "your_configuration.yaml"
2. Add integration in HACS and reboot.
3. Add as HA integration, the settings should match what is added in item 1.
4. Testing phase.

Adds as a device in HA.


See your_configuration.yaml for the only needed code manually added. (without it I had issues, seems I must provide my own modbus interface?)

<img width="1124" height="776" alt="image" src="https://github.com/user-attachments/assets/616d7609-bdff-4be0-9805-427637dd1d77" />
