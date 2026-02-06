# Errors

## Response Format

All errors return a JSON object with a `detail` field:

```json
{
  "detail": "Description of what went wrong"
}
```

Validation errors (422) include a list of issues:

```json
{
  "detail": [
    {
      "loc": ["body", "aoi", "coordinates"],
      "msg": "Polygon ring must have at least 3 points",
      "type": "value_error"
    }
  ]
}
```

## Error Types

| HTTP Code | Error Type | When It Occurs |
|-----------|-----------|----------------|
| 400 | `GeometryError` | Invalid geometry: unclosed ring, fewer than 3 points, coordinates out of range, invalid topology |
| 400 | `RasterError` | Raster I/O failure, pixel count exceeded, band not found |
| 400 | `VectorError` | Column not found, no valid numeric columns among requested, DuckDB query failure |
| 400 | `STACError` | STAC item fetch failed, asset not found, missing href |
| 415 | `UnsupportedMediaTypeError` | File is not GeoParquet (vector endpoints only) |
| 422 | `ValidationError` | Request body fails Pydantic validation |
| 500 | Internal Server Error | Unexpected errors |

## Examples

**Invalid geometry:**
```json
{
  "detail": "Polygon ring must be closed (first and last coordinates must match)"
}
```

**Area limit exceeded:**
```json
{
  "detail": "AOI area exceeds maximum of 1000000 km²"
}
```

**Unsupported format:**
```json
{
  "detail": "Only GeoParquet files are supported. Received: .geojson"
}
```

**STAC asset not found:**
```json
{
  "detail": "Asset 'visual' not found in STAC item"
}
```
