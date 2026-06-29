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
    assert band_stats.count == 10
    assert band_stats.mean == 4.6
    assert band_stats.min == 3
    assert band_stats.max == 6


def test_point_geometry_with_radius():
    """Test zonal statistics calculation for a point with radius."""
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    point = {
        "type": "Point",
        "coordinates": [-0.135, 51.51],  # Central point in our test area
        "radius": 1000,  # 1km radius
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
            radius=1000,
        )

    with pytest.raises(ValueError):
        PointGeometry(
            type="Point",
            coordinates=[-0.135, 100],  # Invalid latitude
            radius=1000,
        )


def test_invalid_radius():
    """Test validation of negative radius."""
    with pytest.raises(ValueError):
        PointGeometry(
            type="Point",
            coordinates=[-0.135, 51.5],
            radius=-1000,  # Negative radius
        )


def test_point_without_radius():
    """Test single-pixel sampling for a point without radius."""
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    point = {
        "type": "Point",
        "coordinates": [-0.135, 51.51],
    }

    service = ZonalStatsService(url=raster_path, bands=[1], approx_stats=False)

    results = service.calculate_stats(
        geometry=PointGeometry(**point),
        stats=[
            StatType.COUNT,
            StatType.MEAN,
            StatType.MIN,
            StatType.MAX,
            StatType.STD,
        ],
    )

    assert "band_1" in results
    band_stats = results["band_1"]
    # Single pixel: count is 0 or 1
    assert band_stats.count in (0, 1)
    if band_stats.count == 1:
        # For a single pixel, min == max == mean
        assert band_stats.min == band_stats.max
        assert band_stats.min == band_stats.mean
        assert band_stats.std == 0.0
    assert band_stats.aoi_area == 0.0


def test_point_outside_raster_extent():
    """A point outside the raster returns null stats."""
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    # Far from the central London test raster
    point = {
        "type": "Point",
        "coordinates": [10.0, 10.0],
    }

    service = ZonalStatsService(url=raster_path, bands=[1], approx_stats=False)

    results = service.calculate_stats(
        geometry=PointGeometry(**point),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
    )

    assert "band_1" in results
    band_stats = results["band_1"]
    assert band_stats.count is None
    assert band_stats.mean is None
    assert band_stats.min is None
    assert band_stats.max is None
    # A point AOI has no area, but aoi_area is still reported.
    assert band_stats.aoi_area == 0.0
    assert band_stats.data_area is None


def test_buffered_point_outside_raster_extent():
    """A buffered point (radius > 0) outside the raster returns null stats.

    This exercises the polygon code path (create_buffer_polygon -> intersects
    check), distinct from the no-radius _sample_point path above.
    """
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    # Far from the central London test raster
    point = {
        "type": "Point",
        "coordinates": [10.0, 10.0],
        "radius": 1000,
    }

    service = ZonalStatsService(url=raster_path, bands=[1], approx_stats=False)

    results = service.calculate_stats(
        geometry=PointGeometry(**point),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
    )

    assert "band_1" in results
    band_stats = results["band_1"]
    assert band_stats.count is None
    assert band_stats.mean is None
    # A buffered point has area, so aoi_area is reported even outside the extent.
    assert band_stats.aoi_area is not None
    assert band_stats.aoi_area > 0
    assert band_stats.data_area is None


def test_polygon_outside_raster_extent():
    """A polygon outside the raster returns null stats."""
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    # Far from the central London test raster
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [10.0, 10.0],
                [10.01, 10.0],
                [10.01, 10.01],
                [10.0, 10.01],
                [10.0, 10.0],
            ]
        ],
    }

    service = ZonalStatsService(url=raster_path, bands=[1], approx_stats=False)

    results = service.calculate_stats(
        geometry=PolygonGeometry(**polygon),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
    )

    assert "band_1" in results
    band_stats = results["band_1"]
    assert band_stats.count is None
    assert band_stats.mean is None
    # aoi_area describes the query geometry, so it is reported even when the
    # AOI falls outside the raster extent.
    assert band_stats.aoi_area is not None
    assert band_stats.aoi_area > 0
    assert band_stats.data_area is None


def test_multi_band_outside_raster_extent():
    """An out-of-extent AOI returns null stats for every requested band.

    The out-of-coverage early return builds its result dict by iterating
    ``self.bands`` before any pixel data is read, so this exercises multi-band
    propagation even though the test fixture is single-band -- the early return
    fires before band indexes are validated against the raster.
    """
    raster_path = os.path.join(
        "tests", "data", "random_centrallondon_raster_cog_001.tif"
    )
    # Far from the central London test raster
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [10.0, 10.0],
                [10.01, 10.0],
                [10.01, 10.01],
                [10.0, 10.01],
                [10.0, 10.0],
            ]
        ],
    }

    service = ZonalStatsService(url=raster_path, bands=[1, 2, 3], approx_stats=False)

    results = service.calculate_stats(
        geometry=PolygonGeometry(**polygon),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
    )

    # Every requested band is present with null stats.
    assert set(results) == {"band_1", "band_2", "band_3"}
    for band_stats in results.values():
        assert band_stats.count is None
        assert band_stats.mean is None
        assert band_stats.min is None
        assert band_stats.max is None
        # aoi_area describes the query geometry and is reported on every band.
        assert band_stats.aoi_area is not None
        assert band_stats.aoi_area > 0
        assert band_stats.data_area is None


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
