# Intersection Modes

Vector endpoints use one of two intersection modes, **automatically determined** by your AOI geometry.

## Modes

### `intersect` (area-weighted)

Used for **polygons** and **points with radius > 0**.

Features are clipped to the AOI, and statistics are weighted based on the `weighting_method` parameter.

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

## Weighting Methods

When using `intersect` mode, you can choose how features are weighted using the `weighting_method` parameter:

### `area` (default)

Standard areal interpolation. Features are weighted by their **intersection area**:

```
weight = intersection_area
```

Larger clipped areas contribute more to the result. This is the standard approach used in GIS for area-weighted statistics.

**Use when:**

- Values represent densities, rates, or intensive properties (e.g., temperature, species density per km²)
- You want larger areas within your AOI to have more influence
- Working with habitat zones, environmental regions, or coverage data

**Example:**

| Feature | Value | Intersection Area | Weight |
|---------|-------|-------------------|--------|
| A | 87 | 283,722,930 m² | 283,722,930 |
| B | 323 | 551,934,911 m² | 551,934,911 |

```
mean = (87 × 283,722,930 + 323 × 551,934,911) / (283,722,930 + 551,934,911)
     = 242.88
```

### `ratio`

Features are weighted by the **proportion of the feature** that falls inside the AOI:

```
weight = intersection_area / feature_area
```

Each feature has a base weight of 1.0, scaled by how much of it is captured.

**Use when:**

- Features represent discrete entities (e.g., individual parcels, buildings)
- You want each feature to contribute proportionally to its coverage
- A feature that's 50% inside the AOI should contribute half as much as one fully inside

**Example:**

| Feature | Value | Feature Area | Intersection Area | Weight |
|---------|-------|--------------|-------------------|--------|
| A | 87 | 1,497,409,128 m² | 283,722,930 m² | 0.189 |
| B | 323 | 1,664,686,543 m² | 551,934,911 m² | 0.332 |

```
mean = (87 × 0.189 + 323 × 0.332) / (0.189 + 0.332)
     = 237.20
```

## Request Example

```json
{
  "aoi": {
    "type": "Polygon",
    "coordinates": [[[-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52], [-0.16, 51.5]]]
  },
  "url": "https://example.com/data.parquet",
  "columns": ["population_density"],
  "weighting_method": "area"
}
```

!!! note
    The `weighting_method` parameter only applies to **vector** endpoints in `intersect` mode. It has no effect on `touch` mode or raster endpoints.
