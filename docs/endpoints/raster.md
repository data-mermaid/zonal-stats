# Raster (COG)

```
POST /api/v1/zonal-stats/raster
```

Calculate zonal statistics from a Cloud Optimized GeoTIFF.

## Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `aoi` | `PointGeometry` or `PolygonGeometry` | Yes | -- | GeoJSON geometry (WGS84) |
| `url` | `string` | Yes | -- | URL to a COG. Protocols: `http://`, `https://`, `s3://`, `file://` |
| `bands` | `int[]` | No | `[1]` | Band indices (1-based) |
| `stats` | `string[]` | No | `["min","max","mean","count"]` | Statistics to compute |
| `approx_stats` | `boolean` | No | `false` | Use raster overviews for faster approximate results |

## Response

Keys are `band_1`, `band_2`, etc. matching the requested bands.

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

## Examples

=== "Polygon AOI"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/raster" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
        },
        "url": "https://example.com/data.tif",
        "bands": [1, 2],
        "stats": ["min", "max", "mean", "std"]
      }'
    ```

=== "Point sample (no radius)"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/raster" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Point",
          "coordinates": [-0.13, 51.51]
        },
        "url": "https://example.com/data.tif"
      }'
    ```

    Returns the single pixel value under the point.

=== "Approximate stats"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/raster" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-10, 40], [10, 40], [10, 60], [-10, 60], [-10, 40]]]
        },
        "url": "https://example.com/large.tif",
        "approx_stats": true
      }'
    ```

    Bypasses area and pixel limits by reading from raster overviews.

!!! note "Scale and offset"
    If the raster contains scale/offset metadata, values are automatically adjusted before statistics are calculated.
