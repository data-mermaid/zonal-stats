import os
from unittest.mock import patch

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

# Mock STAC responses
MOCK_STAC_RESPONSE = {
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

MOCK_STAC_RESPONSE_NO_ASSETS = {"assets": {}}

MOCK_STAC_RESPONSE_NO_HREF = {
    "assets": {
        "red": {
            "type": "image/tiff; application=geotiff",
            "roles": ["data"],
        }
    }
}


def test_stac_integration_with_specific_asset():
    """Test zonal statistics calculation with STAC configuration and specific asset."""
    with patch("requests.get") as mock_get:
        # Create a mock response object
        mock_response = mock_get.return_value
        mock_response.json.return_value = MOCK_STAC_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200

        request_data = {
            "aoi": POLYGON_GEOMETRY,
            "stats": [StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
            "stac": {
                "url": "https://example.com/stac/item.json",
                "asset": "red",
                "bands": [1],
                "approx_stats": False,
            },
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

        # Verify the STAC API was called correctly
        mock_get.assert_called_once_with("https://example.com/stac/item.json")


def test_stac_integration_without_asset():
    """Test zonal statistics calculation with STAC config without asset."""
    with patch("requests.get") as mock_get:
        # Create a mock response object
        mock_response = mock_get.return_value
        mock_response.json.return_value = MOCK_STAC_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200

        request_data = {
            "aoi": POLYGON_GEOMETRY,
            "stats": [StatType.COUNT, StatType.MEAN, StatType.MIN, StatType.MAX],
            "stac": {
                "url": "https://example.com/stac/item.json",
                "bands": [1],
                "approx_stats": False,
            },
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

        # Verify the STAC API was called correctly
        mock_get.assert_called_once_with("https://example.com/stac/item.json")
