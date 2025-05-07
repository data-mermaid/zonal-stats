import logging

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.warp import transform_geom
from rasterstats import zonal_stats
from shapely.geometry import MultiPolygon, Polygon, shape

from ..models.schemas import BandStats, StatType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ZonalStatsService:
    def __init__(self, url: str, bands: list[int], approx_stats: bool = True):
        self.url = url
        self.bands = bands
        self.approx_stats = approx_stats

    def _process_stats_list(self, stats: list[StatType]) -> list[str]:
        """Process the list of statistics."""
        return [stat.value for stat in stats]

    def calculate_stats(
        self, geometry: dict, stats: list[StatType]
    ) -> dict[str, BandStats]:
        """Calculate zonal statistics for the given geometry and bands."""
        shapely_geom = shape(geometry)
        logger.info(f"Processing geometry: {shapely_geom.bounds}")

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

            # Process the statistics list
            processed_stats = self._process_stats_list(stats)

            # Read the data for each band
            results = {}
            for band_idx in self.bands:
                # Read the data for the specific region
                band_data = src.read(
                    band_idx, window=src.window(minx, miny, maxx, maxy)
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
                    affine=src.window_transform(src.window(minx, miny, maxx, maxy)),
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
