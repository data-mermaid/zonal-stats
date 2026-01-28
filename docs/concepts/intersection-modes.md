# Intersection Modes

Vector endpoints use one of two intersection modes, **automatically determined** by your AOI geometry.

## Modes

### `intersect` (area-weighted)

Used for **polygons** and **points with radius > 0**.

Features are clipped to the AOI, and statistics are weighted by the ratio of the intersection area to the full feature area:

```
weight = intersection_area / feature_area
```

This means a feature that is only partially inside your AOI contributes proportionally to the result.

### `touch` (unweighted)

Used for **bare points** (no radius, or radius = 0).

All features that spatially touch the point are included with equal weight. No area-based weighting is applied.

## Auto-Detection

| AOI | Mode | Weighting |
|-----|------|-----------|
| Point, no radius | `touch` | Unweighted |
| Point, radius = 0 | `touch` | Unweighted |
| Point, radius > 0 | `intersect` | Area-weighted |
| Polygon | `intersect` | Area-weighted |

!!! note
    The intersection mode only applies to **vector** endpoints. Raster endpoints always use the full pixel value within the AOI window (or a single pixel sample for bare points).
