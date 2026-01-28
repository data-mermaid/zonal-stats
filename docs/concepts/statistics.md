# Statistics

## Default Statistics

If you omit `stats` from your request, you get:

| Stat | Description |
|------|-------------|
| `min` | Minimum value |
| `max` | Maximum value |
| `mean` | Mean value (area-weighted for vector `intersect` mode) |
| `count` | Number of pixels (raster) or features (vector) |

## Always Included

These are present in every response regardless of your `stats` selection:

| Stat | Description |
|------|-------------|
| `aoi_area` | Area of your AOI in square meters |
| `data_area` | Area of data within the AOI in square meters |

## Compatibility Matrix

| Stat | Raster | Vector | Notes |
|------|--------|--------|-------|
| `min` | Yes | Yes | |
| `max` | Yes | Yes | |
| `mean` | Yes | Yes | Area-weighted in vector `intersect` mode |
| `count` | Yes | Yes | Pixels (raster) or features (vector) |
| `sum` | Yes | Yes | Area-weighted in vector `intersect` mode |
| `std` | Yes | Yes | Standard deviation |
| `median` | Yes | Yes | |
| `majority` | Yes | No | Most common value (raster only) |
| `minority` | Yes | No | Least common value (raster only) |
| `unique` | Yes | Yes | Count of unique values (raster) or list of unique values (vector) |
| `range` | Yes | Yes | max - min |
| `nodata` | Yes | No | Count of nodata pixels (raster only) |
| `freq_hist` | Yes | No | Value frequency histogram (raster only) |
| `density` | No | Yes | Features per km&sup2; of AOI (vector only) |

!!! warning "Incompatible stats are silently dropped"
    Requesting a raster-only stat (e.g., `freq_hist`) on a vector endpoint will not cause an error -- it is silently removed from the computation.
