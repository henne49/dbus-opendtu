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


def get_DbusServices(config):
    """
    Retrieves and registers D-Bus services based on the provided configuration.

    Args:
        config (dict): Configuration dictionary containing the necessary settings.

    Returns:
        list: A list of registered DbusService instances.
    """

    services = []

    # region Get the configuration values
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
    # endregion

    # region Register the inverters
    if dtuvariant != constants.DTUVARIANT_TEMPLATE:
        logging.info("Registering dtu devices")
        servicename = get_config_value(config, "Servicename", "INVERTER", 0, "com.victronenergy.pvinverter")
        service = DbusService(
            servicename=servicename,
            actual_inverter=0,
        )
        services.append(service)

        if number_of_inverters == 0:
            # pylint: disable=W0621
            number_of_inverters = service.get_number_of_inverters()

        # If there are no inverters or templates, return an empty list
        if number_of_inverters == 0 and number_of_templates == 0:
            logging.critical("No inverters or templates to query")
            return []  # Empty list

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
                services.append(DbusService(
                    servicename=servicename,
                    actual_inverter=actual_inverter + 1,
                ))
    # endregion

    # region Register the templates
    for actual_template in range(number_of_templates):
        logging.critical("Registering Templates")
        servicename = get_config_value(
            config,
            "Servicename",
            "TEMPLATE",
            actual_template,
            "com.victronenergy.pvinverter"
        )
        services.append(DbusService(
            servicename=servicename,
            actual_inverter=actual_template,
            istemplate=True,
        ))
    # endregion

    return services


def sign_of_life_all_services(services):
    """
    Sends a 'sign of life' signal to all services in the provided list.

    Args:
        services (list): A list of service objects. Each service object must have a 'sign_of_life' method.

    Returns:
        bool: Always returns True to keep the timeout active.
    """
    for service in services:
        service.sign_of_life()
    return True


def update_all_services(services):
    """
    Updates all services in the provided list.

    Args:
        services (list): A list of service objects. 
            Each service object must have an 'update' method and 
            a 'polling_interval' and a 'polling_last_polling' attribute.

    Returns:
        bool: Always returns True to keep the timeout active.
    """
    if sys.version_info.major == 2:
        current_time = gobject.get_current_time()
    else:
        current_time = gobject.get_real_time() // 1000
    for service in services:
        if current_time - service.last_polling >= service.polling_interval:
            service.update()
            service.last_polling = current_time
    return True


def main():
    """ Main function """
    config = getConfig()
    signofliveinterval = int(get_config_value(config, "SignOfLifeLog", "DEFAULT", "", 1))

    logging.debug("SignOfLifeLog: %d", signofliveinterval)

    # TODO: I think it is better to run the tests inside CI/CD pipeline instead of running it here
    # tests.run_tests()

    try:
        logging.info("Start")

        from dbus.mainloop.glib import DBusGMainLoop  # pylint: disable=E0401,C0415

        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        services = get_DbusServices(config)
        logging.info("Registered %d services", len(services))

        # Use a single timeout to call sign_of_life for all services
        gobject.timeout_add(signofliveinterval * 60 * 1000, sign_of_life_all_services, services)

        # Use another timeout to update all services
        gobject.timeout_add(1000, update_all_services, services)

        logging.info("Connected to dbus, and switching over to gobject.MainLoop() (= event based)")
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as error:  # pylint: disable=W0718
        logging.critical("Error at %s", "main", exc_info=error)


if __name__ == "__main__":
    main()
