"""Tests for STAC integration endpoints."""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import StatType

client = TestClient(app)

# Test data
RASTER_PATH = os.path.join("tests", "data", "random_centrallondon_raster_cog_001.tif")
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

# Mock STAC responses for raster
MOCK_STAC_RASTER_RESPONSE = {
    "assets": {
        "red": {
            "href": RASTER_PATH,
            "type": "image/tiff; application=geotiff",
            "roles": ["data"],
        },
        "nir": {
            "href": RASTER_PATH,
            "type": "image/tiff; application=geotiff",
            "roles": ["data"],
        },
    }
}

# Mock STAC responses for vector
MOCK_STAC_VECTOR_RESPONSE = {
    "assets": {
        "data": {
            "href": VECTOR_PATH,
            "type": "application/geoparquet",
            "roles": ["data"],
        },
    }
}

MOCK_STAC_RESPONSE_NO_ASSETS = {"assets": {}}

MOCK_STAC_RESPONSE_NO_HREF = {
    "assets": {
        "red": {
            "type": "image/tiff; application=geotiff",
            "roles": ["data"],
        }
    }
}


# =============================================================================
# Raster STAC Tests
# =============================================================================


def test_raster_stac_with_specific_asset():
    """Test raster STAC statistics with specific asset."""
    with patch("app.services.stac.requests.get") as mock_get:
        mock_response = mock_get.return_value
        mock_response.json.return_value = MOCK_STAC_RASTER_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200

        response = client.post(
            "/api/v1/zonal-stats/raster/stac",
            json={
                "aoi": POLYGON_GEOMETRY,
                "url": "https://example.com/stac/item.json",
                "asset": "red",
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


def test_raster_stac_without_asset():
    """Test raster STAC statistics using first asset (default)."""
    with patch("app.services.stac.requests.get") as mock_get:
        mock_response = mock_get.return_value
        mock_response.json.return_value = MOCK_STAC_RASTER_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200

        response = client.post(
            "/api/v1/zonal-stats/raster/stac",
            json={
                "aoi": POLYGON_GEOMETRY,
                "url": "https://example.com/stac/item.json",
                "bands": [1],
                "stats": [StatType.COUNT, StatType.MEAN],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "band_1" in data


# =============================================================================
# Vector STAC Tests
# =============================================================================


def test_vector_stac_basic():
    """Test vector STAC statistics with GeoParquet asset."""
    with patch("app.services.stac.requests.get") as mock_get:
        mock_response = mock_get.return_value
        mock_response.json.return_value = MOCK_STAC_VECTOR_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200

        response = client.post(
            "/api/v1/zonal-stats/vector/stac",
            json={
                "aoi": POLYGON_GEOMETRY,
                "url": "https://example.com/stac/vector-item.json",
                "asset": "data",
                "columns": ["population", "median_income"],
                "stats": [StatType.COUNT, StatType.MEAN],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "population" in data
        assert "median_income" in data


def test_vector_stac_unsupported_format():
    """Test error when STAC asset is not GeoParquet."""
    with patch("app.services.stac.requests.get") as mock_get:
        # Return a STAC item with a non-GeoParquet asset
        mock_response = mock_get.return_value
        mock_response.json.return_value = {
            "assets": {
                "data": {
                    "href": "https://example.com/data.geojson",
                    "type": "application/geo+json",
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200

        response = client.post(
            "/api/v1/zonal-stats/vector/stac",
            json={
                "aoi": POLYGON_GEOMETRY,
                "url": "https://example.com/stac/vector-item.json",
                "columns": ["value"],
            },
        )
        assert response.status_code == 415
        assert "GeoParquet" in response.json()["detail"]
