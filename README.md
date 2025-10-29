# Zonal Statistics API

A FastAPI application that calculates zonal statistics from raster data using GeoJSON geometries.

> For the initial requirements and specifications, see [specs.md](specs.md)

## Features

- Calculate zonal statistics (min, max, mean, count, sum, std, median, majority, minority, unique, range, nodata, area, freq_hist)
- Support for COG (Cloud Optimized GeoTIFF) raster data
- Support for STAC (SpatioTemporal Asset Catalog) items
- Optional approximate statistics using overviews for better performance
- Input validation using Pydantic models
- Docker containerization for easy deployment
- AWS Lambda compatible
- Support for both polygon and point geometries (with buffer)

## API Endpoints

### POST /api/v1/zonal-stats

Calculate zonal statistics for a given area of interest and raster data.

#### Request Body

You can provide either an image URL or a STAC item URL, but not both. The area of interest (aoi) can be either a polygon or a point with buffer:

Using a polygon:

```json
{
  "aoi": {
    "type": "Polygon",
    "coordinates": [[[x1, y1], [x2, y2], ...]]
  },
  "stats": ["min", "max", "mean", "count", "sum", "std", "median", "majority", "minority", "unique", "range", "nodata", "area", "freq_hist"],  // optional
  "image": {
    "url": "https://example.com/image.tif",
    "bands": [1],  // optional, defaults to [1]
    "approx_stats": false  // optional, defaults to false
  }
}
```

Or using a point with buffer:

```json
{
  "aoi": {
    "type": "Point",
    "coordinates": [longitude, latitude],
    "buffer_size": 1000  // buffer size in meters
  },
  "stats": ["min", "max", "mean", "count"],
  "stac": {
    "url": "https://example.com/stac/item.json",
    "asset": "cog",  // optional, defaults to first asset
    "bands": [1, 2, 3],  // optional, defaults to [1]
    "approx_stats": false  // optional, defaults to false
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

## Features in Detail

### Approximate Statistics

When `approx_stats` is set to `true`, the API may use lower-resolution overviews of the raster data to improve performance. This is particularly useful for large areas of interest. The system automatically selects an appropriate overview level based on the size of the area being processed, ensuring a balance between performance and accuracy. By default, `approx_stats` is set to `false` to ensure maximum accuracy.

### STAC Support

The API supports processing data from STAC items. When using a STAC item:

1. Provide the STAC item URL in the `stac.url` field
2. Optionally specify which asset to use in `stac.asset` (defaults to the first asset)
3. Specify which bands to process in `stac.bands` (defaults to band 1)
4. Control approximate statistics with `stac.approx_stats` (defaults to false)

The API will:

1. Fetch the STAC item
2. Extract the asset URL
3. Process the data using the same zonal statistics calculation as direct image URLs

## Development

### Prerequisites

- Python 3.10+
- Docker (for containerized deployment)
- uv (recommended for dependency management)

### Local Development

1. Install dependencies 

```bash
  uv sync
```

2. Run development server:

```bash
  uv run uvicorn app.main:app --reload --host 0.0.0.0
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

### AWS Deployment

For deploying the application to AWS using CDK, see the [Infrastructure README](infrastructure/README.md) for detailed instructions on:

- Setting up the AWS environment
- Creating the Lambda layer
- Deploying the infrastructure
- Testing the deployed API

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
