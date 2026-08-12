'''Global constants'''

from helpers import _kwh, _a, _w, _v

DTUVARIANT_AHOY = "ahoy"
DTUVARIANT_OPENDTU = "opendtu"
DTUVARIANT_TEMPLATE = "template"
PRODUCTNAME = "henne49_dbus-opendtu"
CONNECTION = "TCP/IP (HTTP)"
MODE_TIMEOUT = "timeout"
MODE_RETRYCOUNT = "retrycount"

# /StatusCode values shared by com.victronenergy.pvinverter and .inverter
# 0..6 = Startup, 7 = Running, 8 = Standby, 9 = Boot loading, 10 = Error
STATUSCODE_STARTUP = 0
STATUSCODE_RUNNING = 7
STATUSCODE_STANDBY = 8
STATUSCODE_BOOTLOADING = 9
STATUSCODE_ERROR = 10

# ---------------------------------------------------------------------------
# com.victronenergy.pvinverter DBus schema
# (https://github.com/victronenergy/venus/wiki/dbus#pv-inverters)
#
# Published via PVINVERTER_PATHS (registered in the add_path loop):
#   /Ac/Energy/Forward      kWh   Total produced energy over all phases
#   /Ac/Power               W     Total real power across all phases
#   /Ac/L<n>/Voltage        V AC
#   /Ac/L<n>/Current        A AC
#   /Ac/L<n>/Power          W
#   /Ac/L<n>/Energy/Forward kWh
#   /Ac/MaxPower            W     Max rated power of the inverter
#   /Ac/PowerLimit          W     Fronius zero-feed-in setpoint. Must be absent
#                                  for PV inverters without power-limit support;
#                                  VictronConnect-set user limit still caps it.
#
# Deprecated (do not use):
#   /Ac/Current, /Ac/Voltage
#
# Published directly in dbus_service.py __init__:
#   /Position               0 = AC input 1, 1 = AC output, 2 = AC input 2
#   /PositionIsAdjustable   0 = not adjustable, 1 = adjustable
#   /StatusCode             see STATUSCODE_* above
#
# Optional (not implemented here):
#   /ErrorCode              0 = No Error
#   /FroniusDeviceType      Fronius-specific product id
#   /IsGenericEnergyMeter   1 = PV inverter is provided by a generic energy
#                             meter (no power-limit support)
# ---------------------------------------------------------------------------

PVINVERTER_PATHS = {
    "/Ac/Energy/Forward": {"initial": None, "textformat": _kwh},
    "/Ac/Power": {"initial": None, "textformat": _w},
    "/Ac/MaxPower": {"initial": None, "textformat": _w},
    "/Ac/PowerLimit": {"initial": None, "textformat": _w},
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

# Superset used by com.victronenergy.inverter (battery inverter). Adds the
# Ac/Out/* and Dc/0/Voltage paths that the inverter service reports on.
VICTRON_PATHS = dict(PVINVERTER_PATHS)
VICTRON_PATHS.update({
    "/Ac/Out/L1/I": {"initial": None, "textformat": _a},
    "/Ac/Out/L1/V": {"initial": None, "textformat": _v},
    "/Ac/Out/L1/P": {"initial": None, "textformat": _w},
    "/Dc/0/Voltage": {"initial": None, "textformat": _v},
})
