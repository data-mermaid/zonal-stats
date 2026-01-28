"""Tests for raster endpoints (/api/v1/zonal-stats/raster)."""

import os

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import StatType

client = TestClient(app)

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

POINT_GEOMETRY = {
    "type": "Point",
    "coordinates": [-0.135, 51.51],
    "radius": 1000,
}


# =============================================================================
# Raster Endpoint Tests
# =============================================================================


def test_raster_stats_basic():
    """Test basic raster statistics calculation."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
            "stats": [StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert "band_1" in data
    band_stats = data["band_1"]
    assert band_stats["count"] == 10
    assert band_stats["mean"] == 4.6
    assert band_stats["min"] == 3
    assert band_stats["max"] == 6


def test_raster_stats_with_point():
    """Test raster statistics calculation with point geometry."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POINT_GEOMETRY,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
            "stats": [StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert "band_1" in data
    band_stats = data["band_1"]
    assert band_stats["count"] > 0
    assert band_stats["min"] >= 0


def test_raster_stats_all_stat_types():
    """Test calculation of all available raster statistics."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
            "stats": [
                StatType.COUNT,
                StatType.MEAN,
                StatType.MIN,
                StatType.MAX,
                StatType.SUM,
                StatType.STD,
                StatType.MEDIAN,
            ],
            "approx_stats": False,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert "band_1" in data
    band_stats = data["band_1"]
    assert all(
        stat in band_stats
        for stat in ["count", "mean", "min", "max", "sum", "std", "median"]
    )


def test_raster_stats_includes_area_stats():
    """Test that aoi_area and data_area are always included."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
            "stats": [StatType.COUNT],  # Only request count
        },
    )
    assert response.status_code == 200
    data = response.json()

    band_stats = data["band_1"]
    assert "aoi_area" in band_stats
    assert "data_area" in band_stats
    assert band_stats["aoi_area"] > 0
    assert band_stats["data_area"] >= 0


def test_raster_stats_invalid_url():
    """Test error handling for invalid raster URL."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": "file://invalid/path/to/raster.tif",
            "bands": [1],
        },
    )
    assert response.status_code == 400
    assert "Error opening raster file" in response.json()["detail"]


def test_raster_stats_invalid_url_format():
    """Test error handling for invalid URL format."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": "not-a-url",
            "bands": [1],
        },
    )
    assert response.status_code == 422
    error_detail = response.json()["detail"]
    assert any("URL must start with" in str(err) for err in error_detail)


def test_raster_stats_empty_stats_list():
    """Test error handling for empty statistics list."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
            "stats": [],
        },
    )
    assert response.status_code == 422
    error_detail = response.json()["detail"]
    assert any("Statistics list cannot be empty" in str(err) for err in error_detail)


def test_raster_stats_point_without_radius():
    """Test that Point without radius returns 400 for raster endpoints."""
    point_no_radius = {
        "type": "Point",
        "coordinates": [-0.135, 51.51],
    }

    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": point_no_radius,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
        },
    )
    assert response.status_code == 400
    assert "radius" in response.json()["detail"].lower()


def test_raster_stats_invalid_point_coordinates():
    """Test error handling for invalid point coordinates."""
    invalid_point = {
        "type": "Point",
        "coordinates": [200, 100],  # Invalid coordinates
        "radius": 1000,
    }

    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": invalid_point,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
        },
    )
    assert response.status_code == 422
    error_detail = response.json()["detail"]
    assert any(
        "Longitude must be between -180 and 180" in str(err) for err in error_detail
    )


def test_raster_stats_invalid_radius():
    """Test error handling for negative radius."""
    invalid_point = {
        "type": "Point",
        "coordinates": [-0.135, 51.51],
        "radius": -1000,
    }

    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": invalid_point,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
        },
    )
    assert response.status_code == 422
    error_detail = response.json()["detail"]
    assert any("Radius must be non-negative" in str(err) for err in error_detail)


def test_raster_stats_invalid_geometry():
    """Test error handling for invalid polygon geometry."""
    invalid_geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-0.16, 51.5],
                [-0.11, 51.5],
                [-0.11, 51.52],
                [-0.16, 51.52],
                [-0.16, 51.5],
                [-0.11, 51.5],  # Extra point makes it invalid
            ]
        ],
    }

    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": invalid_geometry,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            "bands": [1],
        },
    )
    assert response.status_code == 422
    error_detail = response.json().get("detail") or []
    passes = False
    for err in error_detail:
        error_msg = err.get("msg") or ""
        if "Polygon must be closed" in error_msg:
            passes = True
            break
    assert passes, "Expected geometry validation error not found"


def test_raster_stats_default_values():
    """Test that default values work correctly."""
    response = client.post(
        "/api/v1/zonal-stats/raster",
        json={
            "aoi": POLYGON_GEOMETRY,
            "url": f"file://{os.path.abspath(RASTER_PATH)}",
            # No bands, stats, or approx_stats - should use defaults
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "band_1" in data  # Default band is [1]
