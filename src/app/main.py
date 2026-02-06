from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import HTMLResponse, JSONResponse
from mangum import Mangum
from pydantic import ValidationError

from .api.endpoints import router
from .services.zonal_stats import STACError, UnsupportedMediaTypeError, ZonalStatsError

app = FastAPI(
    title="Zonal Statistics API",
    description="""
Calculate zonal statistics from raster and vector data sources.

## Endpoints

- **Raster**: `/api/v1/zonal-stats/raster` - Stats from COG
- **Raster STAC**: `/api/v1/zonal-stats/raster/stac` - Stats from STAC raster
- **Vector**: `/api/v1/zonal-stats/vector` - Stats from GeoParquet
- **Vector STAC**: `/api/v1/zonal-stats/vector/stac` - Stats from STAC vector
""",
    version="0.2.0",
    docs_url="/docs",
    redoc_url=None,  # Disable default ReDoc to use custom version
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include the router with zonal-stats prefix
app.include_router(router, prefix="/api/v1/zonal-stats")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to the Zonal Statistics API",
        "version": "0.2.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "endpoints": {
            "raster": "/api/v1/zonal-stats/raster",
            "raster_stac": "/api/v1/zonal-stats/raster/stac",
            "vector": "/api/v1/zonal-stats/vector",
            "vector_stac": "/api/v1/zonal-stats/vector/stac",
        },
    }


@app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
async def redoc_html():
    """Custom ReDoc endpoint with stable CDN URL."""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    )


@app.exception_handler(ZonalStatsError)
async def zonal_stats_exception_handler(request: Request, exc: ZonalStatsError):
    """Handle custom ZonalStatsError exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(STACError)
async def stac_exception_handler(request: Request, exc: STACError):
    """Handle STAC-related errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(UnsupportedMediaTypeError)
async def unsupported_media_type_handler(
    request: Request, exc: UnsupportedMediaTypeError
):
    """Handle unsupported media type errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


# Create handler for AWS Lambda
handler = Mangum(app)
