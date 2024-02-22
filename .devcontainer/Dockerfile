FROM mcr.microsoft.com/vscode/devcontainers/python:3
RUN pip install requests

# Install latest dotnet for vscode user
RUN apt update 
WORKDIR /home/vscode
RUN sudo -S -u vscode wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh
RUN sudo -S -u vscode chmod +x ./dotnet-install.sh
RUN sudo -S -u vscode ./dotnet-install.sh --version latest

# Install GitVersion
RUN sudo -S -u vscode /home/vscode/.dotnet/dotnet tool install --global GitVersion.Tool --version 5.*
RUN sudo -S -u vscode echo 'export DOTNET_ROOT=$HOME/.dotnet' >> /home/vscode/.bashrc
RUN sudo -S -u vscode echo 'export PATH=$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools' >> /home/vscode/.bashrc