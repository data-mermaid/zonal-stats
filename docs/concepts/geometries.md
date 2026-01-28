# Geometries

All geometries are specified in **WGS84 (EPSG:4326)** with coordinates in `[longitude, latitude]` order.

## Point Geometry

```json
{
  "type": "Point",
  "coordinates": [-0.13, 51.51],
  "radius": 500
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"Point"` | Yes | Fixed value |
| `coordinates` | `[lon, lat]` | Yes | Longitude (-180 to 180), latitude (-90 to 90) |
| `radius` | `float` | No | Buffer radius in meters. Must be non-negative |

### Point Behaviors

How a point is handled depends on `radius`:

| Radius | Raster Behavior | Vector Behavior |
|--------|----------------|-----------------|
| Omitted or `null` | Samples the single pixel under the point | `touch` mode: unweighted stats on features at the point |
| `0` | Samples the single pixel under the point | `touch` mode: unweighted stats on features at the point |
| `> 0` | Buffers to polygon, runs zonal stats | `intersect` mode: area-weighted stats within the circle |

!!! note "Buffering"
    The buffer is computed in the appropriate UTM zone for the point's location, then transformed back to WGS84. This ensures accurate circular buffers in meters.

## Polygon Geometry

```json
{
  "type": "Polygon",
  "coordinates": [
    [[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"Polygon"` | Yes | Fixed value |
| `coordinates` | `float[][][]` | Yes | Array of linear rings. Outer ring required, holes optional |

### Rules

- At least **3 distinct points** per ring
- The ring must be **closed** -- the first and last coordinate must be identical
- Polygons always use `intersect` mode for vector queries (area-weighted)
