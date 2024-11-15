'''Global constants'''

# region formatting helping functions (used in constant)


def _kwh(_p, value: float) -> str:
    return f"{round(value, 2)}KWh"


def _a(_p, value: float) -> str:
    return f"{round(value, 1)}A"


def _w(_p, value: float) -> str:
    return f"{round(value, 1)}W"


def _v(_p, value: float) -> str:
    return f"{round(value, 1)}V"
# endregion


DTUVARIANT_AHOY = "ahoy"
DTUVARIANT_OPENDTU = "opendtu"
DTUVARIANT_TEMPLATE = "template"
PRODUCTNAME = "henne49_dbus-opendtu"
CONNECTION = "TCP/IP (HTTP)"


VICTRON_PATHS = {
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
