#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)


# check if config.ini file exists
if [ ! -f $SCRIPT_DIR/config.ini ]; then
    echo "config.ini file not found. Please make sure it exists. If not created yet, please copy it from config.example."
    exit 1
fi

# delete old logs if they exist  
if [ -f $SCRIPT_DIR/current.log ]; then  
    rm $SCRIPT_DIR/current.log*  
fi 

# check if version.txt exists and is larger than 2.0.0
if [ -f $SCRIPT_DIR/version.txt ] && 
    ( [ "$(grep -o 'Version: [^ ]*' version.txt | cut -d' ' -f2)" = "2.0.0" ] || 
    [ "$(grep -o 'Version: [^ ]*' version.txt | cut -d' ' -f2)" \> "2.0.0" ] ); then
    # delete old dbus-opendtu.py file
    if [ -f $SCRIPT_DIR/dbus-opendtu.py ]; then  
        rm $SCRIPT_DIR/dbus-opendtu.py 
    fi 
fi

# set permissions for script files
chmod a+x $SCRIPT_DIR/restart.sh
chmod 744 $SCRIPT_DIR/restart.sh

chmod a+x $SCRIPT_DIR/uninstall.sh
chmod 744 $SCRIPT_DIR/uninstall.sh

chmod a+x $SCRIPT_DIR/service/run
chmod 755 $SCRIPT_DIR/service/run

chmod a+x $SCRIPT_DIR/service/log/run
chmod 755 $SCRIPT_DIR/service/log/run

# create sym-link to run script in deamon
ln -s $SCRIPT_DIR/service /service/$SERVICE_NAME

# add install-script to rc.local to be ready for firmware update
filename=/data/rc.local

#check if rc.local already exists, if not create it
if [ ! -f $filename ]
then
    touch $filename
    chmod 755 $filename
    echo "#!/bin/bash" >> $filename
    echo >> $filename
fi

#check if the service exists? if not add it to rc.local
grep -qxF "$SCRIPT_DIR/install.sh" $filename || echo "$SCRIPT_DIR/install.sh" >> $filename
