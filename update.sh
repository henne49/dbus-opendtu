# Set the repository name and username
REPO="henne49/dbus-opendtu"
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

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
echo "Enter the version to download (e.g. main, v1.2.25, pre-release, or press enter for latest):"
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

# Download the zip file for the specified tag
wget -O $TAG.zip https://github.com/$REPO/archive/$TAG.zip || { echo "version does not exist"; exit 1; }

# Unzip the downloaded file
unzip $TAG.zip

# Check if the TAG string starts with 'v'
if [[ $TAG =~ ^v ]]; then
  # If it starts with 'v', remove the first character and return the result
  EXTRACT_FOLDER="dbus-opendtu-${TAG:1}"
else
  EXTRACT_FOLDER="dbus-opendtu-$TAG"
fi

echo $EXTRACT_FOLDER

# Copy all files from the extract folder to the main folder
cp -R $EXTRACT_FOLDER/* .

# Delete zip file
rm $TAG.zip

# Delete Extract Folder
rm -rf $EXTRACT_FOLDER

# Make all shell scripts executable
chmod a+x $SCRIPT_DIR//*.sh

#restart the service
$SCRIPT_DIR/restart.sh

#install the service
$SCRIPT_DIR/install.sh