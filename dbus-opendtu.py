#!/usr/bin/env python
 
# import normal packages
import logging
import os
import platform
import sys
import dbus
import time

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

def get_nested(value, path):
  for p in path:
    try:
      value = value[p]
    except:
      try: 
        value = value[int(p)]
      except:
        value = 0
  return value

def getAhoyFieldByName(meter_data, actual_inverter, fieldname):
  ac_data_field_names = meter_data['ch0_fld_names']
  data_index = ac_data_field_names.index(fieldname)
  ac_channel_index = 0
  return meter_data['inverter'][actual_inverter]['ch'][ac_channel_index][data_index]

## register every PV Inverter as registry to iterate over it
class PvInverterRegistry(type):
  def __iter__(cls):
    return iter(cls._registry)

class DbusService:
  __metaclass__ = PvInverterRegistry
  _registry = []

  def __init__(self, servicename, paths, actual_inverter, productname='OpenDTU', connection='OpenDTU HTTP JSON service'):
    config = self._getConfig()
    self._registry.append(self)

    self._readConfig(actual_inverter)
    self.numberofinverters  = self._getNumberOfInverters()
    
    logging.debug("%s /DeviceInstance = %d" % (servicename, self.deviceinstance))

    ### Allow for multiple Instance per process in DBUS
    dbusConn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus(private=True)

    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, self.deviceinstance),dbusConn)
    self._paths = paths
    
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)
    
    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', self.deviceinstance)
    #self._dbusservice.add_path('/ProductId', 16) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
    self._dbusservice.add_path('/ProductId', 0xFFFF) # id assigned by Victron Support from SDM630v2.py
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/CustomName', self._getName(self.pvinverternumber))
    self._dbusservice.add_path('/Connected', 1)
    
    self._dbusservice.add_path('/Latency', None)    
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Position', self.acposition) # normaly only needed for pvinverter
    self._dbusservice.add_path('/Serial', self._getSerial(self.pvinverternumber))
    self._dbusservice.add_path('/UpdateIndex', 0)
    self._dbusservice.add_path('/StatusCode', 0)  # Dummy path so VRM detects us as a PV-inverter.
    
    # add path values to dbus
    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

    # last update
    self._lastUpdate = 0
    
    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)
  
  ## read config file

  def _readConfig(self, actual_inverter):
    config = self._getConfig()
    self.pvinverternumber   = actual_inverter
    self.dtuvariant         = str(config['DEFAULT']['DTU'])
    self.deviceinstance     = int(config['INVERTER{}'.format(self.pvinverternumber)]['DeviceInstance'])
    self.customname         = config['DEFAULT']['CustomName']
    try: 
      self.acposition         = int(config['INVERTER{}'.format(self.pvinverternumber)]['AcPosition'])
    except:
      self.acposition         = int(config['DEFAULT']['AcPosition'])
      logging.error("Deprecated AcPosition DEFAULT entries must be moved to INVERTER section")
    self.signofliveinterval = config['DEFAULT']['SignOfLifeLog']
    #self.numberofinverters  = self._getNumberOfInverters()
    #self.numberofinverters  = int(config['DEFAULT']['NumberOfInverters'])
    self.useyieldday        = int(config['DEFAULT']['useYieldDay'])
    self.pvinverterphase    = str(config['INVERTER{}'.format(self.pvinverternumber)]['Phase'])
    try:
      self.host               = config['DEFAULT']['Host']
    except:
      logging.error("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
      self.host               = config['ONPREMISE']['Host']
    try:  
      self.username           = config['DEFAULT']['Username']
    except:
      logging.error("Deprecated Username ONPREMISE entries must be moved to DEFAULT section")
      self.username           = config['ONPREMISE']['Username']
    try:
      self.password           = config['DEFAULT']['Password']
    except:
      logging.error("Deprecated: Password ONPREMISE entries must be moved to DEFAULT section")
      self.password           = config['ONPREMISE']['Password']
    
    self.pollinginterval    = int(config['DEFAULT']['ESP8266PollingIntervall'])

    if self.dtuvariant == "template":
      self.custpower          = config['TEMPLATE']['CUST_Power'].split("/")
      self.custpower_factor   = config['TEMPLATE']['CUST_Power_Mult']
      self.custtotal          = config['TEMPLATE']['CUST_Total'].split("/")
      self.custtotal_factor   = config['TEMPLATE']['CUST_Total_Mult']
      self.custvoltage        = config['TEMPLATE']['CUST_Voltage'].split("/")
      self.custcurrent        = config['TEMPLATE']['CUST_Current'].split("/")
      self.custapipath        = config['TEMPLATE']['CUST_API_PATH']
      self.serial             = str(config['TEMPLATE']['CUST_SN'])
      self.pollinginterval    = int(config['TEMPLATE']['CUST_POLLING'])

  ## get the Serialnumber
  def _getSerial(self, pvinverternumber):
  
    meter_data = self._getData() 

    if self.dtuvariant == 'ahoy':
      if not meter_data['inverter'][pvinverternumber]['name']:
        raise ValueError("Response does not contain name")
      serial = meter_data['inverter'][pvinverternumber]['name']
      
    elif self.dtuvariant =='opendtu':
      if not meter_data['inverters'][pvinverternumber]['serial']:
        raise ValueError("Response does not contain serial attribute try name")
      serial = meter_data['inverters'][pvinverternumber]['serial']

    elif self.dtuvariant =='template':
      serial = self.serial

    gobject.timeout_add(self._getPollingInterval(), self._update)

    return serial

  def _getName(self, pvinverternumber):
    meter_data = self._getData()
    if self.dtuvariant == 'ahoy':
      name = meter_data['inverter'][pvinverternumber]['name']
    elif self.dtuvariant == 'opendtu':
      name = meter_data['inverters'][pvinverternumber]['name']
    else:
      name = self.customname
    logging.info("Name of Inverters found: %s" % (name))
    return name

  def _getNumberOfInverters(self):
    meter_data = self._getData()
    if self.dtuvariant == 'ahoy':
      numberofinverters = len(meter_data['inverter'])
    elif self.dtuvariant == 'opendtu':
      numberofinverters = len(meter_data['inverters'])
    else:
      numberofinverters = 1
    logging.info("Number of Inverters found: %s" % (numberofinverters))
    return numberofinverters

  def _getPollingInterval(self):
    meter_data = self._getData()
    if self.dtuvariant == 'ahoy':
      #Check for ESP8266 and limit polling
      try:
        self.esptype = meter_data['generic']['esp_type']
      except:
        self.esptype = meter_data['system']['esp_type']

      if self.esptype=='ESP8266':
        polling_interval = self.pollinginterval
        logging.info("ESP8266 detected, reducing polling to %s" , polling_interval)
      else:
       polling_interval = 5000
      
    elif self.dtuvariant =='opendtu':
      polling_interval = 5000
    
    elif self.dtuvariant =='template':
      serial = self.serial
      polling_interval = self.pollinginterval
    return polling_interval

  def _getConfig(self):
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    return config;
  
  def _getSignOfLifeInterval(self):
    value = self.signofliveinterval
    
    if not value: 
        value = 0
    return int(value)
  
  def _getStatusUrl(self):
    if self.dtuvariant == 'opendtu':
      URL = "http://%s/api/livedata/status" % ( self.host)
    elif self.dtuvariant == 'ahoy':
      URL = "http://%s/api/live" % ( self.host)
    elif self.dtuvariant == 'template':
      URL = "http://%s:%s@%s/%s" % ( self.username, self.password, self.host, self.custapipath)
      URL = URL.replace(":@", "")
    return URL
  
  def _refreshData(self):
    meter_r = requests.get(url = self._getStatusUrl(), timeout=2.50)
    
    # check for response
    if not meter_r:
      logging.info("No Response from OpenDTU/Ahoy")
      raise ConnectionError("No response from OpenDTU - %s" % (URL))
 
    meter_data = meter_r.json()     

    # check for Json
    if not meter_data:
      logging.info("Converting response to JSON failed")
      raise ValueError("Converting response to JSON failed")

    # store valid data for later use
    self.meter_data = meter_data

  def _getData(self):
    if not self.meter_data:
      self._refreshData()
    return self.meter_data

  def _isDataUpToDate(self, actual_inverter):
    if self.dtuvariant == 'ahoy':
      ts_last_success = self.meter_data['inverter'][actual_inverter]['ts_last_success']
      age_seconds = time.time() - ts_last_success
      return age_seconds < 10*60
    else:
      # anything to do for other DTUs?
      return True

  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last _update() call: %s" % (self._lastUpdate))
    logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
    logging.info("--- End: sign of life ---")
    return True
 
  def _update(self):   
    try:
      # update data from DTU once per _update call:
      self._refreshData()   
       
      pre = '/Ac/' + self.pvinverter_phase
      if self._isDataUpToDate(self.pvinverternumber):
        (power, pvyield, current, voltage) = self.get_values_for_phase(self.pvinverternumber)

        self._dbusservice[pre + '/Voltage'] = voltage
        self._dbusservice[pre + '/Current'] = current
        self._dbusservice[pre + '/Power'] = power
        self._dbusservice['/Ac/Power'] = power
        if power > 0:
          self._dbusservice[pre + '/Energy/Forward'] = pvyield
          self._dbusservice['/Ac/Energy/Forward'] = pvyield
       
      logging.debug("OpenDTU Power (/Ac/Power): %s" % power)
      logging.debug("OpenDTU Energy (/Ac/Energy/Forward): %s" % pvyield)
      logging.debug("---");
      
      self._update_index()
      self._lastUpdate = time.time()              
    except Exception as e:
       logging.critical('Error at %s', '_update', exc_info=e)
       
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True

  def _update_index(self):
    # increment UpdateIndex - to show that new data is available
    index = self._dbusservice['/UpdateIndex'] + 1  # increment index
    if index > 255:   # maximum value of the index
      index = 0       # overflow from 255 to 0
    self._dbusservice['/UpdateIndex'] = index

  def get_values_for_phase(self, actual_inverter):
    meter_data = self._getData()
    (power, pvyield, current, voltage) = (None, None, None, None)
    if self.dtuvariant == 'ahoy':
      power = getAhoyFieldByName(meter_data, actual_inverter, 'P_AC')
      if self.useyieldday:
        pvyield = getAhoyFieldByName(meter_data, actual_inverter, 'YieldDay') / 1000
      else:
        pvyield = getAhoyFieldByName(meter_data, actual_inverter, 'YieldTotal')
      voltage = getAhoyFieldByName(meter_data, actual_inverter, 'U_AC')
      current = getAhoyFieldByName(meter_data, actual_inverter, 'I_AC')
    elif self.dtuvariant == 'opendtu':
      power = meter_data['inverters'][actual_inverter]['0']['Power']['v']
      if self.useyieldday:
        pvyield = meter_data['inverters'][actual_inverter]['0']['YieldDay']['v'] / 1000
      else:
        pvyield = meter_data['inverters'][actual_inverter]['0']['YieldTotal']['v']
      voltage = meter_data['inverters'][actual_inverter]['0']['Voltage']['v']
      current = meter_data['inverters'][actual_inverter]['0']['Current']['v']
    elif self.dtuvariant == 'template':
              #logging.debug("JSON data: %s" % meter_data)
      power = float(get_nested( meter_data, self.custpower) * float(self.custpower_factor))
      pvyield = float(get_nested( meter_data, self.custtotal) * float(self.custtotal_factor))
      voltage = float(get_nested( meter_data, self.custvoltage))
      current = float(get_nested( meter_data, self.custcurrent))
    return (power, pvyield, current, voltage)
 
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
     
      paths ={
            '/Ac/Energy/Forward': {'initial': None, 'textformat': _kwh}, # energy produced by pv inverter
            '/Ac/Power': {'initial': None, 'textformat': _w},        
            '/Ac/L1/Voltage': {'initial': None, 'textformat': _v},
            '/Ac/L2/Voltage': {'initial': None, 'textformat': _v},
            '/Ac/L3/Voltage': {'initial': None, 'textformat': _v},
            '/Ac/L1/Current': {'initial': None, 'textformat': _a},
            '/Ac/L2/Current': {'initial': None, 'textformat': _a},
            '/Ac/L3/Current': {'initial': None, 'textformat': _a},
            '/Ac/L1/Power': {'initial': None, 'textformat': _w},
            '/Ac/L2/Power': {'initial': None, 'textformat': _w},
            '/Ac/L3/Power': {'initial': None, 'textformat': _w},
            '/Ac/L1/Energy/Forward': {'initial': None, 'textformat': _kwh},
            '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': _kwh},
            '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': _kwh},
          }

      service = DbusService(
          servicename='com.victronenergy.pvinverter',
          paths=paths,
          actual_inverter=0) 

      number_of_inverters = service._getNumberOfInverters()

      if number_of_inverters > 1:
        #start our main-service if there are more than 1 inverter
        for actual_inverter in range(number_of_inverters -1):
          DbusService(
            servicename='com.victronenergy.pvinverter',
            paths=paths,
            actual_inverter=actual_inverter+1)
     
      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()            
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
