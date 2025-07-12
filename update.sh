# Set the repository name and username
REPO="henne49/dbus-opendtu"
STARTUP_FILE="/data/rc.local"
#!/bin/bash

# Check if the file exists
if [ -f $STARTUP_FILE ]; then
  # Use grep to find lines containing install.sh and extract the full path
  FOLDERS=$(grep 'install.sh' $STARTUP_FILE | sed -r 's/bash //; s/install\.sh$//; s/\/$//')

  # If no folder is found, ask the user to enter one
  if [ $(echo "$FOLDERS" | wc -l) -eq 0 ]; then
    read -p "No entry with install.sh found. Please enter the path to the folder you want to use: " SCRIPT_DIR
  else
    echo "Found folders:"
    i=1
    for folder in $FOLDERS; do
      echo "$i. $folder"
      ((i++))
    done
    echo "$i. Enter folder manually"
    while true; do
      read -p "Enter the number of the folder you want to use: " choice
      if [ $choice -ge 1 ] && [ $choice -le $i ]; then
        if [ $choice -eq $i ]; then
          read -p "Please enter the path to the folder you want to use: " SCRIPT_DIR
        else
          SCRIPT_DIR=$(echo "$FOLDERS" | sed -n "$choice"p)
        fi
        break
      else
        echo "Invalid selection. Please try again."
      fi
    done
  fi
else
  read -p "The file /data/rc.local does not exist. Please enter the path to the folder you want to use: " SCRIPT_DIR
fi

echo "Using folder: $SCRIPT_DIR"

# Check if SCRIPT_DIR is the current working directory
if [ "$SCRIPT_DIR" = "$(pwd)" ]; then
  echo "SCRIPT_DIR is the current working directory."
else
  echo "SCRIPT_DIR is not the current working directory."
fi

if [ ! -d "$SCRIPT_DIR" ]; then
  read -p "The directory $SCRIPT_DIR does not exist. Do you want to create it? (yes/no) " answer
  if [ "$answer" in ["yes","y"] ]; then
    mkdir -p "$SCRIPT_DIR"
    echo "Directory $SCRIPT_DIR created successfully."
    cd "$SCRIPT_DIR/"
  else
    echo "Directory creation cancelled. Exiting..."
    exit 1
  fi
fi

# Check if version.txt exists in the selected directory
if [ -f "$SCRIPT_DIR/version.txt" ]; then
  INSTALLED_VERSION=$(cat "$SCRIPT_DIR/version.txt" | sed 's/Version: /v/')
  echo "Version: $INSTALLED_VERSION"
else
  echo "No version.txt file found in the selected directory."
  INSTALLED_VERSION="none"
fi

# delete old logs if they exist  
if [ -f $SCRIPT_DIR/current.log ]; then  
    rm $SCRIPT_DIR/current.log*  
fi

# Check if the current folder has enough space for 5MB
FREE_SPACE=$(df . | tail -1 | awk '{ print $4 }' | sed 's/[A-Za-z]//g' | awk '{ printf("%.0f\n", $1 / 1024) }')

if [ $FREE_SPACE -lt 5 ]; then
  echo "Error: Not enough free space in the current folder. Need at least 5MB."
  exit 1
fi

# Ask the user for the version to download, defaulting to "latest"
echo "Enter the version to download (e.g. main, v1.2.25, or press enter for latest):"
read VERSION

# If no version is specified, default to "latest"
if [ -z "$VERSION" ]; then
  VERSION="latest"
fi

# Check if the user wants to download the latest version
if [ "$VERSION" = "latest" ]; then
  # Fetch the latest release information from the GitHub API
  # and extract the latest tag name using awk
  # Assuming GitHub API returns the latest release tag in the format "vX.X.X"
  LATEST_TAG=$(curl -s https://api.github.com/repos/$REPO/releases/latest | 
               awk -F'"' '/tag_name/{print $4}')
  TAG=$LATEST_TAG
else
  # Check if the user wants to download a pre-release version
  if [ "$VERSION" = "pre-release" ]; then
    # Fetch the latest pre-release information from the GitHub API
    # and extract the latest pre-release tag name using awk
    # Assuming GitHub API returns pre-release tags in the format "vX.X.X-rc.X" or "vX.X.X-beta.X"
    PRE_RELEASE_TAG=$(curl -s https://api.github.com/repos/$REPO/releases | 
                      awk -F'"' '/tag_name/{print $4}' | 
                      grep -vE '^v[0-9]+\.[0-9]+\.[0-9]+$')
    TAG=$PRE_RELEASE_TAG
  else
    # Use the specified version as the tag
    # Assuming the version is in the format "vX.X.X"
    TAG=$VERSION
  fi
fi

# check for main or latest version
if [ "$VERSION" == "latest" ] || [ "$VERSION" = "main" ]; then
    # If the installed version is older as the version, print a message
    read -p "INSTALLED VERSION ($INSTALLED_VERSION) will be updated with VERSION ($VERSION). Do you want to continue? (yes/no) " response
# Compare the version numbers using sort -V
# sort -V compares version numbers, ignoring any non-numeric characters
# head -n1 gets the first line of the sorted output, which is the older version
elif [ "$(printf '%s\n' "$INSTALLED_VERSION" "$VERSION" | sort -V | head -n1)" != "$INSTALLED_VERSION" ]; then
    # If the installed version is newer, print a warning
    read -p "WARNING: INSTALLED VERSION ($INSTALLED_VERSION) is newer than UPDATE VERSION ($VERSION). Do you want to continue? (yes/no) " response
elif [ "$INSTALLED_VERSION" != "$VERSION" ]; then
    # If the installed version is older as the version, print a message
    read -p "INSTALLED VERSION ($INSTALLED_VERSION) is older than UPDATE VERSION ($VERSION). Do you want to continue? (yes/no) " response
else
    # If the installed version is the same as the version, print a message
    read -p "INSTALLED VERSION ($INSTALLED_VERSION) is the same as UPDATE VERSION ($VERSION). Do you want to continue? (yes/no) " response
fi
if [ "$response" !in ["yes","y"] ]; then
    # If the user doesn't want to continue, exit the script
    echo "Exiting..."
    exit 1
fi

# Download the zip file for the specified tag

wget -O $SCRIPT_DIR/$TAG.zip https://github.com/$REPO/archive/$TAG.zip || { echo "version does not exist"; exit 1; }

# Unzip the downloaded file
unzip $SCRIPT_DIR/$TAG.zip -d $SCRIPT_DIR

# Check if the TAG string starts with 'v'
if [[ $TAG =~ ^v ]]; then
  # If it starts with 'v', remove the first character and return the result
  EXTRACT_FOLDER="dbus-opendtu-${TAG:1}"
else
  EXTRACT_FOLDER="dbus-opendtu-$TAG"
fi

echo $EXTRACT_FOLDER

# Copy all files from the extract folder to the main folder
cp -R $SCRIPT_DIR/$EXTRACT_FOLDER/* $SCRIPT_DIR/

# Delete zip file
rm $SCRIPT_DIR/$TAG.zip

# Delete Extract Folder
rm -rf $SCRIPT_DIR/$EXTRACT_FOLDER

# Make all shell scripts executable
chmod a+x $SCRIPT_DIR/*.sh

#install the service
$SCRIPT_DIR/install.sh

#restart the service
$SCRIPT_DIR/restart.sh

