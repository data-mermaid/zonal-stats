# Endpoints Overview

All endpoints accept `POST` requests with a JSON body and return JSON.

## Base URL

```
/api/v1/zonal-stats
```

## Common Request Fields

Every request includes:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `aoi` | `PointGeometry` or `PolygonGeometry` | Yes | GeoJSON geometry in WGS84 (EPSG:4326) |
| `stats` | `string[]` | No | Statistics to compute. Default: `["min", "max", "mean", "count"]` |
| `approx_stats` | `boolean` | No | Use overviews for faster approximate results. Default: `false` |

## Response Structure

Responses are JSON objects keyed by band or column name:

=== "Raster"

    ```json
    {
      "band_1": {
        "min": 0.5,
        "max": 255.0,
        "mean": 127.3,
        "count": 1000,
        "aoi_area": 50000.0,
        "data_area": 45000.0
      },
      "band_2": { ... }
    }
    ```

=== "Vector"

    ```json
    {
      "population": {
        "min": 1000,
        "max": 500000,
        "mean": 125000.5,
        "count": 42,
        "aoi_area": 50000000.0,
        "data_area": 45000000.0
      },
      "income": { ... }
    }
    ```

!!! info "Always included"
    `aoi_area` (area of your AOI in m&sup2;) and `data_area` (area of data within the AOI in m&sup2;) are always present in the response regardless of which stats you request.
