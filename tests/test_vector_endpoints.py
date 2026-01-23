"""Tests for vector endpoints (/api/v1/zonal-stats/vector)."""

import os

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import StatType

client = TestClient(app)

# Test data
VECTOR_PATH = os.path.join("tests", "data", "test_vector.parquet")
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

POINT_GEOMETRY = {
    "type": "Point",
    "coordinates": [-0.135, 51.51],
    "buffer_size": 1000,
}

# Geometry that doesn't intersect with test vector data
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


# =============================================================================
# Vector Endpoint Tests - Intersect Mode
# =============================================================================


def test_vector_stats_intersect_mode():
    """Test vector statistics with intersection mode."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population", "median_income"],
            "intersection_mode": "intersect",
            "stats": [StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Check both columns have results
    assert "population" in data
    assert "median_income" in data

    # Check population stats
    pop_stats = data["population"]
    assert pop_stats["count"] > 0
    assert pop_stats["min"] >= 1000  # Min population in test data
    assert pop_stats["max"] <= 3000  # Max population in test data


def test_vector_stats_touch_mode():
    """Test vector statistics with touch mode."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population"],
            "intersection_mode": "touch",
            "stats": [StatType.COUNT, StatType.MEAN, StatType.STD],
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert "population" in data
    pop_stats = data["population"]
    assert pop_stats["count"] > 0
    assert "std" in pop_stats


def test_vector_stats_with_point():
    """Test vector statistics with point geometry."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POINT_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population"],
            "stats": [StatType.COUNT, StatType.MEAN],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "population" in data


def test_vector_stats_density():
    """Test density statistic with vector data."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population"],
            "stats": [StatType.COUNT, StatType.DENSITY],
        },
    )
    assert response.status_code == 200
    data = response.json()

    pop_stats = data["population"]
    assert "density" in pop_stats
    assert pop_stats["density"] >= 0


def test_vector_stats_data_area():
    """Test data_area statistic with vector data."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population"],
            "stats": [StatType.COUNT, StatType.DATA_AREA],
        },
    )
    assert response.status_code == 200
    data = response.json()

    pop_stats = data["population"]
    assert "data_area" in pop_stats
    assert pop_stats["data_area"] >= 0


def test_vector_stats_includes_area_stats():
    """Test that aoi_area and data_area are always included."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population"],
            "stats": [StatType.COUNT],  # Only request count
        },
    )
    assert response.status_code == 200
    data = response.json()

    pop_stats = data["population"]
    assert "aoi_area" in pop_stats
    assert "data_area" in pop_stats


def test_vector_stats_empty_result():
    """Test vector stats with geometry that doesn't intersect any features."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": NON_INTERSECTING_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population"],
            "stats": [StatType.COUNT, StatType.MEAN, StatType.DENSITY],
        },
    )
    assert response.status_code == 200
    data = response.json()

    pop_stats = data["population"]
    assert pop_stats["count"] == 0
    assert pop_stats["mean"] is None
    assert pop_stats["density"] == 0


def test_vector_stats_multiple_columns():
    """Test calculation of statistics for multiple columns."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population", "median_income"],
            "stats": [
                StatType.COUNT,
                StatType.MEAN,
                StatType.MIN,
                StatType.MAX,
                StatType.SUM,
                StatType.DENSITY,
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Check both columns have all stats
    for col in ["population", "median_income"]:
        stats = data[col]
        assert "count" in stats
        assert "mean" in stats
        assert "min" in stats
        assert "max" in stats
        assert "sum" in stats
        assert "density" in stats


# =============================================================================
# Vector Endpoint Error Tests
# =============================================================================


def test_vector_stats_invalid_column():
    """Test error handling for invalid column in vector config."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["nonexistent_column"],
        },
    )
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


def test_vector_stats_invalid_url():
    """Test error handling for invalid vector URL."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": "file:///nonexistent/path/to/file.parquet",
            "columns": ["population"],
        },
    )
    assert response.status_code == 400


def test_vector_stats_invalid_url_format():
    """Test error handling for invalid vector URL format."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": "not-a-valid-url",
            "columns": ["population"],
        },
    )
    assert response.status_code == 422


def test_vector_stats_unsupported_format():
    """Test 415 error for non-GeoParquet vector formats."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": "file:///path/to/file.geojson",
            "columns": ["population"],
        },
    )
    assert response.status_code == 415
    assert "GeoParquet" in response.json()["detail"]


def test_vector_stats_unsupported_shapefile():
    """Test 415 error for shapefile format."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": "https://example.com/data.shp",
            "columns": ["value"],
        },
    )
    assert response.status_code == 415


def test_vector_stats_geoparquet_extension():
    """Test that .geoparquet extension is accepted.

    Note: File may not exist, but format validation passes.
    """
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": "file:///path/to/file.geoparquet",
            "columns": ["population"],
        },
    )
    # Should not be 415 - format is valid, will fail for other reasons
    assert response.status_code != 415


def test_vector_stats_empty_columns():
    """Test error when no columns are specified."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": [],  # Empty columns list
        },
    )
    assert response.status_code == 422


def test_vector_stats_default_values():
    """Test that default values work correctly."""
    response = client.post(
        "/api/v1/zonal-stats/vector",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(VECTOR_PATH)}",
            "columns": ["population"],
            # No intersection_mode, geometry_column, stats - should use defaults
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "population" in data
