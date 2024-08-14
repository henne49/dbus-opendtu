#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)
LOG_DIR=/var/log/$SERVICE_NAME
RC_LOCAL_FILE=/data/rc.local

#remove the service
if [ -d /service/$SERVICE_NAME ]; then  
    rm /service/$SERVICE_NAME
fi 

# end the dbus-opendtu process
kill $(pgrep -f "python $SCRIPT_DIR/dbus-opendtu.py")

# delete old logs if they exist  
if [ -f $SCRIPT_DIR/current.log ]; then  
    rm $SCRIPT_DIR/current.log*  
fi 

# remove install.sh from rc.local
STARTUP=$SCRIPT_DIR/install.sh
sed -i "\~$STARTUP~d" $RC_LOCAL_FILE

# delete log folder in var log if they exist  
if [ -d $LOG_DIR ]; then  
    while true; do
        read -p "Do you really wish to delete the log folder $LOG_DIR? [y/n]" yn
        case $yn in
            [Yy]* ) rm -rf $LOG_DIR; echo $LOG_DIR is deleted ; break;;
            [Nn]* ) break;;
            * ) echo "Please answer y or n.";;
        esac
    done
fi 