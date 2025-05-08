#!/bin/bash

# Create a temporary directory for building the layer
mkdir -p python

# Install dependencies into the python directory
pip install --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all: -r requirements.txt -t python/

# Create the layer zip file
zip -r lambda_layer.zip python/

# Clean up
rm -rf python/ 