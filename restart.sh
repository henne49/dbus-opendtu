#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

rm $SCRIPT_DIR/current.log

kill $(pgrep -f "python $SCRIPT_DIR/dbus-opendtu.py")
