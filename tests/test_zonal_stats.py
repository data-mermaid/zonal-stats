import os

import pytest

from app.models.schemas import PointGeometry, PolygonGeometry, StatType
from app.services.zonal_stats import ZonalStatsService


def test_zonal_stats_central_london():
    """Test zonal statistics calculation for a polygon in central London."""
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    polygon = {
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

    # Create service instance
    service = ZonalStatsService(url=raster_path, bands=[1], approx_stats=False)

    # Calculate stats
    results = service.calculate_stats(
        geometry=PolygonGeometry(**polygon),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
    )

    # Assert results
    assert "band_1" in results
    band_stats = results["band_1"]
    assert band_stats.count == 12
    assert band_stats.mean == 4.6
    assert band_stats.min == 3
    assert band_stats.max == 6


def test_point_geometry_with_buffer():
    """Test zonal statistics calculation for a point with buffer."""
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    point = {
        "type": "Point",
        "coordinates": [-0.135, 51.51],  # Central point in our test area
        "buffer_size": 1000,  # 1km buffer
    }

    service = ZonalStatsService(url=raster_path, bands=[1], approx_stats=False)

    results = service.calculate_stats(
        geometry=PointGeometry(**point),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
    )

    assert "band_1" in results
    band_stats = results["band_1"]
    assert band_stats.count > 0  # Should have some pixels
    assert band_stats.min >= 0  # Values should be non-negative


def test_invalid_point_coordinates():
    """Test validation of invalid point coordinates."""
    with pytest.raises(ValueError):
        PointGeometry(
            type="Point",
            coordinates=[200, 51.5],  # Invalid longitude
            buffer_size=1000,
        )

    with pytest.raises(ValueError):
        PointGeometry(
            type="Point",
            coordinates=[-0.135, 100],  # Invalid latitude
            buffer_size=1000,
        )


def test_invalid_buffer_size():
    """Test validation of invalid buffer size."""
    with pytest.raises(ValueError):
        PointGeometry(
            type="Point",
            coordinates=[-0.135, 51.5],
            buffer_size=-1000,  # Negative buffer size
        )


def test_all_stat_types():
    """Test calculation of all available statistics."""
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    polygon = {
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

    service = ZonalStatsService(url=raster_path, bands=[1], approx_stats=False)

    results = service.calculate_stats(
        geometry=PolygonGeometry(**polygon),
        stats=[
            StatType.COUNT,
            StatType.MEAN,
            StatType.MIN,
            StatType.MAX,
            StatType.SUM,
            StatType.STD,
            StatType.MEDIAN,
        ],
    )

    assert "band_1" in results
    band_stats = results["band_1"]
    assert hasattr(band_stats, "count")
    assert hasattr(band_stats, "mean")
    assert hasattr(band_stats, "min")
    assert hasattr(band_stats, "max")
    assert hasattr(band_stats, "sum")
    assert hasattr(band_stats, "std")
    assert hasattr(band_stats, "median")
