"""STAC item fetching and asset extraction utilities."""

import logging

import requests

from .zonal_stats import STACError, UnsupportedMediaTypeError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_asset_url(stac_url: str, asset_key: str | None = None) -> str:
    """
    Fetch STAC item and extract asset URL.

    Args:
        stac_url: URL to STAC Item JSON
        asset_key: Specific asset key, or None for first asset

    Returns:
        Asset href URL

    Raises:
        STACError: If fetch fails or asset not found
    """
    try:
        logger.info(f"Fetching STAC item from {stac_url}")
        resp = requests.get(stac_url, timeout=30)
        resp.raise_for_status()
        stac_item = resp.json()
        assets = stac_item.get("assets", {})

        if not assets:
            raise STACError("No assets found in the STAC item.")

        if asset_key:
            asset = assets.get(asset_key)
            if not asset:
                raise STACError(f"Asset '{asset_key}' not found in the STAC item.")
        else:
            # Use the first asset if no key is provided
            asset = next(iter(assets.values()))

        href = asset.get("href")
        logger.info(f"Asset href: {href}")

        if not href:
            if asset_key:
                raise STACError(
                    f"Asset '{asset_key}' does not contain an 'href' field."
                )
            else:
                raise STACError("The first asset does not contain an 'href' field.")

        return href
    except requests.RequestException as e:
        raise STACError(f"Error fetching STAC item: {str(e)}") from e
    except STACError:
        raise
    except Exception as e:
        raise STACError(f"Unexpected error processing STAC item: {str(e)}") from e


def get_asset_media_type(stac_url: str, asset_key: str | None = None) -> str | None:
    """
    Get the media type of a STAC asset.

    Args:
        stac_url: URL to STAC Item JSON
        asset_key: Specific asset key, or None for first asset

    Returns:
        Media type string or None if not specified
    """
    try:
        resp = requests.get(stac_url, timeout=30)
        resp.raise_for_status()
        stac_item = resp.json()
        assets = stac_item.get("assets", {})

        if not assets:
            return None

        if asset_key:
            asset = assets.get(asset_key)
        else:
            asset = next(iter(assets.values()), None)

        if not asset:
            return None

        return asset.get("type")
    except Exception:
        return None


def validate_vector_asset(stac_url: str, asset_key: str | None = None) -> str:
    """
    Validate that a STAC asset is a GeoParquet file.

    Args:
        stac_url: URL to STAC Item JSON
        asset_key: Specific asset key, or None for first asset

    Returns:
        Asset href URL if valid

    Raises:
        UnsupportedMediaTypeError: If not a GeoParquet file
        STACError: If fetch fails or asset not found
    """
    href = get_asset_url(stac_url, asset_key)

    # Check URL extension
    url_path = href.split("?")[0].lower()
    if url_path.endswith((".parquet", ".geoparquet")):
        return href

    # Check media type if available
    media_type = get_asset_media_type(stac_url, asset_key)
    geoparquet_media_types = [
        "application/x-parquet",
        "application/vnd.apache.parquet",
        "application/geoparquet",
    ]

    if media_type and media_type.lower() in geoparquet_media_types:
        return href

    raise UnsupportedMediaTypeError(
        "Unsupported vector format. Only GeoParquet files (.parquet, .geoparquet) "
        "are supported. The STAC asset does not appear to be a GeoParquet file."
    )
