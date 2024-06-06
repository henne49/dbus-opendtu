#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)
RC_LOCAL_FILE=/data/rc.local

#remove the service
rm /service/$SERVICE_NAME

# end the dbus-opendtu process
kill $(pgrep -f "python $SCRIPT_DIR/dbus-opendtu.py")

# delete old logs if they exist  
if [ -f $SCRIPT_DIR/current.log ]; then  
    rm $SCRIPT_DIR/current.log*  
fi 

# remove install.sh from rc.local
STARTUP=$SCRIPT_DIR/install.sh
sed -i "\~$STARTUP~d" $RC_LOCAL_FILE