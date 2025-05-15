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
        "image": {"url": RASTER_PATH, "bands": [1], "approx_stats": False},
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
        "image": {"url": RASTER_PATH, "bands": [1], "approx_stats": False},
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
                [
                    -0.11,
                    51.5,
                ],  # Duplicate point that makes the polygon self-intersecting
            ]
        ],
    }

    request_data = {
        "aoi": invalid_geometry,
        "stats": [StatType.COUNT],
        "image": {"url": RASTER_PATH, "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 400
    assert "Invalid geometry provided" in response.json()["detail"]


def test_missing_source():
    """Test error handling when neither image nor stac is provided."""
    request_data = {"aoi": POLYGON_GEOMETRY, "stats": [StatType.COUNT]}

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 400
    assert (
        "Exactly one of image or stac configuration must be provided"
        in response.json()["detail"]
    )


def test_both_sources_provided():
    """Test error handling when both image and stac are provided."""
    request_data = {
        "aoi": POLYGON_GEOMETRY,
        "stats": [StatType.COUNT],
        "image": {"url": RASTER_PATH, "bands": [1]},
        "stac": {"url": "https://example.com/stac", "asset": "test", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 400
    assert (
        "Exactly one of image or stac configuration must be provided"
        in response.json()["detail"]
    )


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
        "image": {"url": RASTER_PATH, "bands": [1], "approx_stats": False},
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
        "image": {"url": "invalid/path/to/raster.tif", "bands": [1]},
    }

    response = client.post("/api/v1/zonal-stats", json=request_data)
    assert response.status_code == 500
    assert "Error calculating zonal statistics" in response.json()["detail"]
