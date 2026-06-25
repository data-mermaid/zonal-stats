# Statistics

## Default Statistics

If you omit `stats` from your request, you get:

| Stat | Description |
|------|-------------|
| `min` | Minimum value |
| `max` | Maximum value |
| `mean` | Mean value (weighted for vector `intersect` mode, see [weighting methods](intersection-modes.md#weighting-methods)) |
| `count` | Number of pixels (raster) or features (vector) |

## Always Included

These are present in every response regardless of your `stats` selection:

| Stat | Description |
|------|-------------|
| `aoi_area` | Area of your AOI in square meters |
| `data_area` | Area of data within the AOI in square meters |

## No Data Within the AOI

Statistics are `null` whenever the AOI captures no valid data. This happens in two cases:

- The AOI falls entirely **outside the raster's extent**.
- The AOI is **within the raster's extent but covers only masked (nodata) pixels**.

In both cases the numeric stats (`min`, `max`, `mean`, `count`, etc.) are returned as `null` rather than as zeros, so an empty result is distinguishable from a real data value of `0`.

!!! note "`aoi_area` is always reported"
    `aoi_area` describes your query geometry, not the data, so it is returned even when every statistic is `null`. `data_area` is `null` (or `0`) in this case, since no valid data was found.

## Compatibility Matrix

| Stat | Raster | Vector | Notes |
|------|--------|--------|-------|
| `min` | Yes | Yes | Unweighted |
| `max` | Yes | Yes | Unweighted |
| `mean` | Yes | Yes | Weighted in vector `intersect` mode (see [weighting methods](intersection-modes.md#weighting-methods)) |
| `count` | Yes | Yes | Pixels (raster) or features (vector), unweighted |
| `sum` | Yes | Yes | Weighted in vector `intersect` mode |
| `std` | Yes | Yes | Standard deviation, weighted in vector `intersect` mode |
| `median` | Yes | Yes | Unweighted |
| `majority` | Yes | No | Most common value (raster only) |
| `minority` | Yes | No | Least common value (raster only) |
| `unique` | Yes | Yes | List of unique values |
| `range` | Yes | Yes | max - min, unweighted |
| `nodata` | Yes | No | Count of nodata pixels (raster only) |
| `freq_hist` | Yes | No | Value frequency histogram (raster only) |
| `density` | No | Yes | Features per km&sup2; of AOI (vector only) |

!!! warning "Incompatible stats are silently dropped"
    Requesting a raster-only stat (e.g., `freq_hist`) on a vector endpoint will not cause an error -- it is silently removed from the computation.
