#!/bin/bash

# Load environment variables from .env file
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi

# Build the Docker image
echo "Building Docker image..."
docker build -t nextdns-monitor .

# Run the container with environment variables from .env
echo "Launching container..."
docker run --rm --env-file .env nextdns-monitor