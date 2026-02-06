# Raster (STAC)

```
POST /api/v1/zonal-stats/raster/stac
```

Calculate zonal statistics from a raster asset referenced by a STAC Item.

## Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `aoi` | `PointGeometry` or `PolygonGeometry` | Yes | -- | GeoJSON geometry (WGS84). Points support optional `radius` in meters. See [Geometries](../concepts/geometries.md) |
| `url` | `string` | Yes | -- | URL to a STAC Item JSON. Protocols: `http://`, `https://` only |
| `asset` | `string` | No | first asset | Key of the asset to use |
| `bands` | `int[]` | No | `[1]` | Band indices (1-based) |
| `stats` | `string[]` | No | `["min","max","mean","count"]` | Statistics to compute. See [Statistics](../concepts/statistics.md) for all options |
| `approx_stats` | `boolean` | No | `false` | Use raster overviews for faster approximate results |

## Response

Same format as the [direct raster endpoint](raster.md) -- keys are `band_1`, `band_2`, etc.

## Examples

=== "Specific asset"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/raster/stac" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
        },
        "url": "https://stac-catalog.example.com/items/scene-123",
        "asset": "visual",
        "bands": [1, 2, 3]
      }'
    ```

=== "First asset (default)"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/raster/stac" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
        },
        "url": "https://stac-catalog.example.com/items/scene-123"
      }'
    ```

    Omitting `asset` uses the first asset in the STAC Item.

!!! warning "STAC URLs"
    Only `http://` and `https://` URLs are accepted for STAC endpoints. `s3://` and `file://` are not supported.
