#!/usr/bin/env python
'''module to read data from dtu/template and show in VenusOS'''

from imports import *

config = None
number_of_inverters = 0
number_of_templates = 0


def initialize():
    """ Initialize the module """
    # pylint: disable=w0603
    global config, number_of_inverters, number_of_templates

    # configure logging
    config = configparser.ConfigParser()
    config.read(f"{(os.path.dirname(os.path.realpath(__file__)))}/config.ini")
    logging_level = config["DEFAULT"]["Logging"].upper()

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


def register_service():
    """ Register the service """
    global number_of_inverters

    dtuvariant = config["DEFAULT"]["DTU"]
    if dtuvariant != constants.DTUVARIANT_TEMPLATE:
        logging.critical("Registering dtu devices")
        servicename = get_config_value(config, "Servicename", "INVERTER", 0, "com.victronenergy.pvinverter")
        service = DbusService(
            servicename=servicename,
            actual_inverter=0,
        )

        if number_of_inverters == 0:
            # pylint: disable=W0621
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
            actual_inverter=actual_template,
            istemplate=True,
        )


def main():
    """ Main function """
    initialize()
    tests.run_tests()

    try:
        logging.critical("Start")

        from dbus.mainloop.glib import DBusGMainLoop  # pylint: disable=E0401,C0415

        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        register_service()

        logging.info("Connected to dbus, and switching over to gobject.MainLoop() (= event based)")
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as error:
        logging.critical("Error at %s", "main", exc_info=error)


if __name__ == "__main__":
    main()
