# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A FastAPI application that calculates zonal statistics from raster and vector data using GeoJSON geometries. Supports Cloud Optimized GeoTIFFs (COG) for raster and GeoParquet for vector data. Designed to run on AWS Lambda.

**Stack:** FastAPI, Rasterio, Rasterstats, DuckDB, Shapely, Pydantic, Docker, Mangum (Lambda adapter)

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
pytest tests/test_raster_endpoints.py
pytest tests/test_vector_endpoints.py

# Run specific test
pytest tests/test_raster_endpoints.py::test_raster_stats_basic
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
# Local development with hot-reload
docker compose up api

# Test Lambda locally with Runtime Interface Emulator
docker compose up lambda
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"httpMethod": "GET", "path": "/docs"}'
```

### AWS Lambda Deployment

See `infrastructure/README.md` for CDK deployment instructions. Key steps:
1. Ensure Docker is running
2. Deploy with CDK: `cd infrastructure && cdk deploy`

CDK builds the Docker image from `Dockerfile.lambda`, pushes to ECR, and updates Lambda automatically.

The Lambda handler is created via Mangum in `src/app/main.py`.

## Architecture

### API Endpoints (v0.2.0)

```
POST /api/v1/zonal-stats/raster        # Stats from Cloud Optimized GeoTIFF
POST /api/v1/zonal-stats/raster/stac   # Stats from STAC raster asset
POST /api/v1/zonal-stats/vector        # Stats from GeoParquet
POST /api/v1/zonal-stats/vector/stac   # Stats from STAC vector asset
```

### Project Structure

```
src/app/
├── main.py                    # FastAPI app, CORS, exception handlers, Lambda handler
├── api/
│   └── endpoints.py           # Four focused endpoints with sub-routers
├── models/
│   └── schemas.py             # Pydantic models for request/response validation
└── services/
    ├── zonal_stats.py         # Raster statistics calculation (ZonalStatsService)
    ├── zonal_vector.py        # Vector statistics calculation (ZonalVectorService)
    └── stac.py                # STAC item fetching and asset extraction

tests/
├── test_raster_endpoints.py   # Raster endpoint tests
├── test_vector_endpoints.py   # Vector endpoint tests
├── test_stac_integration.py   # STAC integration tests
├── test_zonal_stats.py        # ZonalStatsService unit tests
├── test_vector_stats.py       # ZonalVectorService unit tests
└── data/                      # Test data files
```

### Key Components

**1. Geometry Handling (`schemas.py`)**

Two geometry types supported:
- `PointGeometry`: Point with optional `radius` in meters (default `None`)
- `PolygonGeometry`: Standard GeoJSON polygon

**2. Request Models (`schemas.py`)**

Four focused request models (one per endpoint):
- `RasterStatsRequest`: Direct COG URL + bands + approx_stats
- `RasterStacStatsRequest`: STAC URL + asset + bands + approx_stats
- `VectorStatsRequest`: GeoParquet URL + columns
- `VectorStacStatsRequest`: STAC URL + asset + columns

**3. Raster Statistics (`zonal_stats.py`)**

`ZonalStatsService` orchestrates raster calculation:
- **Geometry preparation:** Validates, transforms to raster CRS
- **Overview selection:** Auto-selects overview level if `approx_stats=true`
- **Band processing:** Reads data, handles nodata, applies scale/offset
- **Stats computation:** Uses rasterstats library for standard stats

**4. Vector Statistics (`zonal_vector.py`)**

`ZonalVectorService` uses DuckDB with spatial extension:
- **Intersection mode auto-detection** (determined by geometry type in `endpoints.py`):
  - Point with no radius or `radius=0`: `touch` mode (raw point, unweighted stats)
  - Point with `radius > 0`: `intersect` mode (buffered to polygon, area-weighted)
  - Polygon: `intersect` mode (area-weighted stats)
- **Weighting method** (`weighting_method` parameter, default `area`):
  - `area`: Standard areal interpolation (weight = intersection_area). Larger areas contribute more.
  - `ratio`: Proportional weighting (weight = intersection_area / feature_area). Each feature contributes proportionally to how much is captured.
- **CRS handling:** Reads CRS from GeoParquet metadata
- **File format:** Only GeoParquet supported (HTTP 415 for other formats)

**5. STAC Support (`stac.py`)**

- `get_asset_url()`: Fetches STAC item and extracts asset href
- `validate_vector_asset()`: Validates asset is GeoParquet

**6. Error Handling**

Custom exception hierarchy:
- `ZonalStatsError` (base)
  - `GeometryError` (geometry validation)
  - `RasterError` (raster I/O)
  - `STACError` (STAC fetching)
  - `VectorError` (vector data operations)
  - `UnsupportedMediaTypeError` (HTTP 415 for unsupported formats)

**7. Statistics Types (`schemas.py`)**

Default: min, max, mean, count

Optional: sum, std, median, majority, minority, unique, range, nodata

Special:
- `aoi_area`: Area of the query AOI in square meters (always included)
- `data_area`: Area of data within AOI (always included)
- `freq_hist`: Value frequency histogram (raster only)
- `density`: Features per km² of AOI (vector only)

### Example Requests

**Raster (COG):**
```bash
curl -X POST "http://localhost:8000/api/v1/zonal-stats/raster" \
  -H "Content-Type: application/json" \
  -d '{
    "aoi": {"type": "Polygon", "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]},
    "url": "https://example.com/data.tif",
    "bands": [1, 2],
    "stats": ["min", "max", "mean", "std"]
  }'
```

**Vector (GeoParquet):**
```bash
curl -X POST "http://localhost:8000/api/v1/zonal-stats/vector" \
  -H "Content-Type: application/json" \
  -d '{
    "aoi": {"type": "Polygon", "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]},
    "url": "https://example.com/data.parquet",
    "columns": ["population", "income"]
  }'
```

## API Documentation

When server is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Dependencies

**Core:** fastapi, uvicorn, pydantic, rasterio, rasterstats, duckdb, shapely, numpy, pyproj

**AWS:** mangum (Lambda adapter)

**Dev:** pytest, ruff, pre-commit, httpx (for test client)

Managed via `pyproject.toml` with uv for dependency resolution.
