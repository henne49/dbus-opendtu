FROM mcr.microsoft.com/vscode/devcontainers/python:3
RUN pip install requests

# Switch to the vscode user
USER vscode

WORKDIR /home/vscode

# Update and install dependencies in a single RUN command to reduce image layers
RUN wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh && \
    chmod +x ./dotnet-install.sh && \
    ./dotnet-install.sh --version latest && \
    rm dotnet-install.sh 

# Install GitVersion
RUN /home/vscode/.dotnet/dotnet tool install --global GitVersion.Tool --version 5.* && \
    echo 'export DOTNET_ROOT=$HOME/.dotnet' >> ~/.bashrc && \
    echo 'export PATH=$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools' >> ~/.bashrc
