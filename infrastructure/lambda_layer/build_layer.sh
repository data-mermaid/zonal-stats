#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create a temporary directory for building the layer
mkdir -p "$SCRIPT_DIR/python"

# Install dependencies into the python directory
pip install --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all: -r "$SCRIPT_DIR/requirements.txt" -t "$SCRIPT_DIR/python/"

# Create the layer zip file in the lambda_layer directory
cd "$SCRIPT_DIR"
zip -r lambda_layer.zip python/

# Clean up
rm -rf python/ 