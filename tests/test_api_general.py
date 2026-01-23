"""Tests for general API functionality."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns correct information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["version"] == "0.2.0"
    assert "endpoints" in data
    assert "raster" in data["endpoints"]
    assert "vector" in data["endpoints"]
    assert "raster_stac" in data["endpoints"]
    assert "vector_stac" in data["endpoints"]


def test_docs_endpoint():
    """Test that Swagger docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_redoc_endpoint():
    """Test that ReDoc is accessible."""
    response = client.get("/redoc")
    assert response.status_code == 200


def test_openapi_schema():
    """Test that OpenAPI schema is accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Zonal Statistics API"
    assert data["info"]["version"] == "0.2.0"
    # Check that new endpoints are in the schema
    paths = data["paths"]
    assert "/api/v1/zonal-stats/raster" in paths
    assert "/api/v1/zonal-stats/raster/stac" in paths
    assert "/api/v1/zonal-stats/vector" in paths
    assert "/api/v1/zonal-stats/vector/stac" in paths


def test_nonexistent_endpoint():
    """Test that nonexistent endpoints return 404."""
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404


def test_old_endpoint_removed():
    """Test that the old unified endpoint no longer exists."""
    response = client.post(
        "/api/v1/zonal-stats",
        json={"aoi": {"type": "Point", "coordinates": [0, 0]}},
    )
    assert response.status_code == 404
