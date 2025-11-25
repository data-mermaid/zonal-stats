# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A FastAPI application that calculates zonal statistics from raster data (Cloud Optimized GeoTIFFs) using GeoJSON geometries. Designed to run on AWS Lambda.

**Stack:** FastAPI, Rasterio, Rasterstats, Shapely, Pydantic, Docker, Mangum (Lambda adapter)

## Development Commands

### Local Development

**Setup:**
```bash
# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

**Run development server:**
```bash
# With uv
uv run uvicorn app.main:app --reload --host 0.0.0.0

# Standard
uvicorn app.main:app --reload --host 0.0.0.0  

# API will be available at http://localhost:8000
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_zonal_stats.py

# Run specific test
pytest tests/test_api_endpoints.py::test_zonal_stats_with_cog
```

**Test configuration:** `pyproject.toml` sets `pythonpath = ["src"]`

### Code Quality

```bash
# Install pre-commit hooks
pre-commit install

# Run linting and formatting manually
pre-commit run --all-files

# Ruff is used for linting and formatting
ruff check .
ruff format .
```

**Ruff configuration** in `pyproject.toml`:
- Line length: 88
- Selected rules: D103 (missing docstrings), E/F (errors), UP (pyupgrade), B (bugbear), SIM (simplify), I (isort)

### Docker

```bash
# Build image
docker build -t zonal-stats-api .

# Run container
docker run -p 8000:8000 zonal-stats-api
```

### AWS Lambda Deployment

See `infrastructure/README.md` for CDK deployment instructions. Key steps:
1. Create Lambda layer: `cd infrastructure && ./build_layer.sh`
2. Deploy with CDK: `cdk deploy`

The Lambda handler is created via Mangum in `src/app/main.py:71`.

## Architecture

### Project Structure

```
src/app/
├── main.py                    # FastAPI app, CORS, exception handlers, Lambda handler
├── api/
│   └── endpoints.py           # POST /api/v1/zonal-stats endpoint
├── models/
│   └── schemas.py             # Pydantic models for request/response validation
└── services/
    └── zonal_stats.py         # Core zonal statistics calculation logic

tests/                         # Pytest test suite
infrastructure/                # AWS CDK deployment code
```

### Key Components

**1. Geometry Handling (`schemas.py`)**

Two geometry types supported:
- `PointGeometry`: Point with buffer in meters (default 0.001m)
- `PolygonGeometry`: Standard GeoJSON polygon

Points are converted to polygons via UTM projection buffering in `zonal_stats.py:42-93`.

**2. Data Sources (`schemas.py`)**

Two mutually exclusive sources:
- `ImageConfig`: Direct COG URL
- `StacConfig`: STAC item URL (asset extracted in `zonal_stats.py:95-129`)

Both support:
- `bands`: List of band indices (default: [1])
- `approx_stats`: Use overviews for performance (default: false)

**3. Statistics Calculation (`zonal_stats.py`)**

`ZonalStatsService` orchestrates the calculation:
- **Geometry preparation:** Validates, transforms to raster CRS
- **Overview selection:** Auto-selects overview level if `approx_stats=true` based on pixel count
- **Band processing:** Reads data, handles nodata, applies scale/offset
- **Stats computation:** Uses rasterstats library for standard stats
- **Custom stats:** Area (square meters), frequency histogram

**Validation limits:**
- Max area: 1M km² (`MAX_AREA_KM2`)
- Max pixels: 100M (`MAX_PIXELS`)

**4. Error Handling**

Custom exception hierarchy:
- `ZonalStatsError` (base)
  - `GeometryError` (geometry validation)
  - `RasterError` (raster I/O, processing)
  - `STACError` (STAC fetching)

All return appropriate HTTP status codes via exception handlers in `main.py`.

**5. Statistics Types (`schemas.py:6-26`)**

Default: min, max, mean, count

Optional: sum, std, median, majority, minority, unique, range, nodata

Special: area (square meters), freq_hist (value frequency distribution)

### Request/Response Flow

1. POST `/api/v1/zonal-stats` with `ZonalStatsRequest`
2. Validate geometry and ensure exactly one source (image or stac)
3. If STAC: fetch item and extract asset URL
4. `ZonalStatsService.calculate_stats()`:
   - Prepare geometry (buffer points, validate polygons)
   - Open raster, transform geometry to raster CRS
   - Calculate window and select overview level
   - For each band: read data, compute stats
5. Return `ZonalStatsResponse`: `{"band_1": {...}, "band_2": {...}}`

### Important Implementation Details

- **CRS transformations:** Input geometries assumed to be WGS84 (EPSG:4326), transformed to raster CRS
- **UTM zone calculation:** For point buffering, automatically selects UTM zone based on longitude
- **Nodata handling:** Raster nodata values converted to NaN before statistics
- **Scale/offset:** Automatically applied from raster metadata if present
- **Small polygons:** Adjusted to ensure at least one pixel of data (`zonal_stats.py:445-461`)
- **Area calculation:** Uses equal-area projection for accurate square meter measurements

## API Documentation

When server is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Dependencies

**Core:** fastapi, uvicorn, pydantic, rasterio, rasterstats, shapely, numpy, pyproj

**AWS:** mangum (Lambda adapter)

**Dev:** pytest, ruff, pre-commit, httpx (for test client)

Managed via `pyproject.toml` with uv for dependency resolution.
