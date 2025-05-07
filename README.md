# Zonal Statistics API

A FastAPI application that calculates zonal statistics from raster data using GeoJSON geometries.

> For the initial requirements and specifications, see [specs.md](specs.md)

## Features

- Calculate zonal statistics (min, max, mean, count, sum, std, median, majority, minority, unique, range, nodata, area, freq_hist)
- Support for COG (Cloud Optimized GeoTIFF) raster data
- Input validation using Pydantic models
- Docker containerization for easy deployment
- AWS Lambda compatible

## API Endpoints

### POST /api/v1/zonal-stats

Calculate zonal statistics for a given area of interest and raster data.

#### Request Body

```json
{
  "aoi": {
    "type": "Polygon",
    "coordinates": [[[x1, y1], [x2, y2], ...]]
  },
  "stats": ["min", "max", "mean", "count", "sum", "std", "median", "majority", "minority", "unique", "range", "nodata", "area", "freq_hist"],  // optional
  "image": {
    "url": "https://example.com/image.tif",
    "bands": [1],  // optional
    "approx_stats": true  // optional
  }
}
```

#### Response

```json
{
  "band_1": {
    "min": 10.0,
    "max": 50.0,
    "mean": 25.5,
    "count": 100,
    "sum": 2550.0,
    "std": 5.2,
    "median": 25.0,
    "majority": 24.0,
    "minority": 11.0,
    "unique": 15,
    "range": 40.0,
    "nodata": 0,
    "area": 1000.0,
    "freq_hist": { ... }
  }
}
```

## Development

### Prerequisites

- Python 3.10+
- Docker (for containerized deployment)
- uv (recommended for dependency management)

### Local Development

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
   ```

2. Install dependencies:

   ```bash
   pip install -e .
   ```

3. Run the development server:

   ```bash
   uvicorn app.main:app --reload
   ```

### Docker Deployment

1. Build the Docker image:

   ```bash
   docker build -t zonal-stats-api .
   ```

2. Run the container:

   ```bash
   docker run -p 8000:8000 zonal-stats-api
   ```

## Development Tools

The project uses several development tools to maintain code quality:

- `ruff` for linting and formatting
- `pre-commit` for git hooks
- `pytest` for testing

To set up the development tools:

```bash
# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## API Documentation

Once the server is running, you can access:

- Swagger UI documentation at `/docs`
- ReDoc documentation at `/redoc`

## License

MIT
