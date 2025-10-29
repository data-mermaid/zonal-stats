import os

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import StatType
from app.services.zonal_stats import ZonalStatsError, GeometryError, RasterError

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
    "buffer_size": 1000,
}


def test_root_endpoint():
    """Test the root endpoint returns correct information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs_url" in data
    assert "redoc_url" in data
    assert data["docs_url"] == "/docs"
    assert data["redoc_url"] == "/redoc"


def test_zonal_stats_with_image():
    """Test zonal statistics calculation with image configuration."""
    request_data = {
        "aoi": POLYGON_GEOMETRY,
        "stats": [StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1], "approx_stats": False},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 200
    data = response.json()

    assert "band_1" in data
    band_stats = data["band_1"]
    assert band_stats["count"] == 10
    assert band_stats["mean"] == 4.6
    assert band_stats["min"] == 3
    assert band_stats["max"] == 6


def test_zonal_stats_with_point():
    """Test zonal statistics calculation with point geometry."""
    request_data = {
        "aoi": POINT_GEOMETRY,
        "stats": [StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1], "approx_stats": False},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 200
    data = response.json()

    assert "band_1" in data
    band_stats = data["band_1"]
    assert band_stats["count"] > 0
    assert band_stats["min"] >= 0


def test_invalid_geometry():
    """Test error handling for invalid geometry."""
    invalid_geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-0.16, 51.5],
                [-0.11, 51.5],
                [-0.11, 51.52],
                [-0.16, 51.52],
                [-0.16, 51.5],
                [-0.11, 51.5],  # Duplicate point that makes the polygon self-intersecting
            ]
        ],
    }

    request_data = {
        "aoi": invalid_geometry,
        "stats": [StatType.COUNT],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 422
    error_details = response.json().get("detail") or []
    passes = False
    for error_detail in error_details:
        error_detail = error_detail.get("msg") or ""
        if "Polygon must be closed" in error_detail:
            passes = True
            break
    
    assert passes, "Expected geometry validation error not found"


def test_missing_source():
    """Test error handling when neither image nor stac is provided."""
    request_data = {"aoi": POLYGON_GEOMETRY, "stats": [StatType.COUNT]}

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 422  # Pydantic validation error
    error_detail = response.json()["detail"]
    assert any("Must specify either image or stac source" in str(err) for err in error_detail)


def test_both_sources_provided():
    """Test error handling when both image and stac are provided."""
    request_data = {
        "aoi": POLYGON_GEOMETRY,
        "stats": [StatType.COUNT],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1]},
        "stac": {"url": "https://example.com/stac", "asset": "test", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 422  # Pydantic validation error
    error_detail = response.json()["detail"]
    assert any("Cannot specify both image and stac sources" in str(err) for err in error_detail)


def test_all_stat_types():
    """Test calculation of all available statistics."""
    request_data = {
        "aoi": POLYGON_GEOMETRY,
        "stats": [
            StatType.COUNT,
            StatType.MEAN,
            StatType.MIN,
            StatType.MAX,
            StatType.SUM,
            StatType.STD,
            StatType.MEDIAN,
        ],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1], "approx_stats": False},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 200
    data = response.json()

    assert "band_1" in data
    band_stats = data["band_1"]
    assert all(
        stat in band_stats
        for stat in ["count", "mean", "min", "max", "sum", "std", "median"]
    )


def test_invalid_raster_url():
    """Test error handling for invalid raster URL."""
    request_data = {
        "aoi": POLYGON_GEOMETRY,
        "stats": [StatType.COUNT],
        "image": {"url": "file://invalid/path/to/raster.tif", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 400
    assert "Error opening raster file" in response.json()["detail"]


def test_invalid_url_format():
    """Test error handling for invalid URL format."""
    request_data = {
        "aoi": POLYGON_GEOMETRY,
        "stats": [StatType.COUNT],
        "image": {"url": "not-a-url", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 422  # Pydantic validation error
    error_detail = response.json()["detail"]
    assert any("URL must start with" in str(err) for err in error_detail)


def test_empty_stats_list():
    """Test error handling for empty statistics list."""
    request_data = {
        "aoi": POLYGON_GEOMETRY,
        "stats": [],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 422  # Pydantic validation error
    error_detail = response.json()["detail"]
    assert any("Statistics list cannot be empty" in str(err) for err in error_detail)


def test_invalid_point_coordinates():
    """Test error handling for invalid point coordinates."""
    invalid_point = {
        "type": "Point",
        "coordinates": [200, 100],  # Invalid coordinates
        "buffer_size": 1000,
    }

    request_data = {
        "aoi": invalid_point,
        "stats": [StatType.COUNT],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 422  # Pydantic validation error
    error_detail = response.json()["detail"]
    assert any("Longitude must be between -180 and 180" in str(err) for err in error_detail)


def test_invalid_buffer_size():
    """Test error handling for invalid buffer size."""
    invalid_point = {
        "type": "Point",
        "coordinates": [-0.135, 51.51],
        "buffer_size": -1000,  # Invalid buffer size
    }

    request_data = {
        "aoi": invalid_point,
        "stats": [StatType.COUNT],
        "image": {"url": f"file://{os.path.abspath(RASTER_PATH)}", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 422  # Pydantic validation error
    error_detail = response.json()["detail"]
    assert any("Buffer size must be greater than 0" in str(err) for err in error_detail)
