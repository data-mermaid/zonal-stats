import logging

from fastapi import APIRouter, HTTPException

from ..models.schemas import ZonalStatsRequest, ZonalStatsResponse
from ..services.zonal_stats import ZonalStatsService, get_stac_asset_url, ZonalStatsError, RasterError, GeometryError, STACError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()


@router.post("/zonal-stats", response_model=ZonalStatsResponse)
async def calculate_zonal_stats(request: ZonalStatsRequest):
    """
    Calculate zonal statistics for a given area of interest and raster data.
    """
    # Validate that exactly one of image or stac is provided
    if bool(request.image) == bool(request.stac):
        raise HTTPException(
            status_code=400,
            detail="Exactly one of image or stac configuration must be provided",
        )

    # Validate geometry
    if not ZonalStatsService.validate_geometry(request.aoi):
        raise HTTPException(status_code=400, detail="Invalid geometry provided")

    # Determine which source to use
    if request.image:
        url = request.image.url
        bands = request.image.bands
        approx_stats = request.image.approx_stats
    elif request.stac:
        # Log that STAC input is being processed
        logger.info(
            f"Processing STAC input with URL: {request.stac.url} and asset: {request.stac.asset}"
        )
        url = get_stac_asset_url(request.stac.url, request.stac.asset)
        bands = request.stac.bands
        approx_stats = request.stac.approx_stats
    else:
        raise HTTPException(
            status_code=400,
            detail="Either image or stac configuration must be provided",
        )

    try:
        # Create service and calculate stats
        service = ZonalStatsService(url, bands, approx_stats)
        results = service.calculate_stats(request.aoi, request.stats)
        return results  # Return directly without wrapping in {"__root__": ...}
    except (RasterError, GeometryError, STACError) as e:
        # These are our custom exceptions that already have the correct status code
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )
    except Exception as e:
        # For any other unexpected errors
        logger.error(f"Unexpected error calculating zonal statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while calculating zonal statistics",
        )
