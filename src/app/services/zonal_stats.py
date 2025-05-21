import logging
import math

import numpy as np
import rasterio
import requests
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
            raise GeometryError("Invalid coordinates: longitude must be between -180 and 180, latitude between -90 and 90")

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
        if point.buffer_size <= 0:
            raise GeometryError("Buffer size must be greater than 0")
        
        buffered = utm_point.buffer(point.buffer_size)

        # Transform back to WGS84
        wgs84_polygon = transform(utm_to_wgs84.transform, buffered)

        # Convert to GeoJSON
        return {"type": "Polygon", "coordinates": [list(wgs84_polygon.exterior.coords)]}
    except Exception as e:
        if isinstance(e, ZonalStatsError):
            raise
        raise GeometryError(f"Error creating buffer polygon: {str(e)}")

def get_stac_asset_url(stac_url: str, asset_key: str | None = None) -> str:
    """
    Fetch a STAC item from the given URL and extract the asset URL (href)
    for the specified asset key.
    If asset_key is None, use the first asset in the item.
    """
    try:
        logger.info(f"Fetching STAC item from {stac_url}")
        resp = requests.get(stac_url)
        resp.raise_for_status()
        stac_item = resp.json()
        assets = stac_item.get("assets", {})
        if not assets:
            raise STACError("No assets found in the STAC item.")
        if asset_key:
            asset = assets.get(asset_key)
            if not asset:
                raise STACError(f"Asset '{asset_key}' not found in the STAC item.")
        else:
            # Use the first asset if no key is provided
            asset = next(iter(assets.values()))
        href = asset.get("href")
        logger.info(f"Asset href: {href}")
        if not href:
            if asset_key:
                raise STACError(f"Asset '{asset_key}' does not contain an 'href' field.")
            else:
                raise STACError("The first asset does not contain an 'href' field.")
        return href
    except requests.RequestException as e:
        raise STACError(f"Error fetching STAC item: {str(e)}")
    except Exception as e:
        if isinstance(e, ZonalStatsError):
            raise
        raise STACError(f"Unexpected error processing STAC item: {str(e)}")

