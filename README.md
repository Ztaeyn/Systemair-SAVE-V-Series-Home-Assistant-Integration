# Systemair VSR300 Integration for Home Assistant

## It's work in progress - But usable. I'm looking for bugs and things to improve.

## Information
I wanted to try to make the former YAML package into a integration using Python, which I want to learn for fun. I code on PLC's for work, so I can read much of the python language, but I can't write it. I've used Gemini  to help me convert my YAML code, so this is technically vibe-coding.
It's been fun, and I hope to use it as motivation to finish a python course.

## What it does
If you have not connected your VSR300 to Home Assistant before, this integration lets you control and monitor the system.
Cut short, it lets you
* Set fan modes
* Configure setpoints for duration
* Configure fan speeds
* See filter replacemnt
* See alarms



## Installation
I did not manage for now to make it install without editing files, as it seems I would have to provide the modbus interface myself. So for now you need to add the modbus interface to the configuration.yaml.

0. Prereq: HACS
1. Add the modbus configuration to your HA server. See the file "your_configuration.yaml"
2. In the HACS meny press the top right tree dot menu, and Custom Repos, and add https://github.com/Ztaeyn/HA-VSR300-modbus-python-integration as category Integration.
3. Search for Systemair VSR300 and click download.
4. Restart Home Assistant
5. Now go to Devices and add new integration and search for Systemair VSR300 and add it.
6. It should now be available as a device under Home Assistant.

Note. If you previously used the YAML package you will have to remove it first, and the resulting broken entities. I used the Spook integration for removing dead entities. Use at your own risk.


## Hardware 
I use a Elfin EW11 modbus adapter from AliExpress

<img width="1124" height="776" alt="image" src="https://github.com/user-attachments/assets/616d7609-bdff-4be0-9805-427637dd1d77" />
