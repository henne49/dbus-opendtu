#!/usr/bin/env python
'''module to read data from dtu/template and show in VenusOS'''

from imports import *


def getConfig():
    """
    Reads the configuration from a config.ini file and sets up logging.

    The function reads the configuration file located in the same directory as the script.
    It configures the logging level based on the value specified in the configuration file.

    Returns:
        configparser.ConfigParser: The configuration object containing the parsed configuration.
    """
    # configure logging
    config = configparser.ConfigParser()
    config.read(f"{(os.path.dirname(os.path.realpath(__file__)))}/config.ini")
    logging_level = config["DEFAULT"]["Logging"].upper()

    logging.basicConfig(
        format="%(levelname)s %(message)s",
        level=logging_level,
    )

    return config


def register_services(config):
    """
    Registers DTU devices and templates based on the configuration.

    Args:
        config (configparser.ConfigParser): The configuration object containing the parsed configuration.
    """

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

    try:
        dtuvariant = config["DEFAULT"]["DTU"]
    except KeyError:
        logging.critical("DTU key not found in configuration")
        return

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
    config = getConfig()

    # TODO: I think it is better to run the tests inside CI/CD pipeline instead of running it here
    tests.run_tests()

    try:
        logging.critical("Start")

        from dbus.mainloop.glib import DBusGMainLoop  # pylint: disable=E0401,C0415

        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        register_services(config)

        logging.info("Connected to dbus, and switching over to gobject.MainLoop() (= event based)")
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as error:  # pylint: disable=W0718
        logging.critical("Error at %s", "main", exc_info=error)


if __name__ == "__main__":
    main()
