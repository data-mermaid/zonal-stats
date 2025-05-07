from fastapi import APIRouter, HTTPException

from ..models.schemas import ZonalStatsRequest, ZonalStatsResponse
from ..services.zonal_stats import ZonalStatsService

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
        # For now, just raise an error as STAC support is stubbed
        raise HTTPException(
            status_code=501, detail="STAC support is not yet implemented"
        )
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
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating zonal statistics: {str(e)}"
        ) from e
