# Gotchas

Common pitfalls and how to avoid them.

**1. Coordinate order is `[longitude, latitude]`**
GeoJSON uses `[lon, lat]`, not `[lat, lon]`. Swapping them will query the wrong location or fail validation (latitude > 90).

**2. Polygon rings must be closed**
The first and last coordinate in each ring must be identical. The API will reject unclosed rings with a 400 error.

**3. Bare points sample a single pixel (raster)**
A `Point` without `radius` does not run zonal stats -- it samples the one pixel directly under the point. If you want area-based statistics, provide a `radius`.

**4. `aoi_area` is 0 for bare points**
Points have no area. If you need a meaningful `aoi_area`, use a `radius` to buffer the point into a polygon.

**5. Vector endpoints only accept GeoParquet**
Passing a GeoJSON, Shapefile, or any non-Parquet URL to a vector endpoint returns HTTP 415. Convert your data to GeoParquet first.

**6. `geometry_column` is auto-detected but can be overridden**
The geometry column is auto-detected from GeoParquet metadata (`primary_column`), then by trying common names (`geometry`, `geom`, `the_geom`, `wkb_geometry`, `shape`). You only need to set `geometry_column` explicitly if your file uses an unusual name not in that list.

**7. Empty `stats` array is rejected**
`"stats": []` fails validation. Either omit `stats` entirely (to get defaults) or provide at least one stat.

**8. Incompatible stats are silently dropped**
Requesting `freq_hist` on a vector endpoint doesn't error -- it's removed. Requesting `density` on a raster endpoint is also silently ignored. Check the response to confirm which stats were returned.

**9. `approx_stats` requires raster overviews**
If the COG has no overviews, `approx_stats` reads full-resolution data. It still bypasses the area/pixel limit checks, but results will be exact, not approximate.

**10. Area and pixel limits only apply without `approx_stats`**
If your AOI exceeds 1M km&sup2; or 100M pixels, the request fails with a 400 unless you set `"approx_stats": true`.

**11. STAC endpoints only accept HTTP(S) URLs**
`s3://` and `file://` are not valid for the STAC `url` field. The resolved asset href can be any protocol, but the STAC Item itself must be reachable over HTTP.

**12. Vector `mean` is area-weighted in `intersect` mode**
For polygon or buffered-point queries, `mean` is weighted by the intersection area ratio, not a simple average. This is intentional -- a feature half-inside your AOI contributes half its value.

**13. Empty results return `null`, not `0`**
An AOI that falls outside the raster's extent -- or one that lands inside the extent but covers only masked (nodata) pixels -- returns `null` for every statistic. This keeps an empty result distinct from a real value of `0`, but collapses the distinction between `null` cell value and no value at all (undefined). `aoi_area` is still reported, since it describes your query geometry. See [Statistics](concepts/statistics.md#no-data-within-the-aoi).

**14. Raster stats may differ slightly from QGIS/GDAL**

This API uses `rasterstats` with `rasterio.features.rasterize()` for polygon-to-pixel masking, while QGIS uses GDAL's `gdal_rasterize`. These implement the same conceptual rule (center-of-pixel) but differ slightly at polygon boundaries.

In testing with the same AOI and raster:

| Tool | Pixel Count | Difference |
|------|-------------|------------|
| QGIS / GDAL | 21,245,799 | baseline |
| This API | 21,246,960 | +1,161 (+0.005%) |

The rasterstats mask is a **superset** of the GDAL mask -- it includes all GDAL pixels plus a small number of additional edge pixels. This is due to floating-point handling differences in the rasterization algorithms, not grid alignment.

For most use cases, this difference is negligible. If you need exact parity with QGIS, use GDAL directly:

```bash
gdalwarp -cutline aoi.geojson -crop_to_cutline -dstnodata 0 input.tif clipped.tif
gdalinfo -stats clipped.tif
```
