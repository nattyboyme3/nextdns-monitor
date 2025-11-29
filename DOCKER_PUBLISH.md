# Publishing to GitHub Container Registry

This guide explains how to publish the nextdns-monitor Docker image to GitHub Container Registry (ghcr.io).

## Prerequisites

1. **GitHub Personal Access Token (PAT)**
   - Go to https://github.com/settings/tokens/new
   - Give it a descriptive name (e.g., "Docker GHCR Access")
   - Select the following scopes:
     - `write:packages` (Upload packages to GitHub Package Registry)
     - `read:packages` (Download packages from GitHub Package Registry)
     - `delete:packages` (Delete packages from GitHub Package Registry - optional)
   - Click "Generate token"
   - **Save the token securely** - you won't be able to see it again!

2. **Docker installed and running**

## Publishing Steps

### 1. Login to GitHub Container Registry

```bash
# Set your GitHub token as an environment variable
export GITHUB_TOKEN=your_personal_access_token_here

# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u nattyboyme3 --password-stdin
```

### 2. Build and Push the Image

```bash
# Option A: Use the automated script (recommended)
./docker-publish.sh latest --push

# Option B: Use a specific version tag
./docker-publish.sh v1.0.0 --push

# Option C: Use git commit hash (automatic)
./docker-publish.sh --push
```

### 3. Make the Package Public (First Time Only)

After the first push, the package will be private by default. To make it public:

1. Go to https://github.com/nattyboyme3?tab=packages
2. Click on the `nextdns-monitor` package
3. Click "Package settings" (on the right side)
4. Scroll down to "Danger Zone"
5. Click "Change visibility" and select "Public"

## Using the Published Image

Once published, anyone can pull and use your image:

```bash
# Pull the latest version
docker pull ghcr.io/nattyboyme3/nextdns-monitor:latest

# Run the container with your .env file
docker run --rm --env-file .env ghcr.io/nattyboyme3/nextdns-monitor:latest

# Or use a specific version
docker pull ghcr.io/nattyboyme3/nextdns-monitor:v1.0.0
```

## Updating docker-launch.sh to Use Published Image

You can modify `docker-launch.sh` to use the published image instead of building locally:

```bash
#!/bin/bash

# Load environment variables from .env file
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi

# Pull the latest image
echo "Pulling latest image from GitHub Container Registry..."
docker pull ghcr.io/nattyboyme3/nextdns-monitor:latest

# Run the container with environment variables from .env
echo "Launching container..."
docker run --rm --env-file .env ghcr.io/nattyboyme3/nextdns-monitor:latest
```

## Automation with GitHub Actions

You can automate image publishing using GitHub Actions. Create `.github/workflows/docker-publish.yml`:

```yaml
name: Publish Docker Image

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  release:
    types: [ published ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Log in to the Container registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata (tags, labels) for Docker
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

This will automatically build and publish your Docker image whenever you push to main or create a new release/tag.

## Troubleshooting

### Authentication Failed
- Ensure your PAT has the correct permissions
- Check that you're logged in: `docker login ghcr.io`
- Try logging out and back in: `docker logout ghcr.io` then login again

### Package Not Found
- Make sure the package visibility is set to "Public"
- Check the exact image name: `ghcr.io/nattyboyme3/nextdns-monitor`

### Build Fails
- Ensure all files (main.py, nextdns_logs.py, requirements.txt) are present
- Check that the Dockerfile is valid: `docker build -t test .`