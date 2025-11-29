#!/bin/bash

# Script to publish nextdns-monitor to GitHub Container Registry

set -e

# Configuration
GITHUB_USERNAME="nattyboyme3"
IMAGE_NAME="nextdns-monitor"
REGISTRY="ghcr.io"
FULL_IMAGE_NAME="${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}"

# Get version tag (use git tag, commit hash, or "latest")
if [ -n "$1" ]; then
    VERSION="$1"
else
    # Try to get the latest git tag, otherwise use commit hash
    VERSION=$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)
fi

echo "Building Docker image..."
docker build -t "${IMAGE_NAME}:${VERSION}" .

echo "Tagging image for GitHub Container Registry..."
docker tag "${IMAGE_NAME}:${VERSION}" "${FULL_IMAGE_NAME}:${VERSION}"
docker tag "${IMAGE_NAME}:${VERSION}" "${FULL_IMAGE_NAME}:latest"

echo ""
echo "Ready to push to ${FULL_IMAGE_NAME}"
echo "Version: ${VERSION}"
echo ""
echo "To push the image, you need to:"
echo "1. Create a GitHub Personal Access Token (PAT) with 'write:packages' permission"
echo "   Visit: https://github.com/settings/tokens/new"
echo ""
echo "2. Login to GitHub Container Registry:"
echo "   echo \$GITHUB_TOKEN | docker login ghcr.io -u ${GITHUB_USERNAME} --password-stdin"
echo ""
echo "3. Run this script with the --push flag:"
echo "   $0 ${VERSION} --push"
echo ""

# Check if --push flag is provided
if [ "$2" = "--push" ] || [ "$1" = "--push" ]; then
    echo "Pushing images to GitHub Container Registry..."
    docker push "${FULL_IMAGE_NAME}:${VERSION}"
    docker push "${FULL_IMAGE_NAME}:latest"
    echo ""
    echo "Successfully pushed:"
    echo "  - ${FULL_IMAGE_NAME}:${VERSION}"
    echo "  - ${FULL_IMAGE_NAME}:latest"
    echo ""
    echo "Your image is now available at:"
    echo "  docker pull ${FULL_IMAGE_NAME}:latest"
else
    echo "Images built and tagged locally. Add --push to publish."
fi
