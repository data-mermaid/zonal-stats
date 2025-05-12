import logging
import math

import numpy as np
import rasterio
import requests
from pyproj import CRS
from rasterio.warp import transform_geom
from rasterstats import zonal_stats
from shapely.geometry import MultiPolygon, Polygon, shape

from ..models.schemas import BandStats, StatType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum allowed area in square kilometers
MAX_AREA_KM2 = 1000000  # 1 million square kilometers
# Maximum allowed number of pixels
MAX_PIXELS = 100000000  # 100 million pixels


def get_stac_asset_url(stac_url: str, asset_key: str | None = None) -> str:
    """
    Fetch a STAC item from the given URL and extract the asset URL (href)
    for the specified asset key.
    If asset_key is None, use the first asset in the item.
    """
    logger.info(f"Fetching STAC item from {stac_url}")
    resp = requests.get(stac_url)
    resp.raise_for_status()
    stac_item = resp.json()
    assets = stac_item.get("assets", {})
    if not assets:
        raise ValueError("No assets found in the STAC item.")
    if asset_key:
        asset = assets.get(asset_key)
        if not asset:
            raise ValueError(f"Asset '{asset_key}' not found in the STAC item.")
    else:
        # Use the first asset if no key is provided
        asset = next(iter(assets.values()))
    href = asset.get("href")
    logger.info(f"Asset href: {href}")
    if not href:
        if asset_key:
            raise ValueError(f"Asset '{asset_key}' does not contain an 'href' field.")
        else:
            raise ValueError("The first asset does not contain an 'href' field.")
    return href


class ZonalStatsService:
    def __init__(self, url: str, bands: list[int], approx_stats: bool = True):
        self.url = url
        self.bands = bands
        self.approx_stats = approx_stats

    def _process_stats_list(self, stats: list[StatType]) -> list[str]:
        """Process the list of statistics."""
        return [stat.value for stat in stats]

    def _validate_area(self, shapely_geom: Polygon | MultiPolygon) -> None:
        """Validate that the area is within acceptable limits."""
        # Calculate area in square kilometers
        area_km2 = (
            shapely_geom.area / 1000000
        )  # Convert from square meters to square kilometers
        logger.info(f"Area of geometry: {area_km2:.2f} km²")

        if area_km2 > MAX_AREA_KM2:
            raise ValueError(
                f"Area too large: {area_km2:.2f} km². Maximum allowed area is {MAX_AREA_KM2} km²"
            )

    def _validate_pixel_count(self, window: rasterio.windows.Window) -> None:
        """Validate that the number of pixels is within acceptable limits."""
        total_pixels = window.width * window.height
        logger.info(f"Total pixels in window: {total_pixels}")

        if total_pixels > MAX_PIXELS:
            raise ValueError(
                f"Too many pixels: {total_pixels}. Maximum allowed pixels is {MAX_PIXELS}"
            )

    def _get_overview_level(
        self, src: rasterio.io.DatasetReader, window: rasterio.windows.Window
    ) -> int:
        """
        Determine the appropriate overview level based on the window size.
        Returns the overview level to use (0 means no overview).
        """
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

    def calculate_stats(
        self, geometry: dict, stats: list[StatType]
    ) -> dict[str, BandStats]:
        """Calculate zonal statistics for the given geometry and bands."""
        shapely_geom = shape(geometry)
        logger.info(f"Processing geometry: {shapely_geom.bounds}")

        # Only validate area if not using approximate stats
        if not self.approx_stats:
            self._validate_area(shapely_geom)

        # Open the raster and read only the required portion
        with rasterio.open(self.url) as src:
            # Get the source CRS
            src_crs = src.crs
            if src_crs is None:
                raise ValueError("Source raster has no CRS defined")

            # Transform geometry to match raster CRS if needed
            if geometry.get("crs", {}).get("properties", {}).get("name") != str(
                src_crs
            ):
                logger.info(
                    f"Transforming geometry from "
                    f"{geometry.get('crs', {}).get('properties', {}).get('name')} "
                    f"to {src_crs}"
                )
                transformed_geom = transform_geom(
                    src_crs=CRS.from_epsg(4326),  # Assume input is in WGS84
                    dst_crs=src_crs,
                    geom=geometry,
                )
                shapely_geom = shape(transformed_geom)

            # Get the bounds of the geometry
            minx, miny, maxx, maxy = shapely_geom.bounds

            # Get the window for the geometry bounds
            window = src.window(minx, miny, maxx, maxy)

            # Only validate pixel count if not using approximate stats
            if not self.approx_stats:
                self._validate_pixel_count(window)

            # Determine if we should use overviews
            overview_level = self._get_overview_level(src, window)
            logger.info(f"Using overview level: {overview_level}")

            # Process the statistics list
            processed_stats = self._process_stats_list(stats)

            # Read the data for each band
            results = {}
            for band_idx in self.bands:
                # Read the data for the specific region, using overview if available
                if overview_level > 0:
                    # Get the overview factor
                    overview_factor = src.overviews(band_idx)[overview_level - 1]
                    # Calculate the output shape for the overview
                    out_shape = (
                        math.ceil(window.height / overview_factor),
                        math.ceil(window.width / overview_factor),
                    )
                    logger.info(
                        f"Reading band {band_idx} with overview shape: {out_shape}"
                    )
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

                logger.info(
                    f"Band {band_idx} data shape: {band_data.shape}, "
                    f"dtype: {band_data.dtype}"
                )

                # Handle nodata values
                if src.nodata is not None:
                    band_data[band_data == src.nodata] = np.nan
                    logger.info(
                        f"Number of NaN values after nodata conversion: "
                        f"{np.isnan(band_data).sum()}"
                    )

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

                # Create a dictionary with only the requested statistics
                band_stats_dict = {}
                for stat in stats:
                    value = stats_dict.get(stat.value)
                    if value is not None:
                        # Convert the value to the appropriate type
                        if stat == StatType.COUNT or stat == StatType.NODATA:
                            value = int(value)
                        elif stat == StatType.UNIQUE:
                            value = list(map(float, value))
                        elif stat == StatType.FREQ_HIST:
                            value = dict(value)
                        else:
                            value = float(value)
                        band_stats_dict[stat.value] = value

                # Convert to BandStats model with only requested statistics
                band_stats = BandStats(**band_stats_dict)

                results[f"band_{band_idx}"] = band_stats

            return results

    @staticmethod
    def validate_geometry(geometry: dict) -> bool:
        """Validate that the geometry is a valid GeoJSON Polygon or MultiPolygon."""
        try:
            shapely_geom = shape(geometry)
            return isinstance(shapely_geom, Polygon | MultiPolygon)
        except Exception:
            return False
