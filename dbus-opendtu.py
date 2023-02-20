#!/usr/bin/env python
 
import logging
import os
import platform
import sys
import dbus
import time
import json

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

def isTrue(val):
  return val == 1 or val == '1' or val == True

## register every PV Inverter as registry to iterate over it
class PvInverterRegistry(type):
  def __iter__(cls):
    return iter(cls._registry)

class DbusService:
  __metaclass__ = PvInverterRegistry
  _registry = []
  _meter_data = None
  _test_meter_data = None

  def __init__(self, servicename, paths, actual_inverter, productname='OpenDTU', connection='OpenDTU HTTP JSON service', istemplate=False):

    if servicename == 'testing':
      self.max_age_ts = 600
      self.pvinverternumber = actual_inverter
      self.useyieldday = False
      return

    self._registry.append(self)

    self._lastUpdate = 0
    
    if not istemplate:
      self._readConfigDTU(actual_inverter)
      self.numberofinverters  = self._getNumberOfInverters()
    else:
      self._readConfigTemplate(actual_inverter)
    
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

    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)
  
  ## read config file

  def _readConfigDTU(self, actual_inverter):
    config = self._getConfig()
    self.pvinverternumber   = actual_inverter
    self.dtuvariant         = str(config['DEFAULT']['DTU'])
    self.deviceinstance     = int(config['INVERTER{}'.format(self.pvinverternumber)]['DeviceInstance'])
    try: 
      self.acposition         = int(config['INVERTER{}'.format(self.pvinverternumber)]['AcPosition'])
    except:
      logging.error("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
      raise ValueError("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
    self.signofliveinterval = config['DEFAULT']['SignOfLifeLog']
    self.useyieldday        = int(config['DEFAULT']['useYieldDay'])
    self.pvinverterphase    = str(config['INVERTER{}'.format(self.pvinverternumber)]['Phase'])
    try:
      self.host               = config['DEFAULT']['Host']
    except:
      logging.error("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
      raise ValueError("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
    try:  
      self.username           = config['DEFAULT']['Username']
    except:
      logging.error("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
      raise ValueError("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
    try:
      self.password           = config['DEFAULT']['Password']
    except:
      logging.error("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
      raise ValueError("Deprecated Host ONPREMISE entries must be moved to DEFAULT section")
    try:
      self.max_age_ts         = int(config['DEFAULT']['MagAgeTsLastSuccess'])
    except:
      self.max_age_ts         = 600

    try:
      self.dry_run            = "0" != config['DEFAULT']['DryRun']
    except:
      self.dry_run            = False

    self.pollinginterval    = int(config['DEFAULT']['ESP8266PollingIntervall'])
    self.meter_data         = 0

  def _readConfigTemplate(self, template_number):
      config = self._getConfig()
      self.pvinverternumber   = template_number
      self.custpower          = config['TEMPLATE{}'.format(template_number)]['CUST_Power'].split("/")
      self.custpower_factor   = config['TEMPLATE{}'.format(template_number)]['CUST_Power_Mult']
      self.custtotal          = config['TEMPLATE{}'.format(template_number)]['CUST_Total'].split("/")
      self.custtotal_factor   = config['TEMPLATE{}'.format(template_number)]['CUST_Total_Mult']
      self.custvoltage        = config['TEMPLATE{}'.format(template_number)]['CUST_Voltage'].split("/")
      self.custcurrent        = config['TEMPLATE{}'.format(template_number)]['CUST_Current'].split("/")
      self.custapipath        = config['TEMPLATE{}'.format(template_number)]['CUST_API_PATH']
      self.serial             = str(config['TEMPLATE{}'.format(template_number)]['CUST_SN'])
      self.pollinginterval    = int(config['TEMPLATE{}'.format(template_number)]['CUST_POLLING'])
      self.host               = config['TEMPLATE{}'.format(template_number)]['Host']
      self.username           = config['TEMPLATE{}'.format(template_number)]['Username']
      self.password           = config['TEMPLATE{}'.format(template_number)]['Password']
      self.dtuvariant         = "template"
      self.deviceinstance     = int(config['TEMPLATE{}'.format(template_number)]['DeviceInstance'])
      self.customname         = config['TEMPLATE{}'.format(template_number)]['Name']
      self.acposition         = int(config['TEMPLATE{}'.format(template_number)]['AcPosition'])
      self.signofliveinterval = config['DEFAULT']['SignOfLifeLog']
      self.useyieldday        = int(config['DEFAULT']['useYieldDay'])
      self.pvinverterphase    = str(config['TEMPLATE{}'.format(template_number)]['Phase'])
      try:
        self.max_age_ts         = int(config['DEFAULT']['MagAgeTsLastSuccess'])
      except:
        self.max_age_ts         = 600

      try:
        self.dry_run            = "0" != config['DEFAULT']['DryRun']
      except:
        self.dry_run            = False
      self.meter_data           = 0 

  ## get the Serialnumber
  def _getSerial(self, pvinverternumber):
    
    if self.dtuvariant == 'ahoy' or self.dtuvariant == 'opendtu' :
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
    if self.dtuvariant == 'ahoy' or self.dtuvariant == 'opendtu' :
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

  def _getNumberOfTemplates(self):
    return self.numberoftemplates

  def _getDtuVariant(self):
    return self.dtuvariant

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
      URL = "http://%s:%s@%s/api/livedata/status" % ( self.username, self.password, self.host)
      URL = URL.replace(":@", "")
    elif self.dtuvariant == 'ahoy':
      URL = "http://%s/api/live" % ( self.host)
    elif self.dtuvariant == 'template':
      URL = "http://%s:%s@%s/%s" % ( self.username, self.password, self.host, self.custapipath)
      URL = URL.replace(":@", "")
    return URL

  def _refreshData(self):
    
    if self.pvinverternumber != 0 and self.dtuvariant != 'template':
      # only fetch new data when called for inverter 0 (background: data is kept at class level for all inverters)
      return

    url = self._getStatusUrl()
    meter_r = requests.get(url = url, timeout=2.50)
    
    # check for response
    if not meter_r:
      logging.info("No Response from OpenDTU/Ahoy")
      raise ConnectionError("No response from OpenDTU - %s" % (url))
 
    meter_data = meter_r.json()

    # check for Json
    if not meter_data:
      logging.info("Converting response to JSON failed")
      raise ValueError("Converting response to JSON failed")

    if self.dtuvariant == 'opendtu':
      if not 'AC' in meter_data['inverters'][self.pvinverternumber]:
        logging.info("You do not have the latest OpenDTU Version to run this script, please upgrade your OpenDTU to at least version 4.4.3")
        raise ValueError("You do not have the latest OpenDTU Version to run this script, please upgrade your OpenDTU to at least version 4.4.3")

    # store valid data for later use
    if self.dtuvariant == 'template':
      self.meter_data = meter_data
    else:
      DbusService._meter_data = meter_data

  def _getData(self):
    if self._test_meter_data:
      return self._test_meter_data
    if not DbusService._meter_data:
      self._refreshData()
    
    if self.dtuvariant == 'template': 
      return self.meter_data
    else:
      return DbusService._meter_data
    
  
  def setTestData(self, test_data):
    self._test_meter_data = test_data

  def setDTUVariant(self, dtuvariant):
    self.dtuvariant = dtuvariant

  def _isDataUpToDate(self):
    if self.max_age_ts < 0:
      # check is disabled by config
      return True
    meter_data = self._getData()

    if self.dtuvariant == 'ahoy':
      ts_last_success = meter_data['inverter'][self.pvinverternumber]['ts_last_success']
      age_seconds = time.time() - ts_last_success
      logging.debug("_isDataUpToDate: inverter #%d: age_seconds=%d, max_age_ts=%d" % (self.pvinverternumber, age_seconds, self.max_age_ts))
      return age_seconds >= 0 and age_seconds < self.max_age_ts

    elif self.dtuvariant == 'opendtu':
      return isTrue(meter_data['inverters'][self.pvinverternumber]['reachable'])

    else:
      # TODO: anything for other DTUs?
      return True

  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last inverter #%d _update() call: %s" % (self.pvinverternumber, self._lastUpdate))
    logging.info("Last inverter #%d '/Ac/Power': %s" % (self.pvinverternumber, self._dbusservice['/Ac/Power']))
    logging.info("--- End: sign of life ---")
    return True
 
  def _update(self):   
    try:
      # update data from DTU once per _update call:
      self._refreshData()   
       
      pre = '/Ac/' + self.pvinverterphase

      if self._isDataUpToDate():
        (power, pvyield, current, voltage) = self.get_values_for_inverter()

        if self.dry_run:
          logging.warn("DRY RUN. No data is sent!!")    
        else:
          self._dbusservice[pre + '/Voltage'] = voltage
          self._dbusservice[pre + '/Current'] = current
          self._dbusservice[pre + '/Power'] = power
          self._dbusservice['/Ac/Power'] = power
          if power > 0:
            self._dbusservice[pre + '/Energy/Forward'] = pvyield
            self._dbusservice['/Ac/Energy/Forward'] = pvyield
       
        logging.debug("Inverter #%d Power (/Ac/Power): %s" % (self.pvinverternumber, power))
        logging.debug("Inverter #%d Energy (/Ac/Energy/Forward): %s" % (self.pvinverternumber, pvyield))
        logging.debug("---")
      
      self._update_index()
    except Exception as e:
       logging.critical('Error at %s', '_update', exc_info=e)
       
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True

  def _update_index(self):
    if self.dry_run:
      return
    # increment UpdateIndex - to show that new data is available
    index = self._dbusservice['/UpdateIndex'] + 1  # increment index
    if index > 255:   # maximum value of the index
      index = 0       # overflow from 255 to 0
    self._dbusservice['/UpdateIndex'] = index
    self._lastUpdate = time.time()

  def get_values_for_inverter(self):

    meter_data = self._getData()
    (power, pvyield, current, voltage) = (None, None, None, None)

    if self.dtuvariant == 'ahoy':
      power = getAhoyFieldByName(meter_data, self.pvinverternumber, 'P_AC')
      if self.useyieldday:
        pvyield = getAhoyFieldByName(meter_data, self.pvinverternumber, 'YieldDay') / 1000
      else:
        pvyield = getAhoyFieldByName(meter_data, self.pvinverternumber, 'YieldTotal')
      voltage = getAhoyFieldByName(meter_data, self.pvinverternumber, 'U_AC')
      current = getAhoyFieldByName(meter_data, self.pvinverternumber, 'I_AC')

    elif self.dtuvariant == 'opendtu':
      producing = isTrue(meter_data['inverters'][self.pvinverternumber]['producing'])
      power = meter_data['inverters'][self.pvinverternumber]['AC']['0']['Power']['v'] if producing else 0
      if self.useyieldday:
        pvyield = meter_data['inverters'][self.pvinverternumber]['AC']['0']['YieldDay']['v'] / 1000
      else:
        pvyield = meter_data['inverters'][self.pvinverternumber]['AC']['0']['YieldTotal']['v']
      voltage = meter_data['inverters'][self.pvinverternumber]['AC']['0']['Voltage']['v']
      current = meter_data['inverters'][self.pvinverternumber]['AC']['0']['Current']['v'] if producing else 0

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
  config= configparser.ConfigParser()
  config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
  logging_level = config['DEFAULT']['Logging']
  dtuvariant=config['DEFAULT']['DTU']

  try: 
    number_of_templates=int(config['DEFAULT']['NumberOfTemplates'])
  except:
    number_of_templates = 0


  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level= logging_level,
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])
 
  run_tests()

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
      
      if dtuvariant != 'template':
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

      for actual_template in range(number_of_templates):
        logging.info('Registering Templates')
        service = DbusService(
            servicename='com.victronenergy.pvinverter',
            paths=paths,
            actual_inverter=actual_template,
            istemplate=True) 


      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()            
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)

opendtu_test_data_str = '{"inverters":[{"serial":"112181311701","name":"Holzpalast Süd","data_age":11559,"reachable":false,"producing":false,"limit_relative":100,"limit_absolute":350,"0":{"Power":{"v":1,"u":"W"},"Voltage":{"v":235.1999969,"u":"V"},"Current":{"v":1,"u":"A"},"Power DC":{"v":1.200000048,"u":"W"},"YieldDay":{"v":482,"u":"Wh"},"YieldTotal":{"v":111.3209991,"u":"kWh"},"Frequency":{"v":49.99000168,"u":"Hz"},"Temperature":{"v":21.60000038,"u":"°C"},"PowerFactor":{"v":0,"u":"%"},"ReactivePower":{"v":0,"u":"var"},"Efficiency":{"v":0,"u":"%"}},"1":{"Power":{"v":1.200000048,"u":"W"},"Voltage":{"v":24.10000038,"u":"V"},"Current":{"v":0.050000001,"u":"A"},"YieldDay":{"v":482,"u":"Wh"},"YieldTotal":{"v":111.3209991,"u":"kWh"},"Irradiation":{"v":0.292682916,"u":"%"}},"events":3},{"serial":"112180719948","name":"Holzpalast Ost Links","data_age":11678,"reachable":false,"producing":false,"limit_relative":100,"limit_absolute":300,"0":{"Power":{"v":0,"u":"W"},"Voltage":{"v":235.6000061,"u":"V"},"Current":{"v":0,"u":"A"},"Power DC":{"v":1,"u":"W"},"YieldDay":{"v":351,"u":"Wh"},"YieldTotal":{"v":0.843999982,"u":"kWh"},"Frequency":{"v":49.97000122,"u":"Hz"},"Temperature":{"v":21.70000076,"u":"°C"},"PowerFactor":{"v":0,"u":"%"},"ReactivePower":{"v":0,"u":"var"},"Efficiency":{"v":0,"u":"%"}},"1":{"Power":{"v":1,"u":"W"},"Voltage":{"v":19.70000076,"u":"V"},"Current":{"v":0.050000001,"u":"A"},"YieldDay":{"v":351,"u":"Wh"},"YieldTotal":{"v":0.843999982,"u":"kWh"},"Irradiation":{"v":0.289855093,"u":"%"}},"events":3},{"serial":"114181304338","name":"Mülltonnen","data_age":11377,"reachable":false,"producing":false,"limit_relative":100,"limit_absolute":600,"0":{"Power":{"v":0,"u":"W"},"Voltage":{"v":234.5,"u":"V"},"Current":{"v":0,"u":"A"},"Power DC":{"v":0.700000048,"u":"W"},"YieldDay":{"v":828,"u":"Wh"},"YieldTotal":{"v":5.251999855,"u":"kWh"},"Frequency":{"v":49.99000168,"u":"Hz"},"Temperature":{"v":22.39999962,"u":"°C"},"PowerFactor":{"v":0,"u":"%"},"ReactivePower":{"v":0,"u":"var"},"Efficiency":{"v":0,"u":"%"}},"1":{"Power":{"v":0.300000012,"u":"W"},"Voltage":{"v":18.60000038,"u":"V"},"Current":{"v":0.02,"u":"A"},"YieldDay":{"v":398,"u":"Wh"},"YieldTotal":{"v":2.50999999,"u":"kWh"},"Irradiation":{"v":0.086956523,"u":"%"}},"2":{"Power":{"v":0.400000006,"u":"W"},"Voltage":{"v":18.60000038,"u":"V"},"Current":{"v":0.02,"u":"A"},"YieldDay":{"v":430,"u":"Wh"},"YieldTotal":{"v":2.742000103,"u":"kWh"},"Irradiation":{"v":0.115942039,"u":"%"}},"events":3}]}'
ahoy_test_data_str = '{"menu":{"name":["Live","Serial / Control","Settings","-","REST API","-","Update","System","-","Documentation"],"link":["/live","/serial","/setup",null,"/api",null,"/update","/system",null,"https://ahoydtu.de"],"trgt":[null,null,null,null,"_blank",null,null,null,null,"_blank"]},"generic":{"version":"0.5.70","build":"d8e255d","wifi_rssi":-72,"ts_uptime":1602,"esp_type":"ESP8266"},"inverter":[{"enabled":true,"name":"hoymiles1","channels":1,"power_limit_read":100,"last_alarm":"Inverter start","ts_last_success":1675243378,"ch":[[234.9,0.1,22.5,50.04,1,7.5,96.802,16,23.6,95.339,0],[33,0.71,23.6,16,96.802,6.743]],"ch_names":["AC","einzel"]},{"enabled":true,"name":"hoymiles2","channels":4,"power_limit_read":100,"last_alarm":"Inverter start","ts_last_success":1675243373,"ch":[[234.4,0.37,87.2,50.03,0.971,5.8,11.338,68,91.7,95.093,21.5],[34,0.76,26,19,3.554,6.933],[34,0.01,0.5,0,0.071,0],[33.8,0.95,32.1,24,3.581,8.56],[33.8,0.98,33.1,25,4.132,8.827]],"ch_names":["AC","M1","no","M3","M4"]}],"refresh_interval":5,"ch0_fld_units":["V","A","W","Hz","","°C","kWh","Wh","W","%","var"],"ch0_fld_names":["U_AC","I_AC","P_AC","F_AC","PF_AC","Temp","YieldTotal","YieldDay","P_DC","Efficiency","Q_AC"],"fld_units":["V","A","W","Wh","kWh","%"],"fld_names":["U_DC","I_DC","P_DC","YieldDay","YieldTotal","Irradiation"]}'

def test_opendtu_reachable(test_service):
  test_service.setDTUVariant('opendtu')
  test_data = json.loads(opendtu_test_data_str)

  test_service.setTestData(test_data)
  assert test_service._isDataUpToDate() == False

  test_data = json.loads(opendtu_test_data_str.replace('"reachable":false', '"reachable":"1"'))
  test_service.setTestData(test_data)
  assert test_service._isDataUpToDate() == True

  test_data = json.loads(opendtu_test_data_str.replace('"reachable":false', '"reachable":1'))
  test_service.setTestData(test_data)
  assert test_service._isDataUpToDate() == True

  test_data = json.loads(opendtu_test_data_str.replace('"reachable":false', '"reachable":true'))
  test_service.setTestData(test_data)
  assert test_service._isDataUpToDate() == True

  test_data = json.loads(opendtu_test_data_str.replace('"reachable":false', '"reachable":false'))
  test_service.setTestData(test_data)
  assert test_service._isDataUpToDate() == False

def test_opendtu_producing(test_service):
  test_service.setDTUVariant('opendtu')
  test_data = json.loads(opendtu_test_data_str)

  test_service.setTestData(test_data)
  # current, power are 0 because inverter is not producing
  assert test_service.get_values_for_inverter() == (0, 111.3209991, 0, 235.1999969)

  test_data = json.loads(opendtu_test_data_str.replace('"producing":false', '"producing":"1"'))
  test_service.setTestData(test_data)
  assert test_service.get_values_for_inverter() == (1, 111.3209991, 1, 235.1999969)

def test_ahoy_values(test_service):
  test_service.setDTUVariant('ahoy')
  test_data = json.loads(ahoy_test_data_str)

  test_service.setTestData(test_data)
  assert test_service.get_values_for_inverter() == (22.5, 96.802, 0.1, 234.9)

def test_ahoy_timestamp(test_service):
  test_service.setDTUVariant('ahoy')
  test_data = json.loads(ahoy_test_data_str)

  test_service.setTestData(test_data)
  assert test_service._isDataUpToDate() == False

  test_data = json.loads(ahoy_test_data_str.replace('"ts_last_success":1675243378', '"ts_last_success":'+str(time.time()-10)))
  test_service.setTestData(test_data)
  assert test_service._isDataUpToDate() == True

def run_tests():
  test_service = DbusService(servicename='testing', paths='dummy', actual_inverter=0)
  test_opendtu_reachable(test_service)
  test_opendtu_reachable(test_service)
  test_ahoy_values(test_service)
  test_ahoy_timestamp(test_service)

if __name__ == "__main__":
  main()
