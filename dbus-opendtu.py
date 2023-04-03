#!/usr/bin/env python
'''module to read data from dtu/template and show in VenusOS'''

# system imports:
import logging
import os
import configparser
import sys

# our imports:
import constants
import tests
from helpers import *

# Victron imports:
from dbus_service import DbusService

if sys.version_info.major == 2:
    import gobject #pylint: disable=E0401
else:
    from gi.repository import GLib as gobject #pylint: disable=E0401


def main():
    '''main loop'''
    # configure logging
    config = configparser.ConfigParser()
    config.read(f"{(os.path.dirname(os.path.realpath(__file__)))}/config.ini")
    logging_level = config["DEFAULT"]["Logging"]
    dtuvariant = config["DEFAULT"]["DTU"]

    try:
        number_of_templates = int(config["DEFAULT"]["NumberOfTemplates"])
    except Exception:
        number_of_templates = 0

    logging.basicConfig(
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging_level,
        handlers=[
            logging.FileHandler(
                f"{(os.path.dirname(os.path.realpath(__file__)))}/current.log"
            ),
            logging.StreamHandler(),
        ],
    )

    tests.run_tests()

    try:
        logging.info("Start")

        from dbus.mainloop.glib import DBusGMainLoop #pylint: disable=E0401

        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        # formatting
        _kwh = lambda p, v: (str(round(v, 2)) + "KWh")
        _a = lambda p, v: (str(round(v, 1)) + "A")
        _w = lambda p, v: (str(round(v, 1)) + "W")
        _v = lambda p, v: (str(round(v, 1)) + "V")

        paths = {
            "/Ac/Energy/Forward": {
                "initial": None,
                "textformat": _kwh,
            },  # energy produced by pv inverter
            "/Ac/Power": {"initial": None, "textformat": _w},
            "/Ac/L1/Voltage": {"initial": None, "textformat": _v},
            "/Ac/L2/Voltage": {"initial": None, "textformat": _v},
            "/Ac/L3/Voltage": {"initial": None, "textformat": _v},
            "/Ac/L1/Current": {"initial": None, "textformat": _a},
            "/Ac/L2/Current": {"initial": None, "textformat": _a},
            "/Ac/L3/Current": {"initial": None, "textformat": _a},
            "/Ac/L1/Power": {"initial": None, "textformat": _w},
            "/Ac/L2/Power": {"initial": None, "textformat": _w},
            "/Ac/L3/Power": {"initial": None, "textformat": _w},
            "/Ac/L1/Energy/Forward": {"initial": None, "textformat": _kwh},
            "/Ac/L2/Energy/Forward": {"initial": None, "textformat": _kwh},
            "/Ac/L3/Energy/Forward": {"initial": None, "textformat": _kwh},
        }

        if dtuvariant != constants.DTUVARIANT_TEMPLATE:
            logging.info("Registering dtu devices")
            servicename=get_config_value(config, "Servicename", "INVERTER", 0, "com.victronenergy.pvinverter")
            service = DbusService(
                servicename=servicename,
                paths=paths,
                actual_inverter=0,
            )

            number_of_inverters = service.get_number_of_inverters()

            if number_of_inverters > 1:
                # start our main-service if there are more than 1 inverter
                for actual_inverter in range(number_of_inverters - 1):
                    servicename=get_config_value(config, "Servicename", "INVERTER", actual_inverter + 1, "com.victronenergy.pvinverter")
                    DbusService(
                        servicename=servicename,
                        paths=paths,
                        actual_inverter=actual_inverter + 1,
                    )

        for actual_template in range(number_of_templates):
            logging.info("Registering Templates")
            servicename = get_config_value(config, "Servicename", "TEMPLATE", actual_template, "com.victronenergy.pvinverter")
            service = DbusService(
                servicename=servicename,
                paths=paths,
                actual_inverter=actual_template,
                istemplate=True,
            )

        logging.info("Connected to dbus, and switching over to gobject.MainLoop() (= event based)")
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as error:
        logging.critical("Error at %s", "main", exc_info=error)


if __name__ == "__main__":
    main()
