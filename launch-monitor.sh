#!/bin/bash

# This script launches a monitoring application with specific configurations.
source ./.venv/bin/activate
python main.py | logger -t nextdns-monitor
