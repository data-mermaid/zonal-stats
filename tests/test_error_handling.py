import os
from unittest.mock import MagicMock, patch

import pytest
import rasterio
from requests.exceptions import RequestException, Timeout

from app.models.schemas import PolygonGeometry, StatType
from app.services.zonal_stats import ZonalStatsService

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

        with pytest.raises(RequestException) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Failed to connect to remote server" in str(exc_info.value)


def test_invalid_raster_format():
    """Test handling of invalid raster formats."""
    with patch("rasterio.open") as mock_open:
        # Simulate an invalid raster format error
        mock_open.side_effect = rasterio.errors.RasterioIOError(
            "Not a valid raster file"
        )

        service = ZonalStatsService(url="invalid_raster.txt", bands=[1])

        with pytest.raises(rasterio.errors.RasterioIOError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Not a valid raster file" in str(exc_info.value)


def test_out_of_memory_scenario():
    """Test handling of out-of-memory scenarios."""
    with patch("rasterio.open") as mock_open:
        # Create a mock dataset that simulates a very large raster
        mock_dataset = MagicMock()
        mock_dataset.crs = rasterio.crs.CRS.from_epsg(4326)
        mock_dataset.nodata = None

        # Simulate a very large window that would cause memory issues
        mock_dataset.window.return_value = rasterio.windows.Window(
            0, 0, 1000000, 1000000
        )
        mock_open.return_value.__enter__.return_value = mock_dataset

        service = ZonalStatsService(
            url="large_raster.tif", bands=[1], approx_stats=False
        )

        with pytest.raises(ValueError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Too many pixels" in str(exc_info.value)


def test_timeout_scenario():
    """Test handling of timeout scenarios when fetching remote rasters."""
    with patch("rasterio.open") as mock_open:
        # Simulate a timeout when trying to open the raster
        mock_open.side_effect = Timeout("Request timed out")

        service = ZonalStatsService(
            url="https://example.com/slow_raster.tif", bands=[1]
        )

        with pytest.raises(Timeout) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Request timed out" in str(exc_info.value)


def test_missing_crs_handling():
    """Test handling of rasters with missing CRS information."""
    with patch("rasterio.open") as mock_open:
        # Create a mock dataset with no CRS
        mock_dataset = MagicMock()
        mock_dataset.crs = None
        mock_open.return_value.__enter__.return_value = mock_dataset

        service = ZonalStatsService(url="no_crs_raster.tif", bands=[1])

        with pytest.raises(ValueError) as exc_info:
            service.calculate_stats(
                geometry=PolygonGeometry(**POLYGON_GEOMETRY),
                stats=[StatType.COUNT, StatType.MEAN],
            )

        assert "Source raster has no CRS defined" in str(exc_info.value)
