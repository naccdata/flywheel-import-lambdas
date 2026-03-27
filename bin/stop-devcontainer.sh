#!/bin/zsh

if ! command -v devcontainer &> /dev/null; then
    echo "Error: devcontainer command not found"
    echo "Please install the devcontainer CLI: npm install -g @devcontainers/cli"
    exit 1
fi

export DOCKER_CLI_HINTS=false
export WORKSPACE_FOLDER=`pwd`

# Get the container name
CONTAINER_NAME=$(devcontainer exec --workspace-folder $WORKSPACE_FOLDER hostname 2>/dev/null || echo "")

if [ -n "$CONTAINER_NAME" ]; then
    echo "Stopping devcontainer..."
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
    echo "Devcontainer stopped and removed"
else
    echo "No running devcontainer found"
fi