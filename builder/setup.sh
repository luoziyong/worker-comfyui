#!/bin/bash

# Stop script on error
set -e

# Update System
apt-get update && apt-get upgrade -y

# Install System Dependencies
# - openssh-server: for ssh access and web terminal
apt-get install -y --no-install-recommends software-properties-common curl git wget rsync openssh-server libgl1 libglib2.0-0

# Clean up
apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*
