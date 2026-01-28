# Limits

## Area and Pixel Limits (Raster)

| Limit | Value | Applies When |
|-------|-------|-------------|
| Maximum AOI area | 1,000,000 km&sup2; | `approx_stats = false` |
| Maximum pixel count | 100,000,000 pixels | `approx_stats = false` |

Both limits are **bypassed** when `approx_stats = true`. In that case, the API reads from raster overviews instead of full-resolution data.

!!! tip
    If your request fails with an area or pixel limit error, retry with `"approx_stats": true`. The results will be approximate but cover the full extent.

## Format Constraints

| Endpoint Type | Supported Formats |
|---------------|-------------------|
| Raster | Cloud Optimized GeoTIFF (COG) |
| Vector | GeoParquet (`.parquet`, `.geoparquet`) |

Vector endpoints return HTTP 415 for any non-GeoParquet file.

## URL Protocol Support

| Protocol | Raster | Raster STAC | Vector | Vector STAC |
|----------|--------|-------------|--------|-------------|
| `http://` | Yes | Yes | Yes | Yes |
| `https://` | Yes | Yes | Yes | Yes |
| `s3://` | Yes | No | Yes | No |
| `file://` | Yes | No | Yes | No |

STAC endpoints only accept `http://` and `https://` because the STAC Item itself is fetched over HTTP. The resolved asset URL may point to any protocol the underlying endpoint supports.

## Band Indexing

Raster band indices are **1-based**. `"bands": [1]` reads the first band. Default: `[1]`.

## Coordinate Ranges

| Axis | Range |
|------|-------|
| Longitude | -180 to 180 |
| Latitude | -90 to 90 |
