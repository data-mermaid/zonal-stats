FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by rasterio
RUN apt-get update && apt-get install -y \
    libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/
 
# Install Python dependencies
RUN pip install --no-cache-dir .

# Pre-install DuckDB extensions (so LOAD works without network at runtime)
RUN python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL spatial'); conn.execute('INSTALL httpfs'); conn.close()"

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 