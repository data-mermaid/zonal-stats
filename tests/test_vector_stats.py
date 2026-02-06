"""Unit tests for ZonalVectorService."""

import os

import pytest

from app.models.schemas import PointGeometry, PolygonGeometry, StatType
from app.services.zonal_stats import VectorError
from app.services.zonal_vector import ZonalVectorService

# Test data paths
VECTOR_PATH = os.path.join("tests", "data", "test_vector.parquet")

# Test geometries that intersect with our test data
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

# Point in central London with radius
POINT_GEOMETRY = {
    "type": "Point",
    "coordinates": [-0.135, 51.51],
    "radius": 2000,  # 2km radius
}

# Geometry that doesn't intersect with test data
NON_INTERSECTING_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [
            [-1.0, 50.0],
            [-0.9, 50.0],
            [-0.9, 50.1],
            [-1.0, 50.1],
            [-1.0, 50.0],
        ]
    ],
}


def test_vector_stats_polygon_intersect_mode():
    """Test vector statistics calculation with polygon in intersect mode."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population", "median_income"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX, StatType.SUM],
    )

    # Should have results for both columns
    assert "population" in results
    assert "median_income" in results

    # Check population stats
    pop_stats = results["population"]
    assert pop_stats.count > 0
    assert pop_stats.min >= 1000  # Min population in test data
    assert pop_stats.max <= 3000  # Max population in test data


def test_vector_stats_polygon_touch_mode():
    """Test vector statistics calculation with polygon in touch mode."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="touch",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX, StatType.STD],
    )

    assert "population" in results
    pop_stats = results["population"]
    assert pop_stats.count > 0
    assert hasattr(pop_stats, "std")


def test_vector_stats_with_point():
    """Test vector statistics calculation with point geometry and buffer."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    results = service.calculate_stats(
        geometry=PointGeometry(**POINT_GEOMETRY),
        stats=[StatType.COUNT, StatType.MEAN],
    )

    assert "population" in results
    pop_stats = results["population"]
    assert pop_stats.count >= 0  # Might be 0 or more depending on buffer


def test_vector_stats_density():
    """Test density statistic calculation."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[StatType.COUNT, StatType.DENSITY],
    )

    pop_stats = results["population"]
    assert hasattr(pop_stats, "density")
    assert pop_stats.density >= 0  # Features per km²


def test_vector_stats_total_area():
    """Test total_area statistic calculation."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[StatType.COUNT, StatType.DATA_AREA],
    )

    pop_stats = results["population"]
    assert hasattr(pop_stats, "data_area")
    assert pop_stats.data_area >= 0  # Area in square meters


def test_vector_stats_empty_result():
    """Test handling of empty results when no features intersect."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**NON_INTERSECTING_GEOMETRY),
        stats=[StatType.COUNT, StatType.MEAN, StatType.DENSITY],
    )

    pop_stats = results["population"]
    assert pop_stats.count == 0
    assert pop_stats.mean is None
    assert pop_stats.density == 0


def test_vector_stats_invalid_column():
    """Test error handling for invalid column names."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["nonexistent_column"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    with pytest.raises(VectorError) as exc_info:
        service.calculate_stats(
            geometry=PolygonGeometry(**POLYGON_GEOMETRY),
            stats=[StatType.COUNT],
        )

    assert "not found" in str(exc_info.value).lower()


def test_vector_stats_invalid_geometry_column():
    """Test error handling for invalid geometry column."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="invalid_geom",
        intersection_mode="intersect",
    )

    with pytest.raises(VectorError) as exc_info:
        service.calculate_stats(
            geometry=PolygonGeometry(**POLYGON_GEOMETRY),
            stats=[StatType.COUNT],
        )

    assert "geometry column" in str(exc_info.value).lower()


def test_vector_stats_invalid_url():
    """Test error handling for invalid file URL."""
    service = ZonalVectorService(
        url="file:///nonexistent/path/to/file.parquet",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    with pytest.raises(VectorError):
        service.calculate_stats(
            geometry=PolygonGeometry(**POLYGON_GEOMETRY),
            stats=[StatType.COUNT],
        )


def test_vector_stats_median():
    """Test median statistic calculation."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="touch",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[StatType.MEDIAN],
    )

    pop_stats = results["population"]
    assert hasattr(pop_stats, "median")


def test_vector_stats_unique():
    """Test unique values statistic calculation."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="touch",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[StatType.UNIQUE],
    )

    pop_stats = results["population"]
    assert hasattr(pop_stats, "unique")
    assert isinstance(pop_stats.unique, list)


def test_vector_stats_range():
    """Test range statistic calculation."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population"],
        geometry_column="geometry",
        intersection_mode="touch",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[StatType.MIN, StatType.MAX, StatType.RANGE],
    )

    pop_stats = results["population"]
    assert hasattr(pop_stats, "range")
    if pop_stats.min is not None and pop_stats.max is not None:
        assert pop_stats.range == pop_stats.max - pop_stats.min


def test_vector_stats_all_stats():
    """Test calculation of multiple statistics at once."""
    service = ZonalVectorService(
        url=f"file://{os.path.abspath(VECTOR_PATH)}",
        columns=["population", "median_income"],
        geometry_column="geometry",
        intersection_mode="intersect",
    )

    results = service.calculate_stats(
        geometry=PolygonGeometry(**POLYGON_GEOMETRY),
        stats=[
            StatType.COUNT,
            StatType.MEAN,
            StatType.MIN,
            StatType.MAX,
            StatType.SUM,
            StatType.DENSITY,
            StatType.DATA_AREA,
        ],
    )

    # Check both columns have all stats
    for col in ["population", "median_income"]:
        stats = results[col]
        assert hasattr(stats, "count")
        assert hasattr(stats, "mean")
        assert hasattr(stats, "min")
        assert hasattr(stats, "max")
        assert hasattr(stats, "sum")
        assert hasattr(stats, "density")
        assert hasattr(stats, "data_area")


def test_validate_geometry():
    """Test the validate_geometry static method."""
    # Valid polygon
    assert (
        ZonalVectorService.validate_geometry(PolygonGeometry(**POLYGON_GEOMETRY))
        is True
    )

    # Valid point
    assert ZonalVectorService.validate_geometry(PointGeometry(**POINT_GEOMETRY)) is True