class ZonalStatsService:
    def __init__(self, url: str, bands: list[int], approx_stats: bool = True):
        self.url = url
        self.bands = bands
        self.approx_stats = approx_stats

    def _process_stats_list(self, stats: list[StatType]) -> list[str]:
        """Process the list of statistics."""
        if not stats:
            raise ZonalStatsError("No statistics specified")
        return [stat.value for stat in stats]

    def _validate_area(self, shapely_geom: Polygon | MultiPolygon) -> None:
        """Validate that the area is within acceptable limits."""
        try:
            # Calculate area in square kilometers
            area_km2 = (
                shapely_geom.area / 1000000
            )  # Convert from square meters to square kilometers
            logger.info(f"Area of geometry: {area_km2:.2f} km²")

            if area_km2 > MAX_AREA_KM2:
                raise GeometryError(
                    f"Area too large: {area_km2:.2f} km². Maximum allowed area is {MAX_AREA_KM2} km²"
                )
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise GeometryError(f"Error validating area: {str(e)}")

    def _validate_pixel_count(self, window: rasterio.windows.Window) -> None:
        """Validate that the number of pixels is within acceptable limits."""
        try:
            total_pixels = window.width * window.height
            logger.info(f"Total pixels in window: {total_pixels}")

            if total_pixels > MAX_PIXELS:
                raise RasterError(
                    f"Too many pixels: {total_pixels}. Maximum allowed pixels is {MAX_PIXELS}"
                )
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error validating pixel count: {str(e)}")

    def _get_overview_level(
        self, src: rasterio.io.DatasetReader, window: rasterio.windows.Window
    ) -> int:
        """
        Determine the appropriate overview level based on the window size.
        Returns the overview level to use (0 means no overview).
        """
        try:
            if not self.approx_stats:
                return 0

            # Get the window size in pixels
            window_width = window.width
            window_height = window.height

            # Get available overviews
            overviews = src.overviews(1)  # Check overviews for band 1
            if not overviews:
                logger.info("No overviews available, using full resolution")
                return 0

            # Calculate the total number of pixels in the window
            total_pixels = window_width * window_height
            logger.info(
                f"Window size: {window_width}x{window_height} = {total_pixels} pixels"
            )

            threshold = 100_000_000
            for level, factor in enumerate(overviews):
                # Calculate the effective resolution at this overview level
                effective_pixels = total_pixels / (factor * factor)
                logger.info(
                    f"Overview level {level} (factor: {factor}): {effective_pixels:.0f} effective pixels"
                )

                # Only use this overview if it would result in at least 1 million pixels
                if effective_pixels < 1_000_000:
                    logger.info(
                        f"Overview level {level} would result in too few pixels ({effective_pixels:.0f}), using previous level"
                    )
                    return max(0, level - 1)

                # If we're still above the threshold, continue to next level
                if total_pixels > threshold * (1.2**level):  # More gradual increase
                    continue

                logger.info(f"Selected overview level {level} (factor: {factor})")
                return level

            # If we get here, use the highest available overview
            logger.info(f"Using highest available overview level {len(overviews) - 1}")
            return len(overviews) - 1
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error determining overview level: {str(e)}")

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
                raise GeometryError("Invalid geometry: self-intersection or other topological error")
            
            logger.info(f"Processing geometry: {shapely_geom.bounds}")
            return geometry_dict, shapely_geom
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise GeometryError(f"Error preparing geometry: {str(e)}")

    def _transform_geometry_to_raster_crs(
        self, geometry_dict: dict, src_crs: CRS
    ) -> shape:
        """Transform geometry to match raster CRS if needed."""
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
                return shape(transformed_geom)
            return shape(geometry_dict)
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise GeometryError(f"Error transforming geometry: {str(e)}")

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
                f"Band {band_idx} data shape: {band_data.shape}, dtype: {band_data.dtype}"
            )
            return band_data
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error reading band data: {str(e)}")

    def _handle_nodata(
        self, band_data: np.ndarray, src: rasterio.io.DatasetReader
    ) -> np.ndarray:
        """Handle nodata values in band data."""
        try:
            if src.nodata is not None:
                band_data[band_data == src.nodata] = np.nan
                logger.info(
                    f"Number of NaN values after nodata conversion: {np.isnan(band_data).sum()}"
                )
            return band_data
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise RasterError(f"Error handling nodata values: {str(e)}")

    def _process_band_stats(self, stats_dict: dict, stats: list[StatType]) -> BandStats:
        """Process statistics for a single band and convert to BandStats model."""
        try:
            band_stats_dict = {}
            for stat in stats:
                value = stats_dict.get(stat.value)
                if value is not None:
                    if stat == StatType.COUNT or stat == StatType.NODATA:
                        value = int(value)
                    elif stat == StatType.UNIQUE:
                        value = list(map(float, value))
                    elif stat == StatType.FREQ_HIST:
                        value = dict(value)
                    else:
                        value = float(value)
                    band_stats_dict[stat.value] = value
            return BandStats(**band_stats_dict)
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise ZonalStatsError(f"Error processing band statistics: {str(e)}")

    def calculate_stats(
        self, geometry: PointGeometry | PolygonGeometry, stats: list[StatType]
    ) -> dict[str, BandStats]:
        """Calculate zonal statistics for the given geometry and bands."""
        try:
            # Prepare geometry
            geometry_dict, shapely_geom = self._prepare_geometry(geometry)

            # Only validate area if not using approximate stats
            if not self.approx_stats:
                self._validate_area(shapely_geom)

            # Open the raster and read only the required portion
            try:
                src = rasterio.open(self.url)
            except Exception as e:
                raise RasterError(f"Error opening raster file: {str(e)}")

            try:
                # Get the source CRS
                src_crs = src.crs
                if src_crs is None:
                    raise RasterError("Source raster has no CRS defined")

                # Transform geometry to match raster CRS if needed
                shapely_geom = self._transform_geometry_to_raster_crs(
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
                        center_x - pixel_size_x/2,
                        center_y - pixel_size_y/2,
                        center_x + pixel_size_x/2,
                        center_y + pixel_size_y/2
                    )
                    logger.info(f"Adjusted window size for small polygon to ensure at least one pixel: {window}")

                # Only validate pixel count if not using approximate stats
                if not self.approx_stats:
                    self._validate_pixel_count(window)

                # Determine if we should use overviews
                overview_level = self._get_overview_level(src, window)
                logger.info(f"Using overview level: {overview_level}")

                # Process the statistics list
                processed_stats = self._process_stats_list(stats)

                # Process each band
                results = {}
                for band_idx in self.bands:
                    # Read band data
                    band_data = self._read_band_data(src, band_idx, window, overview_level)

                    # Handle nodata values
                    band_data = self._handle_nodata(band_data, src)

                    # Calculate statistics
                    stats_dict = zonal_stats(
                        shapely_geom,
                        band_data,
                        affine=src.window_transform(window),
                        stats=processed_stats,
                        nodata=np.nan,
                        all_touched=True,
                        raster_out=False,
                    )[0]

                    logger.info(f"Calculated stats for band {band_idx}: {stats_dict}")

                    # Process and store results
                    band_stats = self._process_band_stats(stats_dict, stats)
                    results[f"band_{band_idx}"] = band_stats

                return results
            finally:
                src.close()
        except Exception as e:
            if isinstance(e, ZonalStatsError):
                raise
            raise ZonalStatsError(f"Error calculating statistics: {str(e)}")

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
                if shapely_geom.is_empty:
                    return False

                return True
        except Exception:
            return False
