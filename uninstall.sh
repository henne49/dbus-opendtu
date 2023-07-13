#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)
filename=/data/rc.local
rm /service/$SERVICE_NAME
kill $(pgrep -f 'supervise dbus-opendtu')
chmod a-x $SCRIPT_DIR/service/run
$SCRIPT_DIR/restart.sh
STARTUP=$SCRIPT_DIR/install.sh
#sed -i "\~/data/dbus-opendtu/install.sh~d" $filename
sed -i "\~$STARTUP~d" $filename
