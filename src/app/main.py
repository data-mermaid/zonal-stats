from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import ValidationError

from .api.endpoints import router
from .services.zonal_stats import ZonalStatsError, GeometryError, RasterError, STACError

app = FastAPI(
    title="Zonal Statistics API",
    description="API for calculating zonal statistics from raster data",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the router
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "Welcome to the Zonal Statistics API",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }


@app.exception_handler(ZonalStatsError)
async def zonal_stats_exception_handler(request: Request, exc: ZonalStatsError):
    """Handle custom ZonalStatsError exceptions."""
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
