#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)
filename=/data/rc.local

#remove the service
rm /service/$SERVICE_NAME

# end the dbus-opendtu process
kill $(pgrep -f 'supervise dbus-opendtu')

# delete old logs if they exist  
if [ -f $SCRIPT_DIR/current.log ]; then  
    rm $SCRIPT_DIR/current.log*  
fi 
