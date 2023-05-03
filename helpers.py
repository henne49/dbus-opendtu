'''Module containing various helper functions'''

# File specific rules
# pylint: disable=broad-except

# system imports
import functools
import time

# our imports:
import logging


def get_config_value(config, name, inverter_or_template, pvinverternumber, defaultvalue=None):
    '''check if config value exist in current inverter/template's section, otherwise throw error'''
    if name in config[f"{inverter_or_template}{pvinverternumber}"]:
        return config[f"{inverter_or_template}{pvinverternumber}"][name]

    if defaultvalue is None:
        raise ValueError(f"config entry '{name}' not found. \
            Hint: Deprecated Host ONPREMISE entries must be moved to DEFAULT section")

    return defaultvalue

def get_default_config(config, name, defaultvalue):
    '''check if config value exist in DEFAULT section, otherwise return defaultvalue'''
    if name in config["DEFAULT"]:
        return config["DEFAULT"][name]

    return defaultvalue

def get_nested(meter_data, path):
    '''Try to extract 'path' from nested array 'meter_data' (derived from json document) and return the found value'''
    value = meter_data
    for path_entry in path:
        try:
            value = value[path_entry]
        except Exception:
            try:
                value = value[int(path_entry)]
            except Exception:
                value = 0
    return value

def get_ahoy_field_by_name(meter_data, actual_inverter, fieldname, use_ch0_fld_names = True):
    '''get the value by name instead of list index'''
    # fetch value from record call:
    #  - but there seem to be more than one value per type and Inverter, and we don't know which one to take
    # values = meter_data["record"]["inverter"][actual_inverter] # -> array of dicts
    # for value_dict in values:
    #     if value_dict["fld"] == fieldname:
    #         val = value_dict["val"]
    #         print(f"returning fieldname {fieldname}: value {val}")
    #         return val
    # raise ValueError(f"Fieldname {fieldname} not found in meter_data.")

    data = None

    # If "use_ch0_fld_names" is true, then the field names from the ch0_fld_names section in the JSON is used
    # instead of the "fld_names" channel which includes DC-Parameter like "U_DC"
    if use_ch0_fld_names:
        data_field_names = meter_data["ch0_fld_names"]
        data_index = data_field_names.index(fieldname)
        ac_channel_index = 0
        data = meter_data["inverter"][actual_inverter]["ch"][ac_channel_index][data_index]
    else:
        data_field_names = meter_data["fld_names"]
        data_index = data_field_names.index(fieldname)
        # TODO - check if this channel has to be adjusted
        dc_channel_index = 1 # 1 = DC1, 2 = DC2 etc.
        data = meter_data["inverter"][actual_inverter]["ch"][dc_channel_index][data_index]

    return data

def is_true(val):
    '''helper function to test for different true values'''
    return val in (1, '1', True, "True", "true")

def timeit(func):
    '''decorator to measure execution time of a function'''
    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        logging.debug(f"function {func.__name__} finished in {round(elapsed_time * 1000)} ms")
        return result
    return wrapped_func
