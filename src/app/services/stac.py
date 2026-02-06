"""STAC item fetching and asset extraction utilities."""

import logging
from dataclasses import dataclass

import requests

from .zonal_stats import STACError, UnsupportedMediaTypeError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AssetInfo:
    """Information extracted from a STAC asset."""

    href: str
    media_type: str | None = None


def _fetch_stac_item(stac_url: str) -> dict:
    """Fetch and parse a STAC item JSON.

    Args:
        stac_url: URL to STAC Item JSON

    Returns:
        Parsed STAC item dict

    Raises:
        STACError: If fetch fails or response is invalid
    """
    try:
        logger.info(f"Fetching STAC item from {stac_url}")
        resp = requests.get(stac_url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise STACError(f"Error fetching STAC item: {str(e)}") from e
    except Exception as e:
        raise STACError(f"Unexpected error processing STAC item: {str(e)}") from e


def _extract_asset(stac_item: dict, asset_key: str | None = None) -> AssetInfo:
    """Extract asset info from a parsed STAC item.

    Args:
        stac_item: Parsed STAC item dict
        asset_key: Specific asset key, or None for first asset

    Returns:
        AssetInfo with href and media_type

    Raises:
        STACError: If asset not found or missing href
    """
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
    if not href:
        if asset_key:
            raise STACError(f"Asset '{asset_key}' does not contain an 'href' field.")
        else:
            raise STACError("The first asset does not contain an 'href' field.")

    logger.info(f"Asset href: {href}")
    return AssetInfo(href=href, media_type=asset.get("type"))


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
    stac_item = _fetch_stac_item(stac_url)
    asset_info = _extract_asset(stac_item, asset_key)
    return asset_info.href


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
        stac_item = _fetch_stac_item(stac_url)
        asset_info = _extract_asset(stac_item, asset_key)
        return asset_info.media_type
    except Exception:
        return None


def validate_vector_asset(stac_url: str, asset_key: str | None = None) -> str:
    """
    Validate that a STAC asset is a GeoParquet file.

    Fetches the STAC item once and validates both href extension and media type.

    Args:
        stac_url: URL to STAC Item JSON
        asset_key: Specific asset key, or None for first asset

    Returns:
        Asset href URL if valid

    Raises:
        UnsupportedMediaTypeError: If not a GeoParquet file
        STACError: If fetch fails or asset not found
    """
    # Fetch once and extract both href and media type
    stac_item = _fetch_stac_item(stac_url)
    asset_info = _extract_asset(stac_item, asset_key)

    # Check URL extension
    url_path = asset_info.href.split("?")[0].lower()
    if url_path.endswith((".parquet", ".geoparquet")):
        return asset_info.href

    # Check media type if available
    geoparquet_media_types = [
        "application/x-parquet",
        "application/vnd.apache.parquet",
        "application/geoparquet",
    ]

    if (
        asset_info.media_type
        and asset_info.media_type.lower() in geoparquet_media_types
    ):
        return asset_info.href

    raise UnsupportedMediaTypeError(
        "Unsupported vector format. Only GeoParquet files (.parquet, .geoparquet) "
        "are supported. The STAC asset does not appear to be a GeoParquet file."
    )
