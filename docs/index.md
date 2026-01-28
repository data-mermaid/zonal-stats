# Zonal Statistics API

A FastAPI service that calculates zonal statistics from **raster** (Cloud Optimized GeoTIFF) and **vector** (GeoParquet) data using GeoJSON geometries. Designed for AWS Lambda deployment via Mangum.

## Endpoints

| Method | Path | Data Source |
|--------|------|-------------|
| `POST` | `/api/v1/zonal-stats/raster` | Cloud Optimized GeoTIFF (COG) |
| `POST` | `/api/v1/zonal-stats/raster/stac` | COG via STAC Item |
| `POST` | `/api/v1/zonal-stats/vector` | GeoParquet |
| `POST` | `/api/v1/zonal-stats/vector/stac` | GeoParquet via STAC Item |

## Quick Example

```bash
curl -X POST "http://localhost:8000/api/v1/zonal-stats/raster" \
  -H "Content-Type: application/json" \
  -d '{
    "aoi": {
      "type": "Polygon",
      "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
    },
    "url": "https://example.com/data.tif",
    "bands": [1]
  }'
```

```json
{
  "band_1": {
    "min": 0.5,
    "max": 255.0,
    "mean": 127.3,
    "count": 1000,
    "aoi_area": 50000.0,
    "data_area": 45000.0
  }
}
```

## Next Steps

- [Getting Started](getting-started.md) -- send your first request
- [Endpoints](endpoints/index.md) -- full parameter reference
- Interactive docs at [`/docs`](http://localhost:8000/docs) (Swagger) or [`/redoc`](http://localhost:8000/redoc) (ReDoc) when the server is running
