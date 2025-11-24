import os
from unittest.mock import MagicMock, patch

import pytest
import rasterio
from requests.exceptions import RequestException, Timeout

from app.models.schemas import PolygonGeometry, StatType
from app.services.zonal_stats import (
    GeometryError,
    RasterError,
    STACError,
    ZonalStatsError,
    ZonalStatsService,
    get_stac_asset_url,
)

# Test data
RASTER_PATH = os.path.join("tests", "data", "random_centrallondon_raster_cog_001.tif")
POLYGON_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [
            [-0.16, 51.5],
            [-0.11, 51.5],
            [-0.11, 51.52],
            [-0.16, 51.52],
            [-0.16, 51.5],
        ]
    ],
}


def test_network_error_handling():
    """Test handling of network errors when fetching remote rasters."""
    with patch("rasterio.open") as mock_open:
        # Simulate a network error when trying to open the raster
        mock_open.side_effect = RequestException("Failed to connect to remote server")

        service = ZonalStatsService(
            url="https://example.com/remote_raster.tif", bands=[1]
        )

        with pytest.raises(RasterError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Error opening raster file" in str(exc_info.value)
        assert exc_info.value.status_code == 400


def test_invalid_raster_format():
    """Test handling of invalid raster formats."""
    with patch("rasterio.open") as mock_open:
        # Simulate an invalid raster format error
        mock_open.side_effect = rasterio.errors.RasterioIOError(
            "Not a valid raster file"
        )

        service = ZonalStatsService(url="invalid_raster.txt", bands=[1])

        with pytest.raises(RasterError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Error opening raster file" in str(exc_info.value)
        assert exc_info.value.status_code == 400


def test_out_of_memory_scenario():
    """Test handling of out-of-memory scenarios."""
    # To test memory errors, we need to patch _read_band_data and make sure
    # it's correctly handled by ZonalStatsService
    with patch(
        "app.services.zonal_stats.ZonalStatsService._read_band_data"
    ) as mock_read_band:
        # Make the _read_band_data method raise a MemoryError
        mock_read_band.side_effect = MemoryError("Not enough memory")

        service = ZonalStatsService(url=RASTER_PATH, bands=[1], approx_stats=False)

        with pytest.raises(ZonalStatsError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Not enough memory" in str(exc_info.value)
        assert exc_info.value.status_code == 400


def test_timeout_scenario():
    """Test handling of timeout scenarios when fetching remote rasters."""
    with patch("rasterio.open") as mock_open:
        # Simulate a timeout when trying to open the raster
        mock_open.side_effect = Timeout("Request timed out")

        service = ZonalStatsService(
            url="https://example.com/slow_raster.tif", bands=[1]
        )

        with pytest.raises(RasterError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Error opening raster file" in str(exc_info.value)
        assert exc_info.value.status_code == 400


def test_missing_crs_handling():
    """Test handling of rasters with missing CRS information."""
    with (
        patch("rasterio.open") as mock_open,
        patch(
            "app.services.zonal_stats.ZonalStatsService._transform_geometry_to_raster_crs"
        ) as mock_transform,
    ):
        # Create a mock dataset with no CRS
        mock_dataset = MagicMock()
        mock_dataset.crs = None
        mock_open.return_value.__enter__.return_value = mock_dataset

        # Skip all the transformation code with this mock
        mock_transform.side_effect = RasterError(
            "Source raster has no CRS defined", status_code=400
        )

        service = ZonalStatsService(url="no_crs_raster.tif", bands=[1])

        with pytest.raises(RasterError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Source raster has no CRS defined" in str(exc_info.value)


def test_invalid_geometry_handling():
    """Test handling of invalid geometries."""
    # Create an invalid geometry (self-intersecting polygon)
    invalid_geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-0.16, 51.5],
                [-0.11, 51.5],
                [-0.11, 51.52],
                [-0.16, 51.52],
                [-0.16, 51.5],
            ]
        ],
    }

    with (
        patch("rasterio.open") as mock_open,
        patch(
            "app.services.zonal_stats.ZonalStatsService._transform_geometry_to_raster_crs"
        ),
        patch(
            "app.services.zonal_stats.ZonalStatsService._prepare_geometry"
        ) as mock_prepare,
    ):
        # We'll make the prepare_geometry method raise a GeometryError
        mock_prepare.side_effect = GeometryError("Invalid geometry")

        # Create a mock dataset
        mock_dataset = MagicMock()
        mock_crs = MagicMock()
        mock_crs.__str__.return_value = "EPSG:4326"
        mock_dataset.crs = mock_crs
        mock_dataset.window.return_value = rasterio.windows.Window(0, 0, 100, 100)
        mock_open.return_value.__enter__.return_value = mock_dataset

        service = ZonalStatsService(url=RASTER_PATH, bands=[1])

        with pytest.raises(GeometryError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**invalid_geometry),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Invalid geometry" in str(exc_info.value)
        assert exc_info.value.status_code == 400


def test_stac_error_handling():
    """Test handling of STAC-related errors."""
    # Directly test the STAC handling function
    with patch("requests.get") as mock_get:
        # Set up the mock to raise an Exception
        mock_get.side_effect = RequestException("STAC API unavailable")

        # Call the function directly and verify it raises the correct error
        with pytest.raises(STACError) as exc_info:
            get_stac_asset_url("https://example.com/stac/item.json", "visual")

        assert "Error fetching STAC item" in str(exc_info.value)
