# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Python service that bridges Hoymiles inverters (via [OpenDTU](https://github.com/tbnobody/OpenDTU) or [AhoyDTU](https://github.com/lumapu/ahoy)) and generic REST devices (Shelly, Tasmota) into Victron's Venus OS over DBus. Deployed on GX devices under `/data/dbus-opendtu/` and supervised by daemontools.

## Runtime environment matters

- The target runtime is **Venus OS**, not the dev machine. `dbus_service.py` imports `vedbus` from `/opt/victronenergy/dbus-systemcalc-py/ext/velib_python` (path injected via `sys.path.insert`). That module is not available outside Venus OS / the devcontainer, so running `dbus_opendtu.py` locally fails.
- Tests mock around dbus by using `servicename="testing"` in [`DbusService.__init__`](dbus_service.py#L66-L70), which short-circuits dbus registration. Any new test must use this path.
- Python 2/3 dual-support for `gobject`/`GLib` lives in [imports.py](imports.py) — don't remove the branch.
- CI targets **Python 3.8** ([.github/workflows/pylint.yml](.github/workflows/pylint.yml)).

## Commands

```bash
# Run tests (unittest discovery, no pytest)
python -m unittest discover -s tests -p "test_*.py"

# Run a single test
python -m unittest tests.test_dbus_service.TestDbusService.test_name

# Coverage (uses python3-coverage, i.e. Debian/Venus OS package naming)
./run_coverage.sh

# Lint (CI threshold: --fail-under=8.5)
pylint $(git ls-files '*.py')
```

Max line length is 120 ([.vscode/settings.json](.vscode/settings.json), autopep8).

On the target device:
- `install.sh` — sym-links [service/](service/) into `/service/$SERVICE_NAME`, appends itself to `/data/rc.local` for boot persistence. Requires `config.ini` to exist (copy [config.example](config.example)).
- `restart.sh` / `uninstall.sh` — kill the supervised python process / remove the service.
- `update.sh` — interactive download of a release from GitHub; writes into the same folder.

## Architecture

Single-process, event-loop driven:

1. [dbus_opendtu.py](dbus_opendtu.py) is the entry point. It reads `config.ini`, constructs one `DbusService` per inverter + per template, then starts a `GLib.MainLoop` with two periodic timers: `update_all_services` (1 s tick, self-throttled per service) and `sign_of_life_all_services` (minutes, just logs).
2. Each [`DbusService`](dbus_service.py) instance owns one `VeDbusService` on the bus (`{servicename}.http_{DeviceInstance}`). It fetches JSON from the DTU's REST API, extracts values, and pushes them to the DBus paths declared in [`constants.VICTRON_PATHS`](constants.py#L21-L43).
3. **Shared fetch optimization:** when multiple inverters are behind one DTU, only `pvinverternumber == 0` actually calls the HTTP API ([`_refresh_data`](dbus_service.py#L385-L402)). The JSON is cached on the class via `DbusService._meter_data` and all instances read from there. Templates bypass this — each has its own `self.meter_data`.
4. **Three DTU modes** (`DEFAULT.DTU` in config): `opendtu`, `ahoy`, `template`. `ahoy`/`opendtu` and `template` can coexist — templates are always iterated on top. The mode drives URL shape, JSON parsing, and the polling interval (5 s for OpenDTU, 5 s or `ESP8266PollingIntervall` for Ahoy depending on ESP type, configurable for templates).
5. **Error handling** has two modes (`ErrorMode`): `retrycount` (zero values + StatusCode=10 after N consecutive failures) and `timeout` (zero values only after `ErrorStateAfterSeconds` without any success). See README "Error Handling Modes" — both modes share `RetryAfterSeconds` for reconnect cadence.
6. **Three-phase split:** if `Phase=3P`, reported total power/current/energy is divided across L1/L2/L3 (Hoymiles three-phase micros only report totals). Otherwise values land on the single configured phase.
7. **Service types:** `com.victronenergy.pvinverter` is the normal path. `com.victronenergy.inverter` (battery inverter / non-PV) is BETA and adds `/Mode` and `/State` paths ([dbus_service.py:135-143](dbus_service.py#L135-L143)).

## Details on OpenDTU API
[OpenDTU API](https://www.opendtu.solar/firmware/web_api/)

## Configuration

- `config.ini` is required at runtime and is **gitignored**. [config.example](config.example) is the authoritative template — update it in lockstep with any new config key.
- Helpers [`get_config_value`](helpers.py#L33) and [`get_default_config`](helpers.py#L45) wrap lookups; `get_config_value` raises for missing keys in `INVERTER*` sections (no silent defaults there).
- Template `CUST_*` path keys are slash-separated paths into the JSON, consumed by [`get_value_by_path`](helpers.py#L53) which falls back to integer-indexing for array steps.

## Tests and fixtures

- JSON fixtures under [docs/](docs/) are test data, not user docs — every supported DTU variant/version has a captured sample (e.g. `ahoy_0.5.93_live.json`, `opendtu_v24.2.12_livedata_status.json`, `tasmota_shelly_2pm.json`). Add a new fixture when adding support for a new DTU firmware shape.
- [tests.py](tests.py) is a legacy in-process test runner that's disabled in `main()`. New tests belong in [tests/](tests/) using `unittest`.
- `tests/test_dbus_service.py` mocks `requests.get` (see `mocked_requests_get`) to return fixture JSON — follow that pattern for new HTTP-dependent tests.

## Versioning

Version is tracked in [version.txt](version.txt) (format: `Version: X.Y.Z`) and read at startup by [`read_version`](helpers.py#L129) to populate `/FirmwareVersion` on DBus. GitHub Actions (`.github/workflows/version.yml`) bumps it on release. `install.sh` has version-gated cleanup logic for migrations across 2.0.0.
