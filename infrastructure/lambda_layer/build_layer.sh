#!/bin/bash
#
# Build Lambda layer with Python dependencies and DuckDB extensions.
#
# NOTE: DuckDB extensions are platform-specific. For Lambda compatibility,
# this script should be run on Amazon Linux 2 or in a Docker container
# that matches Lambda's runtime (e.g., public.ecr.aws/lambda/python:3.11).
#
# Example using Docker:
#   docker run --rm -v $(pwd):/build -w /build \
#     public.ecr.aws/lambda/python:3.11 \
#     bash lambda_layer/build_layer.sh

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create a temporary directory for building the layer
mkdir -p "$SCRIPT_DIR/python"

# Install dependencies into the python directory
pip install --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all: -r "$SCRIPT_DIR/requirements.txt" -t "$SCRIPT_DIR/python/"

# Pre-install DuckDB extensions so they're available at runtime without network
# Use PYTHONPATH to import from the layer target directory we just populated
echo "Pre-installing DuckDB extensions..."
PYTHONPATH="$SCRIPT_DIR/python" python3 -c "
import duckdb
conn = duckdb.connect()
conn.execute('INSTALL spatial')
conn.execute('INSTALL httpfs')
conn.close()
print('DuckDB extensions installed successfully')
"

# Copy DuckDB extensions to the layer
# DuckDB stores extensions in ~/.duckdb/extensions/<version>/<platform>/
DUCKDB_EXT_DIR="$HOME/.duckdb/extensions"
if [ -d "$DUCKDB_EXT_DIR" ]; then
    mkdir -p "$SCRIPT_DIR/python/.duckdb"
    cp -r "$DUCKDB_EXT_DIR" "$SCRIPT_DIR/python/.duckdb/"
    echo "Copied DuckDB extensions to layer"
else
    echo "Warning: DuckDB extensions directory not found at $DUCKDB_EXT_DIR"
fi

# Create the layer zip file in the lambda_layer directory
cd "$SCRIPT_DIR"
zip -r lambda_layer.zip python/

# Clean up
rm -rf python/

echo "Layer built: $SCRIPT_DIR/lambda_layer.zip" 