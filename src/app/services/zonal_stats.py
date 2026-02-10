import logging
import math

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.warp import transform_geom
from rasterstats import zonal_stats
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.ops import transform

from ..models.schemas import BandStats, PointGeometry, PolygonGeometry, StatType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum allowed area in square kilometers
MAX_AREA_KM2 = 1000000  # 1 million square kilometers
# Maximum allowed number of pixels
MAX_PIXELS = 100000000  # 100 million pixels


class ZonalStatsError(Exception):
    """Base exception for zonal statistics errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GeometryError(ZonalStatsError):
    """Exception for geometry-related errors."""

    pass


class RasterError(ZonalStatsError):
    """Exception for raster-related errors."""

    pass


class STACError(ZonalStatsError):
    """Exception for STAC-related errors."""

    pass


class VectorError(ZonalStatsError):
    """Exception for vector data operations."""

    pass


class UnsupportedMediaTypeError(ZonalStatsError):
    """Exception for unsupported file formats (HTTP 415)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=415)


def create_buffer_polygon(point: PointGeometry) -> dict:
    """
    Create a polygon from a point by applying a buffer in meters.
    Returns a GeoJSON polygon.
    """
    try:
        # Create a Point geometry
        point_geom = Point(point.coordinates)

        # Create a transformer from WGS84 to a projected CRS (using UTM)
        # We'll use UTM zone based on the longitude and hemisphere based on latitude
        lon = point.coordinates[0]
        lat = point.coordinates[1]

        if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
            raise GeometryError(
                "Invalid coordinates: longitude must be between -180 and 180, "
                "latitude between -90 and 90"
            )

        # Calculate UTM zone
        utm_zone = int((lon + 180) / 6) + 1

        # Determine if we're in the northern or southern hemisphere
        # UTM North is EPSG:32600 + zone, UTM South is EPSG:32700 + zone
        utm_epsg = 32600 + utm_zone if lat >= 0 else 32700 + utm_zone
        utm_crs = CRS.from_epsg(utm_epsg)

        logger.info(
            f"Using UTM zone {utm_zone} {'North' if lat >= 0 else 'South'} "
            f"(EPSG:{utm_epsg}) for point at {lon}, {lat}"
        )

        # Create transformers
        wgs84_to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        utm_to_wgs84 = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

        # Transform point to UTM
        utm_point = transform(wgs84_to_utm.transform, point_geom)

        # Create buffer in UTM coordinates (meters)
        if not point.radius or point.radius <= 0:
            raise GeometryError("Radius must be greater than 0")

        buffered = utm_point.buffer(point.radius)

        # Transform back to WGS84
        wgs84_polygon = transform(utm_to_wgs84.transform, buffered)

        # Convert to GeoJSON
        return {"type": "Polygon", "coordinates": [list(wgs84_polygon.exterior.coords)]}
    except Exception as e:
        if isinstance(e, ZonalStatsError):
            raise
        raise GeometryError(f"Error creating buffer polygon: {str(e)}") from e


