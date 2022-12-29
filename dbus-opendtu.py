#!/usr/bin/env python
 
# import normal packages
import logging
import os
import platform
import sys

if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject

import configparser  # for config/ini file
import sys
import time

import requests  # for http GET

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusOpenDTUService:
  def __init__(self, servicename, paths, productname='OpenDTU', connection='OpenDTU HTTP JSON service'):
    config = self._getConfig()
    deviceinstance = int(config['DEFAULT']['Deviceinstance'])
    customname = config['DEFAULT']['CustomName']
    acposition = int(config['DEFAULT']['AcPosition'])
    
    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
    self._paths = paths
    
    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
    
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)
    
    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    #self._dbusservice.add_path('/ProductId', 16) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
    self._dbusservice.add_path('/ProductId', 0xFFFF) # id assigned by Victron Support from SDM630v2.py
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/CustomName', customname)    
    self._dbusservice.add_path('/Connected', 1)
    
    self._dbusservice.add_path('/Latency', None)    
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Position', acposition) # normaly only needed for pvinverter
    self._dbusservice.add_path('/Serial', self._getOpenDTUSerial())
    self._dbusservice.add_path('/UpdateIndex', 0)
    self._dbusservice.add_path('/StatusCode', 0)  # Dummy path so VRM detects us as a PV-inverter.
    
    # add path values to dbus
    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

    # last update
    self._lastUpdate = 0

    # add _update function 'timer'
    #gobject.timeout_add(1000, self._update) # pause 250ms before the next request
    
    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)
 
  def _getOpenDTUSerial(self):
    config = self._getConfig()
    dtu = str(config['DEFAULT']['DTU'])
    meter_data = self._getOpenDTUData()  

    #inverters = len(meter_data['inverters'])
    #logging.info("Numer of Inverter: %s" % (inverters))
    if dtu == 'ahoy':
      if not meter_data['inverter'][0]['name']:
        raise ValueError("Response does not contain name")
      serial = meter_data['inverter'][0]['name']

      #Check for ESP8266 and limit polling

      if meter_data['system']['esp_type']=='ESP8266':
        polling_interval = int(config['DEFAULT']['ESP8266PollingIntervall'])
        logging.info("ESP8266 detected, reducing polling to %s" , polling_interval)
      else:
      polling_interval = 250
      
    else:
      if not meter_data['inverters'][0]['serial']:
        raise ValueError("Response does not contain serial attribute try name")
      serial = meter_data['inverters'][0]['serial']
      polling_interval = 250
    
    gobject.timeout_add(polling_interval, self._update)

    return serial
 
 
  def _getConfig(self):
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    return config;
 
 
  def _getSignOfLifeInterval(self):
    config = self._getConfig()
    value = config['DEFAULT']['SignOfLifeLog']
    
    if not value: 
        value = 0
    return int(value)
  
  
  def _getOpenDTUStatusUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']
    dtu = str(config['DEFAULT']['DTU'])

    if accessType == 'OnPremise':
      if dtu == 'ahoy':
        URL = "http://%s/api/live" % ( config['ONPREMISE']['Host'])
      else:
        URL = "http://%s/api/livedata/status" % ( config['ONPREMISE']['Host'])
    else:
        raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))
    return URL
    
 
  def _getOpenDTUData(self):
    config = self._getConfig()
    URL = self._getOpenDTUStatusUrl()

    meter_r = requests.get(url = URL, timeout=2.50)
    
    # check for response
    if not meter_r:
      logging.info("No Response from OpenDTU/Ahoy")
      raise ConnectionError("No response from OpenDTU - %s" % (URL))
 
    meter_data = meter_r.json()     

    # check for Json
    if not meter_data:
      logging.info("Converting response to JSON failed")
      raise ValueError("Converting response to JSON failed")
    return meter_data

 
  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last _update() call: %s" % (self._lastUpdate))
    logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
    logging.info("--- End: sign of life ---")
    return True
 
  def _update(self):   
    try:
       #get data from OpenDTU
       meter_data = self._getOpenDTUData()   
       config = self._getConfig()
    
       dtu              = str(config['DEFAULT']['DTU'])
       number_of_inverters = int(config['DEFAULT']['NumberOfInverters'])

       #send data to DBus
       
       power = 0.0
       total = 0.0
       voltage = 0.0
       current = 0.0
       total_power = 0.0 
       total_yield = 0.0 
       
       for phase in ['L1', 'L2', 'L3']:
          pre = '/Ac/' + phase
          for actual_inverter in range(number_of_inverters):
            pvinverter_phase = str(config['INVERTER{}'.format(actual_inverter)]['Phase'])# Take phase of actual inverter from config
            if phase == pvinverter_phase: 
              if dtu == 'ahoy':
                power += meter_data['inverter'][actual_inverter]['ch'][0][2]
                total += meter_data['inverter'][actual_inverter]['ch'][0][6]
                voltage = meter_data['inverter'][actual_inverter]['ch'][0][0]
                current += meter_data['inverter'][actual_inverter]['ch'][0][1]
              else:
                power += meter_data['inverters'][actual_inverter]['0']['Power']['v']
                total += meter_data['inverters'][actual_inverter]['0']['YieldTotal']['v'] 
                voltage = meter_data['inverters'][actual_inverter]['0']['Voltage']['v']
                current += meter_data['inverters'][actual_inverter]['0']['Current']['v']

        #write values per Phase into dbus
          self._dbusservice[pre + '/Voltage'] = voltage
          self._dbusservice[pre + '/Current'] = current
          self._dbusservice[pre + '/Power'] = power
          if power > 0 :
            self._dbusservice[pre + '/Energy/Forward'] = total

        #carry over Total Power and Energy for Total view
          total_power += power
          total_yield += total

        #reset values for next phase
          power = 0.0
          total = 0.0
          voltage = 0.0
          current = 0.0

       if dtu == 'opendtu':
          total_power = meter_data['total']['Power']['v'] 
          total_yield = meter_data['total']['YieldTotal']['v']

       self._dbusservice['/Ac/Power'] = total_power
       if total_power > 0 :
        self._dbusservice['/Ac/Energy/Forward'] = total_yield
       
       #logging
       logging.debug("OpenDTU Power (/Ac/Power): %s" % total_power)
       logging.debug("OpenDTU Energy (/Ac/Energy/Forward): %s" % total_yield)
       logging.debug("---");
       
       # increment UpdateIndex - to show that new data is available
       index = self._dbusservice['/UpdateIndex'] + 1  # increment index
       if index > 255:   # maximum value of the index
         index = 0       # overflow from 255 to 0
       self._dbusservice['/UpdateIndex'] = index

       #update lastupdate vars
       self._lastUpdate = time.time()              
    except Exception as e:
       logging.critical('Error at %s', '_update', exc_info=e)
       
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True
 
  def _handlechangedvalue(self, path, value):
    logging.debug("someone else updated %s to %s" % (path, value))
    return True # accept the change
 


def main():
  #configure logging

  config_log = configparser.ConfigParser()
  config_log.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
  logging_level = config_log['DEFAULT']['Logging']

  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level= logging_level,
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])
 
  try:
      logging.info("Start");
  
      from dbus.mainloop.glib import DBusGMainLoop

      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)
     
      #formatting 
      _kwh = lambda p, v: (str(round(v, 2)) + 'KWh')
      _a = lambda p, v: (str(round(v, 1)) + 'A')
      _w = lambda p, v: (str(round(v, 1)) + 'W')
      _v = lambda p, v: (str(round(v, 1)) + 'V')   
     
      #start our main-service
      pvac_output = DbusOpenDTUService(
        servicename='com.victronenergy.pvinverter',
        paths={
          '/Ac/Energy/Forward': {'initial': None, 'textformat': _kwh}, # energy produced by pv inverter
          '/Ac/Power': {'initial': 0, 'textformat': _w},
          
          '/Ac/Current': {'initial': 0, 'textformat': _a},
          '/Ac/Voltage': {'initial': 0, 'textformat': _v},
          
          '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L1/Energy/Forward': {'initial': None, 'textformat': _kwh},
          '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': _kwh},
          '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': _kwh},
        })
     
      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()            
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
