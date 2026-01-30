"""API endpoints for zonal statistics calculations."""

import logging

from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    PointGeometry,
    PolygonGeometry,
    RasterStacStatsRequest,
    RasterStatsRequest,
    VectorStacStatsRequest,
    VectorStatsRequest,
    ZonalStatsResponse,
    filter_raster_stats,
    filter_vector_stats,
)
from ..services.stac import get_asset_url as stac_get_asset_url
from ..services.stac import validate_vector_asset
from ..services.zonal_stats import (
    ZonalStatsError,
    ZonalStatsService,
)
from ..services.zonal_vector import ZonalVectorService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Main router for zonal-stats
router = APIRouter(tags=["Zonal Statistics"])

# Sub-routers for organization
raster_router = APIRouter(prefix="/raster", tags=["Raster"])
vector_router = APIRouter(prefix="/vector", tags=["Vector"])


def _determine_intersection_mode(aoi: PointGeometry | PolygonGeometry) -> str:
    """Determine intersection mode from geometry type.

    - Point with no radius or radius=0: touch (raw point, unweighted)
    - Point with radius > 0: intersect (buffered to polygon, area-weighted)
    - Polygon: intersect (area-weighted)
    """
    if isinstance(aoi, PointGeometry):
        if not aoi.radius or aoi.radius <= 0:
            return "touch"
        return "intersect"
    return "intersect"


def _handle_service_error(e: Exception):
    """Convert service exceptions to HTTP exceptions."""
    if isinstance(e, ZonalStatsError):
        raise HTTPException(status_code=e.status_code, detail=e.message) from None
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    raise HTTPException(
        status_code=500,
        detail="An unexpected error occurred while calculating zonal statistics",
    ) from e


# =============================================================================
# Raster Endpoints
# =============================================================================


@raster_router.post(
    "",
    response_model=ZonalStatsResponse,
    summary="Calculate zonal statistics from COG",
    description="Calculate statistics for raster data from a Cloud Optimized GeoTIFF.",
)
async def raster_stats(request: RasterStatsRequest) -> ZonalStatsResponse:
    """Calculate zonal statistics from a direct COG URL."""
    if not ZonalStatsService.validate_geometry(request.aoi):
        raise HTTPException(status_code=400, detail="Invalid geometry provided")

    try:
        stats = filter_raster_stats(request.stats)

        service = ZonalStatsService(
            url=request.url,
            bands=request.bands,
            approx_stats=request.approx_stats,
        )
        return service.calculate_stats(request.aoi, stats)

    except Exception as e:
        _handle_service_error(e)


@raster_router.post(
    "/stac",
    response_model=ZonalStatsResponse,
    summary="Calculate zonal statistics from STAC raster asset",
    description="Fetch a STAC item and calculate statistics from its raster asset.",
)
async def raster_stac_stats(request: RasterStacStatsRequest) -> ZonalStatsResponse:
    """Calculate zonal statistics from a STAC item's raster asset."""
    if not ZonalStatsService.validate_geometry(request.aoi):
        raise HTTPException(status_code=400, detail="Invalid geometry provided")

    try:
        logger.info(f"Processing STAC raster: {request.url}, asset: {request.asset}")

        # Fetch STAC item and get asset URL
        cog_url = stac_get_asset_url(request.url, request.asset)
        stats = filter_raster_stats(request.stats)

        service = ZonalStatsService(
            url=cog_url,
            bands=request.bands,
            approx_stats=request.approx_stats,
        )
        return service.calculate_stats(request.aoi, stats)

    except Exception as e:
        _handle_service_error(e)


# =============================================================================
# Vector Endpoints
# =============================================================================


@vector_router.post(
    "",
    response_model=ZonalStatsResponse,
    summary="Calculate zonal statistics from GeoParquet",
    description="Calculate statistics for vector data from a GeoParquet file.",
)
async def vector_stats(request: VectorStatsRequest) -> ZonalStatsResponse:
    """Calculate zonal statistics from a direct GeoParquet URL."""
    if not ZonalVectorService.validate_geometry(request.aoi):
        raise HTTPException(status_code=400, detail="Invalid geometry provided")

    try:
        intersection_mode = _determine_intersection_mode(request.aoi)
        logger.info(
            f"Processing vector: {request.url}, columns: {request.columns}, "
            f"mode: {intersection_mode}, weighting: {request.weighting_method.value}"
        )

        stats = filter_vector_stats(request.stats)

        service = ZonalVectorService(
            url=request.url,
            columns=request.columns,
            geometry_column=request.geometry_column,
            intersection_mode=intersection_mode,
            weighting_method=request.weighting_method,
            approx_stats=request.approx_stats,
        )
        return service.calculate_stats(request.aoi, stats)

    except Exception as e:
        _handle_service_error(e)


@vector_router.post(
    "/stac",
    response_model=ZonalStatsResponse,
    summary="Calculate zonal statistics from STAC vector asset",
    description="Fetch a STAC item and calculate statistics from its GeoParquet asset.",
)
async def vector_stac_stats(request: VectorStacStatsRequest) -> ZonalStatsResponse:
    """Calculate zonal statistics from a STAC item's vector asset."""
    if not ZonalVectorService.validate_geometry(request.aoi):
        raise HTTPException(status_code=400, detail="Invalid geometry provided")

    try:
        intersection_mode = _determine_intersection_mode(request.aoi)
        logger.info(
            f"Processing STAC vector: {request.url}, asset: {request.asset}, "
            f"weighting: {request.weighting_method.value}"
        )

        # Fetch STAC item and validate it's a GeoParquet asset
        parquet_url = validate_vector_asset(request.url, request.asset)
        stats = filter_vector_stats(request.stats)

        service = ZonalVectorService(
            url=parquet_url,
            columns=request.columns,
            geometry_column=request.geometry_column,
            intersection_mode=intersection_mode,
            weighting_method=request.weighting_method,
            approx_stats=request.approx_stats,
        )
        return service.calculate_stats(request.aoi, stats)

    except Exception as e:
        _handle_service_error(e)


# Include sub-routers
router.include_router(raster_router)
router.include_router(vector_router)
