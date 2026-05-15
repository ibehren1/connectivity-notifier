#!/bin/bash
# Script to run Docker build.

# Internal registry for publishing dev builds.
INTERNAL_REG="registry.internal.behrenshome.com"


#
# Set some colors.
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'


# Read the version number.
VERSION=$(uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
echo -e "\n${CYAN}Building version: ${VERSION}${NC}\n"


#
# Run Docker Build and Publish
echo -e "\n${CYAN}#\n# Running Dockerbuild.${NC}\n"

# Set the Docker Hub username and password
docker login -u ${DOCKER_USER} -p ${DOCKER_PAT}

# Build images for ARM64 and AMD64.
docker buildx create \
    --use \
    --platform=linux/arm64,linux/amd64 \
    --name multi-platform-builder

docker buildx inspect \
    --bootstrap

docker buildx build -f docker/Dockerfile \
    --platform=linux/arm64,linux/amd64 \
    --no-cache \
    --push \
    --tag ${DOCKER_USER}/connectivity-notifier:${VERSION} \
    --tag ${DOCKER_USER}/connectivity-notifier:latest \
    --tag ${INTERNAL_REG}/connectivity-notifier:${VERSION} \
    --tag ${INTERNAL_REG}/connectivity-notifier:latest .

echo -e "\n${GREEN}Build of ${VERSION} completed.${NC}"

exit 0
