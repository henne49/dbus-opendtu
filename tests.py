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


OPENDTU_TEST_DATA_FILE = "docs/opendtu_status.json"
AHOY_TEST_DATA_FILE_LIVE = "docs/ahoy_0.5.93_live.json"
AHOY_TEST_DATA_FILE_RECORD = "docs/ahoy_0.5.93_record-live.json"
AHOY_TEST_DATA_FILE_IV_0 = "docs/ahoy_0.5.93_inverter-id-0.json"


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
    assert test_service.get_values_for_inverter() == (0, 270.4660034, 0, 226.1999969)

    test_data = load_json_file(OPENDTU_TEST_DATA_FILE, '"producing": false', '"producing":"1"')
    test_service.set_test_data(test_data)
    # (power, pvyield total, current, voltage)
    assert test_service.get_values_for_inverter() == (31.79999924, 270.4660034, 0.140000001, 226.1999969)


def load_json_file(filename, find_str = None, replace_str = None):
    '''Load json data from filename (relative to main file). If given, find_str is replaced by replace_str'''
    with open(f"{(os.path.dirname(os.path.realpath(__file__)))}/{filename}") as file:
        json_str = file.read()
        if find_str != None:
            json_str = json_str.replace(find_str, replace_str)
        return json.loads(json_str)

def load_ahoy_test_data():
    '''Load Test data for Ahoy'''
    test_data = load_json_file(AHOY_TEST_DATA_FILE_LIVE)
    # not needed: test_data["record"] = load_json_file(AHOY_TEST_DATA_FILE_RECORD)
    test_data["inverter"] = []
    test_data["inverter"].append(load_json_file(AHOY_TEST_DATA_FILE_IV_0))
    return test_data


def test_ahoy_values(test_service):
    '''test with ahoy data'''
    test_service.set_dtu_variant(constants.DTUVARIANT_AHOY)
    test_data = load_ahoy_test_data()

    test_service.set_test_data(test_data)
    # (power, pvyield total, current, voltage)
    assert test_service.get_values_for_inverter() == (223.7, 422.603, 0.98, 229.5)


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


def run_tests():
    '''function to run tests'''
    test_service = DbusService(servicename="testing", paths="dummy", actual_inverter=0)
    test_opendtu_reachable(test_service)
    test_opendtu_producing(test_service)
    test_ahoy_values(test_service)
    test_ahoy_timestamp(test_service)
    logging.debug("tests have passed")
