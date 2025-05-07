from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from .api.endpoints import router

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


# Create handler for AWS Lambda
handler = Mangum(app)
