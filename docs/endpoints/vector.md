# Vector (GeoParquet)

```
POST /api/v1/zonal-stats/vector
```

Calculate zonal statistics from a GeoParquet file.

## Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `aoi` | `PointGeometry` or `PolygonGeometry` | Yes | -- | GeoJSON geometry (WGS84). Points support optional `radius` in meters. See [Geometries](../concepts/geometries.md) |
| `url` | `string` | Yes | -- | URL to a GeoParquet file (`.parquet` or `.geoparquet`). Protocols: `http://`, `https://`, `s3://`, `file://` |
| `columns` | `string[]` | Yes | -- | Numeric columns to compute statistics on (min 1) |
| `geometry_column` | `string` | No | `"geometry"` | Name of the geometry column in the file |
| `stats` | `string[]` | No | `["min","max","mean","count"]` | Statistics to compute. See [Statistics](../concepts/statistics.md) for all options |
| `weighting_method` | `string` | No | `"area"` | Weighting method for `intersect` mode: `"area"` or `"ratio"`. See [weighting methods](../concepts/intersection-modes.md#weighting-methods) |
| `approx_stats` | `boolean` | No | `false` | Reserved for future use |

## Response

Keys match the requested column names.

```json
{
  "population": {
    "min": 1000,
    "max": 500000,
    "mean": 125000.5,
    "count": 42,
    "aoi_area": 50000000.0,
    "data_area": 45000000.0
  }
}
```

## Intersection Mode

The intersection mode is **automatically determined** by your AOI geometry:

| AOI Type | Mode | Behavior |
|----------|------|----------|
| Point (no radius or radius=0) | `touch` | Unweighted stats on features at the point |
| Point (radius > 0) | `intersect` | Area-weighted stats within the buffered circle |
| Polygon | `intersect` | Area-weighted stats within the polygon |

See [Intersection Modes](../concepts/intersection-modes.md) for details.

## Examples

=== "Polygon AOI"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/vector" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
        },
        "url": "https://example.com/data.parquet",
        "columns": ["population", "income"],
        "stats": ["min", "max", "mean", "sum", "density"]
      }'
    ```

=== "Point with radius"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/vector" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Point",
          "coordinates": [-0.13, 51.51],
          "radius": 1000
        },
        "url": "https://example.com/data.parquet",
        "columns": ["population"]
      }'
    ```

=== "Bare point (touch mode)"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/vector" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Point",
          "coordinates": [-0.13, 51.51]
        },
        "url": "https://example.com/data.parquet",
        "columns": ["population"]
      }'
    ```

    Returns unweighted stats for features that touch the point.

!!! warning "GeoParquet only"
    Only `.parquet` and `.geoparquet` files are supported. Other formats return HTTP 415.

!!! info "Column validation"
    All requested columns must exist in the file and be numeric types (integer, float, decimal). Non-numeric columns will be rejected.
