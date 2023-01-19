# dbus-opendtu/ahoydtu inverter
Integrate openDTU or ahoyDTU and with that all Hoymiles Interverter https://github.com/tbnobody/OpenDTU into Victron Energies Venus OS. This also allows for template configuration to include other generic REST Devices. 

Tested Examples:

    * Tasmota unauthenticated
    * Shelly 1 PM authenticated/unauthenticated
    * Shelly Plus 1 PM unathenticated

All configuration is done via config.ini examples are commented in config.ini

## Purpose
With the scripts in this repo it should be easy possible to install, uninstall, restart a service that connects the opendtu to the VenusOS and GX devices from Victron.
Idea is inspired on @fabian-lauer & @vikt0rm project linked below.



## Inspiration
This project is my first on GitHub and with the Victron Venus OS, so I took some ideas and approaches from the following projects - many thanks for sharing the knowledge:
- https://github.com/fabian-lauer/dbus-shelly-3em-smartmeter
- https://shelly-api-docs.shelly.cloud/gen1/#shelly1-shelly1pm
- https://github.com/victronenergy/venus/wiki/dbus#pv-inverters
- https://github.com/vikt0rm/dbus-shelly-1pm-pvinverter
- https://github.com/tbnobody/OpenDTU 
- https://github.com/tbnobody/OpenDTU/blob/master/docs/Web-API.md
- https://ahoydtu.de/


## How it works


### Details / Process
As mentioned above the script is inspired by @fabian-lauer dbus-shelly-3em-smartmeter implementation.
So what is the script doing:
- Running as a service
- connecting to DBus of the Venus OS `com.victronenergy.pvinverter.http_{DeviceInstanceID_from_config}`
- After successful DBus connection OpenDTU/ahoyDTU is accessed via REST-API - simply the /status is called and a JSON is returned with all details
  A sample JSON file from OpenDTU can be found [here](docs/OpenDTU.json). A sample JSON file from OpenDTU can be found [here](docs/ahoy.json)
- Serial/devicename is taken from the response as device serial
- Paths are added to the DBus with default value 0 - including some settings like name, etc
- After that a "loop" is started which pulls OpenDTU/AhoyDTU data every 5s from the REST-API and updates the values in the DBus, for ESP 8266 based ahoy systems we even pull data only every 10seconds

Thats it 😄

### Pictures
<img src="img/overview.png" width="400" /> <img src="img/devicelist.png" width="400" />
<img src="img/device.png" width="400" /> <img src="img/devicedetails.png" width="400" />

## Install & Configuration
### Get the code
Just grap a copy of the main branche and copy them to a folder under `/data/` e.g. `/data/dbus-opendtu`.
After that call the install.sh script.

The following script should do everything for you:
```
wget https://github.com/henne49/dbus-opendtu/archive/refs/heads/main.zip
unzip main.zip "dbus-opendtu-main/*" -d /data
mv /data/dbus-opendtu-main /data/dbus-opendtu
chmod a+x /data/dbus-opendtu/install.sh
nano /data/dbus-opendtu/config.ini
```

⚠️Edit and change the config file to your needs and save⚠️

```
/data/dbus-opendtu/install.sh
rm main.zip
```
⚠️ Check configuration after that - because service is already installed an running and with wrong connection data (host, username, pwd) you will spam the log-file, also check to set right ⚠️minimal log level⚠️ as possible

### Change config.ini
Within the project there is a file `/data/dbus-opendtu/config.ini` - just change the values - most important is the deviceinstance, custom name and phase under "DEFAULT" and host, username and password in section "ONPREMISE". More details below:

| Section  | Config vlaue | Explanation |
| ------------- | ------------- | ------------- |
| DEFAULT  | AccessType | Fixed value 'OnPremise' |
| DEFAULT  | SignOfLifeLog  | Time in minutes how often a status is added to the log-file `current.log` with log-level INFO |
| DEFAULT  | Deviceinstance | Unique ID identifying the OpenDTU in Venus OS |
| DEFAULT  | CustomName | Name shown in Remote Console (e.g. name of pv inverter) |
| DEFAULT  | AcPosition | Position shown in Remote Console (0=AC input 1; 1=AC output; 2=AC input 2) |
| DEFAULT  | NumberOfInverters | How Many inverters to check, up 10 for ahoy and opendtu, template can only monitor 1 device |
| DEFAULT  | DTU |  Which DTU to be used ahoy, opendtu or template REST devices Valid options: opendtu, ahoy, template |
| DEFAULT  | useYieldDay | send YieldDay instead of YieldTotal. Set this to 1 to prevent VRM from adding the total value to the history on one day. E.g. if you don't start using the inverter at 0. |
| DEFAULT  | ESP8266PollingIntervall |  For ESP8266 reduce polling intervall to reduce load, default 10000ms|
| DEFAULT  | Logging | Valid options for log level: CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET, to keep logfile small use ERROR or CRITICAL |
| DEFAULT | MagAgeTsLastSuccess | Maximum accepted age of ts_last_success in Ahoy status message. If ts_last_success is older than this number of seconds, values are not used.  Set this to < 0 to disable this check.                                    |
| DEFAULT  | DryRun | Set this to a value different to "0" to prevent values from being sent. Use this for debugging or experiments. |
| ONPREMISE  | Host | IP or hostname of OpenDTU web-interface |
| ONPREMISE  | Username | use for template device, if authenticaed, leave empty if no authentication needed |
| ONPREMISE  | Password | use for template device, if authenticaed, leave empty if no authentication needed |
| INVERTER0  | Phase | 1st Inverter added to which Phase L1, L2, L3|
| INVERTER1  | Phase | 2nd Inverter added to which Phase L1, L2, L3|
| .........  |       | ........... |
| INVERTER9  | Phase | 3rd Inverter added to which Phase L1, L2, L3|
| TEMPLATE  | CUST_SN | Serialnumber to register device in VenusOS|
| TEMPLATE  | CUST_API_PATH | Location of REST API Path for JSON to be used |
| TEMPLATE  | CUST_POLLING | Polling for Device |
| TEMPLATE  | CUST_Total | Path in JSON where to find total Energy |
| TEMPLATE  | CUST_Total_Mult | Multiplier to convert W per minute for example in kWh|
| TEMPLATE  | CUST_Power | Path in JSON where to find actual Power |
| TEMPLATE  | CUST_Power_Mult | Multiplier to convert W in negative or positive |
| TEMPLATE  | CUST_Voltage | Path in JSON where to find actual Voltage |
| TEMPLATE  | CUST_Current | Path in JSON where to find actual Current |

Example for JSON PATH: use keywords separated by /

## Used documentation
- https://github.com/victronenergy/venus/wiki/dbus#pv-inverters   DBus paths for Victron namespace
- https://github.com/victronenergy/venus/wiki/dbus-api   DBus API from Victron
- https://www.victronenergy.com/live/ccgx:root_access   How to get root access on GX device/Venus OS
- https://github.com/tbnobody/OpenDTU/blob/master/docs/Web-API.md

## Discussions on the web
This module/repository has been posted on the following threads:
- https://community.victronenergy.com/questions/169076/opendtu-as-pv-inverter-in-venusos.html

## Video on how to install and use:
- https://youtu.be/PpjCz33pGkk Meine Energiewende
- https://youtu.be/UNuIOa72eP4 Schatten PV
