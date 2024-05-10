'''(Unit) tests'''

# system imports:
import json
import logging
import os
import time

# our imports:
import constants

# Victron imports:
from dbus_service import DbusService
from helpers import get_value_by_path


OPENDTU_TEST_DATA_FILE = "docs/opendtu_status.json"
AHOY_TEST_DATA_FILE_LIVE = "docs/ahoy_0.5.93_live.json"
AHOY_TEST_DATA_FILE_RECORD = "docs/ahoy_0.5.93_record-live.json"
AHOY_TEST_DATA_FILE_IV_0 = "docs/ahoy_0.5.93_inverter-id-0.json"
TEMPLATE_TASMOTA_TEST_DATA_FILE = "docs/tasmota_shelly_2pm.json"


def test_opendtu_reachable(test_service):
    '''Test if DTU is reachable'''
    test_service.set_dtu_variant(constants.DTUVARIANT_OPENDTU)
    test_data = load_json_file(OPENDTU_TEST_DATA_FILE)

    test_service.set_test_data(test_data)
    assert test_service.is_data_up2date() is False

    test_data = load_json_file(OPENDTU_TEST_DATA_FILE, '"reachable": false', '"reachable":"1"')
    test_service.set_test_data(test_data)
    assert test_service.is_data_up2date() is True

    test_data = load_json_file(OPENDTU_TEST_DATA_FILE, '"reachable": false', '"reachable":1')
    test_service.set_test_data(test_data)
    assert test_service.is_data_up2date() is True

    test_data = load_json_file(OPENDTU_TEST_DATA_FILE, '"reachable": false', '"reachable":true')
    test_service.set_test_data(test_data)
    assert test_service.is_data_up2date() is True

    test_data = load_json_file(OPENDTU_TEST_DATA_FILE, '"reachable": false', '"reachable":false')
    test_service.set_test_data(test_data)
    assert test_service.is_data_up2date() is False


def test_opendtu_producing(test_service):
    '''test if the opendtu inverter is producing'''
    test_service.set_dtu_variant(constants.DTUVARIANT_OPENDTU)
    test_data = load_json_file(OPENDTU_TEST_DATA_FILE)

    test_service.set_test_data(test_data)
    # current, power are 0 because inverter is not producing
    # (power, pvyield total, current, voltage)
    assert test_service.get_values_for_inverter() == (0, 270.4660034, 0, 226.1999969, 0.699999988)

    test_data = load_json_file(OPENDTU_TEST_DATA_FILE, '"producing": false', '"producing":"1"')
    test_service.set_test_data(test_data)
    # (power, pvyield total, current, voltage)
    assert test_service.get_values_for_inverter() == (31.79999924, 270.4660034, 0.140000001, 226.1999969, 0.699999988)


def load_json_file(filename, find_str=None, replace_str=None):
    '''Load json data from filename (relative to main file). If given, find_str is replaced by replace_str'''
    with open(f"{(os.path.dirname(os.path.realpath(__file__)))}/{filename}", encoding="utf-8") as file:
        json_str = file.read()
        if find_str is not None:
            json_str = json_str.replace(find_str, replace_str)
        return json.loads(json_str)


def load_ahoy_test_data():
    '''Load Test data for Ahoy'''
    test_data = load_json_file(AHOY_TEST_DATA_FILE_LIVE)
    # not needed: test_data["record"] = load_json_file(AHOY_TEST_DATA_FILE_RECORD)
    test_data["inverter"] = []
    test_data["inverter"].append(load_json_file(AHOY_TEST_DATA_FILE_IV_0))
    return test_data


def load_template_tasmota_test_data():
    '''Load Test data for Template for tasmota case'''
    test_data = load_json_file(TEMPLATE_TASMOTA_TEST_DATA_FILE)
    return test_data


def test_ahoy_values(test_service):
    '''test with ahoy data'''
    test_service.set_dtu_variant(constants.DTUVARIANT_AHOY)
    test_data = load_ahoy_test_data()

    test_service.set_test_data(test_data)
    # (power, pvyield total, current, voltage)
    assert test_service.get_values_for_inverter() == (223.7, 422.603, 0.98, 229.5, 33.3)


def test_ahoy_timestamp(test_service):
    '''test the timestamps for ahoy'''
    test_service.set_dtu_variant(constants.DTUVARIANT_AHOY)
    test_data = load_ahoy_test_data()

    test_service.set_test_data(test_data)
    assert test_service.is_data_up2date() is False

    test_data = load_ahoy_test_data()
    test_data["inverter"][0]["ts_last_success"] = time.time() - 10
    test_service.set_test_data(test_data)
    assert test_service.is_data_up2date() is True


def test_ahoy_get_number_of_inverters(test_service):
    '''test if get_number_of_inverters works correctly'''
    test_service.set_dtu_variant(constants.DTUVARIANT_AHOY)
    test_data = load_ahoy_test_data()

    test_service.set_test_data(test_data)
    assert test_service.get_number_of_inverters() == 3


def test_get_value_by_path():
    test_meter_data = {
        "a": 1,
        "b": {
            "c": 3,
            "arr": ["x", "y"],
        }
    }
    assert 1 == get_value_by_path(test_meter_data, ["a"])
    assert 3 == get_value_by_path(test_meter_data, ["b", "c"])
    assert "y" == get_value_by_path(test_meter_data, ["b", "arr", 1])  # not: ["b", "arr[1]"]


def test_template_values(test_service):
    '''test with template test data for tasmota'''
    test_service.set_dtu_variant(constants.DTUVARIANT_TEMPLATE)
    test_service.custpower = "StatusSNS/ENERGY/Power/0".split("/")
    test_service.custcurrent = "StatusSNS/ENERGY/Current/0".split("/")
    test_service.custpower_default = 999
    test_service.custcurrent_default = 999
    test_service.custpower_factor = 2
    test_service.custtotal_default = 99
    test_service.custtotal_factor = 1
    test_service.custvoltage = "StatusSNS/ENERGY/Voltage".split("/")
    test_service.custvoltage_default = 99.9
    test_service.custtotal = "StatusSNS/ENERGY/Today".split("/")

    test_data = load_template_tasmota_test_data()

    test_service.set_test_data(test_data)
    logging.debug("starting test for test_template_values")
    (power, pvyield, current, voltage, dc_voltage) = test_service.get_values_for_inverter()
    print(power, pvyield, current, voltage, dc_voltage)
    assert (power, pvyield, current, voltage, dc_voltage) == (320.0, 0.315, 0.734, 235, None)


def run_tests():
    '''function to run tests'''
    test_get_value_by_path()
    test_service = DbusService(servicename="testing", paths="dummy", actual_inverter=0)
    test_opendtu_reachable(test_service)
    test_opendtu_producing(test_service)
    test_ahoy_values(test_service)
    test_ahoy_timestamp(test_service)
    test_template_values(test_service)
    logging.debug("tests have passed")
