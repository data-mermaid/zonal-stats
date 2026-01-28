# Getting Started

## Request Anatomy

Every request has three parts:

1. **`aoi`** -- a GeoJSON Point or Polygon defining your area of interest
2. **Data source** -- a `url` (and optionally `asset` for STAC endpoints)
3. **Options** -- `bands`/`columns`, `stats`, `approx_stats`

If you omit `stats`, the API returns **min, max, mean, count** by default. `aoi_area` and `data_area` are always included.

## First Request

=== "Raster"

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

    Response keys are `band_1`, `band_2`, etc.

=== "Vector"

    ```bash
    curl -X POST "http://localhost:8000/api/v1/zonal-stats/vector" \
      -H "Content-Type: application/json" \
      -d '{
        "aoi": {
          "type": "Polygon",
          "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
        },
        "url": "https://example.com/data.parquet",
        "columns": ["population", "income"]
      }'
    ```

    Response keys match your column names.

## Point Geometries

Points behave differently depending on whether you include a `radius`:

=== "No radius (pixel sample)"

    ```json
    {
      "aoi": {
        "type": "Point",
        "coordinates": [-0.13, 51.51]
      },
      "url": "https://example.com/data.tif",
      "bands": [1]
    }
    ```

    For raster: samples the single pixel under the point. For vector: uses `touch` mode (unweighted stats on features at that point).

=== "With radius (buffered)"

    ```json
    {
      "aoi": {
        "type": "Point",
        "coordinates": [-0.13, 51.51],
        "radius": 500
      },
      "url": "https://example.com/data.tif",
      "bands": [1]
    }
    ```

    The point is buffered into a polygon using the specified radius in meters. Behaves like a polygon request from that point on.

## Defaults

| Field | Default |
|-------|---------|
| `bands` | `[1]` |
| `stats` | `["min", "max", "mean", "count"]` |
| `approx_stats` | `false` |
| `geometry_column` | `"geometry"` (vector only) |
