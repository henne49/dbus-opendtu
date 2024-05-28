#!/usr/bin/env python
'''module to read data from dtu/template and show in VenusOS'''


# File specific rules
# pylint: disable=broad-except

# system imports:
import logging
import logging.handlers
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
    import gobject  # pylint: disable=E0401
else:
    from gi.repository import GLib as gobject  # pylint: disable=E0401


def main():
    '''main loop'''
    # configure logging
    config = configparser.ConfigParser()
    config.read(f"{(os.path.dirname(os.path.realpath(__file__)))}/config.ini")
    logging_level = config["DEFAULT"]["Logging"].upper()
    dtuvariant = config["DEFAULT"]["DTU"]

    logging.basicConfig(
        format="%(levelname)s %(message)s",
        level=logging_level,
    )

    try:
        number_of_inverters = int(config["DEFAULT"]["NumberOfInvertersToQuery"])
    except (KeyError, ValueError) as ex:
        logging.warning("NumberOfInvertersToQuery: %s", ex)
        logging.warning("NumberOfInvertersToQuery not set, using default")
        number_of_inverters = 0

    try:
        number_of_templates = int(config["DEFAULT"]["NumberOfTemplates"])
    except (KeyError, ValueError) as ex:
        logging.warning("NumberOfTemplates: %s", ex)
        logging.warning("NumberOfTemplates not set, using default")
        number_of_templates = 0


    tests.run_tests()

    try:
        logging.critical("Start")

        from dbus.mainloop.glib import DBusGMainLoop  # pylint: disable=E0401,C0415

        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        # region formatting
        def _kwh(_p, value: float) -> str:
            return f"{round(value, 2)}KWh"

        def _a(_p, value: float) -> str:
            return f"{round(value, 1)}A"

        def _w(_p, value: float) -> str:
            return f"{round(value, 1)}W"

        def _v(_p, value: float) -> str:
            return f"{round(value, 1)}V"
        # endregion

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
            "/Ac/Out/L1/I": {"initial": None, "textformat": _a},
            "/Ac/Out/L1/V": {"initial": None, "textformat": _v},
            "/Ac/Out/L1/P": {"initial": None, "textformat": _w},
            "/Dc/0/Voltage": {"initial": None, "textformat": _v},
        }

        if dtuvariant != constants.DTUVARIANT_TEMPLATE:
            logging.critical("Registering dtu devices")
            servicename = get_config_value(config, "Servicename", "INVERTER", 0, "com.victronenergy.pvinverter")
            service = DbusService(
                servicename=servicename,
                paths=paths,
                actual_inverter=0,
            )

            if number_of_inverters == 0:
                number_of_inverters = service.get_number_of_inverters()

            if number_of_inverters > 1:
                # start our main-service if there are more than 1 inverter
                for actual_inverter in range(number_of_inverters - 1):
                    servicename = get_config_value(
                        config,
                        "Servicename",
                        "INVERTER",
                        actual_inverter + 1,
                        "com.victronenergy.pvinverter"
                    )
                    DbusService(
                        servicename=servicename,
                        paths=paths,
                        actual_inverter=actual_inverter + 1,
                    )

        for actual_template in range(number_of_templates):
            logging.critical("Registering Templates")
            servicename = get_config_value(
                config,
                "Servicename",
                "TEMPLATE",
                actual_template,
                "com.victronenergy.pvinverter"
            )
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