class ZonalStatsService:
    def __init__(self, url: str, bands: list[int], approx_stats: bool = True):
        self.url = url
        self.bands = bands
        self.approx_stats = approx_stats

    def _process_stats_list(self, stats: list[StatType] | None) -> list[str]:
        """Process the list of statistics."""
        if stats is None:
            stats = [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
        elif not stats:
            raise ZonalStatsError("Statistics list cannot be empty")

        # Filter out custom statistics that aren't supported by rasterstats
        raster_stats = [
            stat.value
            for stat in stats
            if stat not in [StatType.AOI_AREA, StatType.DATA_AREA, StatType.FREQ_HIST]
        ]
        return raster_stats

    def _ensure_area_stats(self, stats: list[StatType]) -> list[StatType]:
        """Ensure aoi_area and data_area are always included."""
        result = list(stats)
        if StatType.AOI_AREA not in result:
            result.append(StatType.AOI_AREA)
        if StatType.DATA_AREA not in result:
            result.append(StatType.DATA_AREA)
        return result

    def _validate_area(self, shapely_geom: Polygon | MultiPolygon) -> None:
        """Validate that the area is within acceptable limits."""
        try:
            # Calculate area in square kilometers using the proper CRS-aware method
            area_m2 = self._calculate_area_in_square_meters(
                shapely_geom, CRS.from_epsg(4326)
            )  # Assume WGS84 if not specified
            area_km2 = (
                area_m2 / 1000000
            )  # Convert from square meters to square kilometers
            logger.info(f"Area of geometry: {area_km2:.2f} km²")

            if area_km2 > MAX_AREA_KM2:
                raise GeometryError(
                    f"Area too large: {area_km2:.2f} km². "
                    f"Maximum allowed area is {MAX_AREA_KM2} km²"
                )
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise GeometryError(f"Error validating area: {str(e)}") from e

    def _validate_pixel_count(self, window: rasterio.windows.Window) -> None:
        """Validate that the number of pixels is within acceptable limits."""
        try:
            total_pixels = window.width * window.height
            logger.info(f"Total pixels in window: {total_pixels}")

            if total_pixels > MAX_PIXELS:
                raise RasterError(
                    f"Too many pixels: {total_pixels}. "
                    f"Maximum allowed pixels is {MAX_PIXELS}"
                )
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error validating pixel count: {str(e)}") from e

    def _get_overview_level(
        self, src: rasterio.io.DatasetReader, window: rasterio.windows.Window
    ) -> int:
        """
        Determine the appropriate overview level based on the window size.

        Returns:
            0 = full resolution (no overview)
            1 = first overview (overviews[0])
            2 = second overview (overviews[1])
            etc.
        """
        try:
            if not self.approx_stats:
                return 0

            # Get the window size in pixels
            window_width = window.width
            window_height = window.height

            # Get available overviews for the first requested band
            # (bands may have different overview sets)
            overviews = src.overviews(self.bands[0])
            if not overviews:
                logger.info("No overviews available, using full resolution")
                return 0

            # Calculate the total number of pixels in the window
            total_pixels = window_width * window_height
            logger.info(
                f"Window size: {window_width}x{window_height} = {total_pixels} pixels"
            )

            threshold = 100_000_000
            for idx, factor in enumerate(overviews):
                # idx is 0-based, but we return 1-based (0 = full res)
                level = idx + 1

                # Calculate the effective resolution at this overview level
                effective_pixels = total_pixels / (factor * factor)
                logger.info(
                    f"Overview level {level} (factor: {factor}): "
                    f"{effective_pixels:.0f} effective pixels"
                )

                # Only use this overview if it would result in at least 1 million pixels
                if effective_pixels < 1_000_000:
                    logger.info(
                        f"Overview level {level} would result in too few pixels "
                        f"({effective_pixels:.0f}), using previous level"
                    )
                    # Return previous level (level - 1), but not less than 0 (full res)
                    return max(0, level - 1)

                # If we're still above the threshold, continue to next level
                if total_pixels > threshold * (1.2**idx):  # More gradual increase
                    continue

                logger.info(f"Selected overview level {level} (factor: {factor})")
                return level

            # If we get here, use the highest available overview
            highest_level = len(overviews)
            logger.info(f"Using highest available overview level {highest_level}")
            return highest_level
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error determining overview level: {str(e)}") from e

    def _prepare_geometry(
        self, geometry: PointGeometry | PolygonGeometry
    ) -> tuple[dict, shape]:
        """Convert geometry to GeoJSON dict and Shapely shape, handling point buffering
        if needed."""
        try:
            if isinstance(geometry, PointGeometry):
                geometry_dict = create_buffer_polygon(geometry)
            else:
                geometry_dict = geometry.model_dump()

            shapely_geom = shape(geometry_dict)
            if not shapely_geom.is_valid:
                raise GeometryError(
                    "Invalid geometry: self-intersection or other topological error"
                )

            logger.info(f"Processing geometry: {shapely_geom.bounds}")
            return geometry_dict, shapely_geom
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise GeometryError(f"Error preparing geometry: {str(e)}") from e

    def _transform_geometry_to_raster_crs(
        self, geometry_dict: dict, src_crs: CRS
    ) -> tuple[shape, CRS]:
        """Transform geometry to match raster CRS if needed.
        Returns the transformed geometry and its CRS."""
        try:
            if geometry_dict.get("crs", {}).get("properties", {}).get("name") != str(
                src_crs
            ):
                logger.info(f"Transforming geometry from WGS84 to {src_crs}")
                transformed_geom = transform_geom(
                    src_crs=CRS.from_epsg(4326),  # Assume input is in WGS84
                    dst_crs=src_crs,
                    geom=geometry_dict,
                )
                return shape(transformed_geom), CRS.from_user_input(src_crs)
            return shape(geometry_dict), CRS.from_epsg(4326)
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise GeometryError(f"Error transforming geometry: {str(e)}") from e

    def _calculate_area_in_square_meters(self, geom: shape, geom_crs: CRS) -> float:
        """
        Calculate area in square meters, converting from the geometry's CRS
        if needed.
        """
        try:
            # If the geometry is already in a projected CRS that uses meters
            if geom_crs.is_projected and geom_crs.axis_info[0].unit_name.lower() in [
                "metre",
                "meter",
            ]:
                return geom.area

            # If the geometry is in a geographic CRS (like WGS84) or uses
            # different units, transform it to an equal-area projection
            # centered on the geometry
            center = geom.centroid
            # Use Albers Equal Area projection centered on the geometry
            proj_crs = CRS.from_proj4(
                f"+proj=aea +lat_1={center.y - 1} +lat_2={center.y + 1} "
                f"+lat_0={center.y} +lon_0={center.x} +x_0=0 +y_0=0 "
                f"+ellps=WGS84 +units=m +no_defs"
            )

            # Transform the geometry to the equal-area projection
            transformer = Transformer.from_crs(geom_crs, proj_crs, always_xy=True)
            transformed_geom = transform(transformer.transform, geom)

            return transformed_geom.area
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise GeometryError(f"Error calculating area: {str(e)}") from e

    def _read_band_data(
        self,
        src: rasterio.io.DatasetReader,
        band_idx: int,
        window: rasterio.windows.Window,
        overview_level: int,
    ) -> np.ndarray:
        """Read band data with appropriate overview level and apply scale/offset."""
        try:
            if band_idx not in src.indexes:
                raise RasterError(f"Band {band_idx} not found in raster")

            if overview_level > 0:
                overview_factor = src.overviews(band_idx)[overview_level - 1]
                out_shape = (
                    math.ceil(window.height / overview_factor),
                    math.ceil(window.width / overview_factor),
                )
                logger.info(f"Reading band {band_idx} with overview shape: {out_shape}")
                band_data = src.read(
                    band_idx,
                    window=window,
                    out_shape=out_shape,
                ).astype(np.float32)
            else:
                logger.info(f"Reading band {band_idx} at full resolution")
                band_data = src.read(
                    band_idx,
                    window=window,
                ).astype(np.float32)

            # Handle nodata values
            band_data = self._handle_nodata(band_data, src)

            # Apply scale and offset if they exist
            scales = src.scales
            offsets = src.offsets

            if scales is not None and len(scales) >= band_idx:
                scale = scales[band_idx - 1]
                if scale != 1.0:
                    logger.info(f"Applying scale factor {scale} to band {band_idx}")
                    band_data = band_data * scale

            if offsets is not None and len(offsets) >= band_idx:
                offset = offsets[band_idx - 1]
                if offset != 0.0:
                    logger.info(f"Applying offset {offset} to band {band_idx}")
                    band_data = band_data + offset

            logger.info(
                f"Band {band_idx} data shape: {band_data.shape}, "
                f"dtype: {band_data.dtype}"
            )
            return band_data
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error reading band data: {str(e)}") from e

    def _handle_nodata(
        self, band_data: np.ndarray, src: rasterio.io.DatasetReader
    ) -> np.ndarray:
        """Handle nodata values in band data."""
        try:
            if src.nodata is not None:
                band_data[band_data == src.nodata] = np.nan
                logger.info(
                    f"Number of NaN values after nodata conversion: "
                    f"{np.isnan(band_data).sum()}"
                )
            return band_data
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error handling nodata values: {str(e)}") from e

    def _process_band_stats(self, stats_dict: dict, stats: list[StatType]) -> BandStats:
        """Process statistics for a single band and convert to BandStats model."""
        try:
            band_stats_dict = {}
            for stat in stats:
                if stat == StatType.AOI_AREA:
                    # AOI area in square meters
                    band_stats_dict[stat.value] = float(stats_dict.get("aoi_area", 0))
                elif stat == StatType.DATA_AREA:
                    # Data area (valid pixels) in square meters
                    band_stats_dict[stat.value] = float(stats_dict.get("data_area", 0))
                elif stat == StatType.FREQ_HIST:
                    # Frequency histogram is already calculated
                    band_stats_dict[stat.value] = dict(stats_dict.get("freq_hist", {}))
                elif stat == StatType.COUNT or stat == StatType.NODATA:
                    value = stats_dict.get(stat.value)
                    band_stats_dict[stat.value] = int(value) if value is not None else 0
                elif stat == StatType.UNIQUE:
                    # Handle unique values - they should already be a list of numbers
                    value = stats_dict.get(stat.value)
                    band_stats_dict[stat.value] = value if value is not None else []
                else:
                    value = stats_dict.get(stat.value)
                    band_stats_dict[stat.value] = (
                        float(value) if value is not None else None
                    )
            return BandStats(**band_stats_dict)
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise ZonalStatsError(f"Error processing band statistics: {str(e)}") from e

    def _sample_point(
        self,
        geometry: PointGeometry,
        stats: list[StatType] | None,
    ) -> dict[str, BandStats]:
        """Sample the single pixel under a point (no radius) for each band."""
        try:
            lon, lat = geometry.coordinates

            # Process stats list
            base_stats = (
                stats
                if stats is not None
                else [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
            )
            stats_to_use = self._ensure_area_stats(base_stats)

            try:
                src = rasterio.open(self.url)
            except Exception as e:
                raise RasterError(f"Error opening raster file: {str(e)}") from e

            try:
                src_crs = src.crs
                if src_crs is None:
                    raise RasterError("Source raster has no CRS defined")

                # Transform point to raster CRS
                if src_crs != CRS.from_epsg(4326):
                    transformer = Transformer.from_crs(
                        "EPSG:4326", src_crs, always_xy=True
                    )
                    x, y = transformer.transform(lon, lat)
                else:
                    x, y = lon, lat

                # Get pixel row/col
                row, col = src.index(x, y)

                # Check bounds
                if row < 0 or row >= src.height or col < 0 or col >= src.width:
                    raise GeometryError("Point is outside the raster extent")

                # Calculate pixel area in m²
                pixel_width = abs(src.transform.a)
                pixel_height = abs(src.transform.e)
                if src_crs.is_geographic:
                    center_lat = lat
                    meters_per_degree_lon = 111320 * math.cos(math.radians(center_lat))
                    meters_per_degree_lat = 110540
                    pixel_area_m2 = (
                        pixel_width
                        * meters_per_degree_lon
                        * pixel_height
                        * meters_per_degree_lat
                    )
                else:
                    pixel_area_m2 = pixel_width * pixel_height

                window = rasterio.windows.Window(col, row, 1, 1)

                results = {}
                for band_idx in self.bands:
                    if band_idx not in src.indexes:
                        raise RasterError(f"Band {band_idx} not found in raster")

                    data = src.read(band_idx, window=window).astype(np.float32)
                    value = data[0, 0]

                    # Handle nodata
                    is_nodata = False
                    if src.nodata is not None and value == src.nodata:
                        is_nodata = True

                    # Apply scale/offset
                    if not is_nodata:
                        scales = src.scales
                        offsets = src.offsets
                        if scales is not None and len(scales) >= band_idx:
                            scale = scales[band_idx - 1]
                            if scale != 1.0:
                                value = value * scale
                        if offsets is not None and len(offsets) >= band_idx:
                            offset = offsets[band_idx - 1]
                            if offset != 0.0:
                                value = value + offset

                    # Build stats dict
                    stats_dict = {}
                    pixel_value = None if is_nodata else float(value)

                    for stat in stats_to_use:
                        if stat == StatType.AOI_AREA:
                            stats_dict["aoi_area"] = 0.0
                        elif stat == StatType.DATA_AREA:
                            stats_dict["data_area"] = (
                                0.0 if is_nodata else pixel_area_m2
                            )
                        elif stat == StatType.FREQ_HIST:
                            stats_dict["freq_hist"] = (
                                {} if is_nodata else {pixel_value: 1}
                            )
                        elif stat == StatType.COUNT:
                            stats_dict["count"] = 0 if is_nodata else 1
                        elif stat == StatType.NODATA:
                            stats_dict["nodata"] = 1 if is_nodata else 0
                        elif stat == StatType.STD:
                            stats_dict["std"] = None if is_nodata else 0.0
                        elif stat == StatType.UNIQUE:
                            stats_dict["unique"] = [] if is_nodata else [pixel_value]
                        elif stat == StatType.RANGE:
                            stats_dict["range"] = None if is_nodata else 0.0
                        else:
                            # min, max, mean, sum, median, majority, minority
                            stats_dict[stat.value] = pixel_value

                    band_stats = self._process_band_stats(stats_dict, stats_to_use)
                    results[f"band_{band_idx}"] = band_stats

                return results
            finally:
                src.close()
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise ZonalStatsError(f"Error sampling point: {str(e)}") from e

    def calculate_stats(
        self, geometry: PointGeometry | PolygonGeometry, stats: list[StatType] | None
    ) -> dict[str, BandStats]:
        """Calculate zonal statistics for the given geometry and bands."""
        try:
            # Point without radius: sample single pixel directly
            if isinstance(geometry, PointGeometry) and (
                not geometry.radius or geometry.radius <= 0
            ):
                return self._sample_point(geometry, stats)

            # Prepare geometry
            geometry_dict, shapely_geom = self._prepare_geometry(geometry)

            # Only validate area if not using approximate stats
            if not self.approx_stats:
                self._validate_area(shapely_geom)

            # Open the raster and read only the required portion
            try:
                src = rasterio.open(self.url)
            except Exception as e:
                raise RasterError(f"Error opening raster file: {str(e)}") from e

            try:
                # Get the source CRS
                src_crs = src.crs
                if src_crs is None:
                    raise RasterError("Source raster has no CRS defined")

                # Transform geometry to match raster CRS if needed
                shapely_geom, geom_crs = self._transform_geometry_to_raster_crs(
                    geometry_dict, src_crs
                )

                # Get the bounds and window
                minx, miny, maxx, maxy = shapely_geom.bounds
                window = src.window(minx, miny, maxx, maxy)

                # Ensure we have at least one pixel of data
                if window.width < 1 or window.height < 1:
                    # Get the center point of the geometry
                    center_x = (minx + maxx) / 2
                    center_y = (miny + maxy) / 2

                    # Create a window that's at least one pixel in size
                    pixel_size_x = src.res[0]
                    pixel_size_y = src.res[1]

                    # Create a window that's at least one pixel in size
                    window = src.window(
                        center_x - pixel_size_x / 2,
                        center_y - pixel_size_y / 2,
                        center_x + pixel_size_x / 2,
                        center_y + pixel_size_y / 2,
                    )
                    logger.info(
                        f"Adjusted window size for small polygon to ensure at least "
                        f"one pixel: {window}"
                    )

                # Only validate pixel count if not using approximate stats
                if not self.approx_stats:
                    self._validate_pixel_count(window)

                # Determine if we should use overviews
                overview_level = self._get_overview_level(src, window)
                logger.info(f"Using overview level: {overview_level}")

                # Process the statistics list
                processed_stats = self._process_stats_list(stats)
                # Get the actual stats to use for processing results
                # Always include aoi_area and data_area
                base_stats = (
                    stats
                    if stats is not None
                    else [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
                )
                stats_to_use = self._ensure_area_stats(base_stats)

                # Process each band
                results = {}
                for band_idx in self.bands:
                    # Read band data
                    band_data = self._read_band_data(
                        src, band_idx, window, overview_level
                    )

                    # Calculate frequency histogram if requested
                    freq_hist = {}
                    if StatType.FREQ_HIST in stats_to_use:
                        # Calculate histogram before handling nodata
                        unique_values, counts = np.unique(band_data, return_counts=True)
                        freq_hist = dict(
                            zip(unique_values.tolist(), counts.tolist(), strict=False)
                        )

                    # Initialize stats dictionary with custom statistics
                    stats_dict = {}
                    if StatType.AOI_AREA in stats_to_use:
                        stats_dict["aoi_area"] = self._calculate_area_in_square_meters(
                            shapely_geom, geom_crs
                        )
                    if StatType.FREQ_HIST in stats_to_use:
                        stats_dict["freq_hist"] = freq_hist

                    # Calculate rasterstats if there are any standard statistics
                    # requested
                    window_transform = src.window_transform(window)

                    # Adjust transform for overview level to match resampled array
                    if overview_level > 0:
                        overviews = src.overviews(band_idx)
                        overview_factor = overviews[overview_level - 1]
                        # Scale pixel dimensions by overview factor
                        adjusted_transform = rasterio.Affine(
                            window_transform.a * overview_factor,
                            window_transform.b,
                            window_transform.c,
                            window_transform.d,
                            window_transform.e * overview_factor,
                            window_transform.f,
                        )
                    else:
                        adjusted_transform = window_transform

                    if processed_stats:
                        raster_stats_dict = zonal_stats(
                            shapely_geom,
                            band_data,
                            affine=adjusted_transform,
                            stats=processed_stats,
                            nodata=np.nan,
                            all_touched=False,
                            raster_out=False,
                        )[0]
                        stats_dict.update(raster_stats_dict)

                    # Calculate data_area (area of valid pixels) if requested
                    if StatType.DATA_AREA in stats_to_use:
                        # Count valid (non-NaN) pixels within the geometry
                        valid_pixel_stats = zonal_stats(
                            shapely_geom,
                            band_data,
                            affine=adjusted_transform,
                            stats=["count"],
                            nodata=np.nan,
                            all_touched=False,
                            raster_out=False,
                        )[0]
                        valid_count = valid_pixel_stats.get("count", 0) or 0
                        # Calculate pixel area in square meters
                        # Transform already accounts for overview scaling
                        pixel_width = abs(adjusted_transform.a)
                        pixel_height = abs(adjusted_transform.e)
                        # Convert to square meters if CRS is geographic
                        if src_crs.is_geographic:
                            # Approximate conversion at geometry centroid
                            center = shapely_geom.centroid
                            meters_per_degree_lon = 111320 * math.cos(
                                math.radians(center.y)
                            )
                            meters_per_degree_lat = 110540
                            pixel_area_m2 = (
                                pixel_width
                                * meters_per_degree_lon
                                * pixel_height
                                * meters_per_degree_lat
                            )
                        else:
                            pixel_area_m2 = pixel_width * pixel_height
                        stats_dict["data_area"] = float(valid_count * pixel_area_m2)

                    logger.info(f"Calculated stats for band {band_idx}: {stats_dict}")

                    # Process and store results
                    band_stats = self._process_band_stats(stats_dict, stats_to_use)
                    results[f"band_{band_idx}"] = band_stats

                return results
            finally:
                src.close()
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise ZonalStatsError(f"Error calculating statistics: {str(e)}") from e

    @staticmethod
    def validate_geometry(geometry: PointGeometry | PolygonGeometry) -> bool:
        """Validate that the geometry is a valid GeoJSON Point or Polygon."""
        try:
            if isinstance(geometry, PointGeometry):
                # Point validation is handled by the Pydantic model
                return True
            else:
                shapely_geom = shape(geometry.model_dump())

                # Check if it's a valid polygon type
                if not isinstance(shapely_geom, (Polygon, MultiPolygon)):
                    return False

                # Check if the polygon is valid (no self-intersections, etc.)
                if not shapely_geom.is_valid:
                    return False

                # Check if the polygon is not empty
                return not shapely_geom.is_empty
        except Exception:
            return False
