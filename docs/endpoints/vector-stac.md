# Vector (STAC)

```
POST /api/v1/zonal-stats/vector/stac
```

Calculate zonal statistics from a GeoParquet asset referenced by a STAC Item.

## Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `aoi` | `PointGeometry` or `PolygonGeometry` | Yes | -- | GeoJSON geometry (WGS84) |
| `url` | `string` | Yes | -- | URL to a STAC Item JSON. Protocols: `http://`, `https://` only |
| `asset` | `string` | No | first asset | Key of the asset to use |
| `columns` | `string[]` | Yes | -- | Numeric columns to compute statistics on (min 1) |
| `geometry_column` | `string` | No | `"geometry"` | Name of the geometry column in the file |
| `stats` | `string[]` | No | `["min","max","mean","count"]` | Statistics to compute |
| `weighting_method` | `string` | No | `"area"` | Weighting method for `intersect` mode: `"area"` or `"ratio"`. See [weighting methods](../concepts/intersection-modes.md#weighting-methods) |
| `approx_stats` | `boolean` | No | `false` | Reserved for future use |

## Response

Same format as the [direct vector endpoint](vector.md) -- keys match column names.

## Asset Validation

The STAC asset must be a GeoParquet file. The API validates this by checking:

1. The asset URL extension (`.parquet` or `.geoparquet`)
2. The asset media type (`application/x-parquet`, `application/vnd.apache.parquet`, or `application/geoparquet`)

If neither check passes, the request returns HTTP 415.

## Examples

=== "Specific asset"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/vector/stac" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
        },
        "url": "https://stac-catalog.example.com/items/buildings-uk",
        "asset": "data",
        "columns": ["height", "area"]
      }'
    ```

=== "First asset (default)"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/vector/stac" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
        },
        "url": "https://stac-catalog.example.com/items/buildings-uk",
        "columns": ["height"]
      }'
    ```

!!! warning "STAC URLs"
    Only `http://` and `https://` URLs are accepted. `s3://` and `file://` are not supported for STAC endpoints.
