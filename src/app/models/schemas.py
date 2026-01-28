from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
)


class StatType(str, Enum):
    # Default statistics
    MIN = "min"
    MAX = "max"
    MEAN = "mean"
    COUNT = "count"

    # Optional statistics
    SUM = "sum"
    STD = "std"
    MEDIAN = "median"
    MAJORITY = "majority"
    MINORITY = "minority"
    UNIQUE = "unique"
    RANGE = "range"
    NODATA = "nodata"

    # Special statistics (work for both raster and vector)
    AOI_AREA = "aoi_area"  # Area of the query AOI in square meters
    DATA_AREA = "data_area"  # Area of data within AOI (valid pixels/features)
    FREQ_HIST = "freq_hist"  # Raster only

    # Vector-specific statistics
    DENSITY = "density"  # Features per km² of AOI


# Stats filtering constants and functions
RASTER_ONLY_STATS = {
    StatType.NODATA,
    StatType.MAJORITY,
    StatType.MINORITY,
    StatType.FREQ_HIST,
}
VECTOR_ONLY_STATS = {StatType.DENSITY}


def filter_raster_stats(stats: list[StatType] | None) -> list[StatType]:
    """Filter stats to only those valid for raster data."""
    if stats is None:
        base = [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
    else:
        base = [s for s in stats if s not in VECTOR_ONLY_STATS]
    # Always include area stats
    if StatType.AOI_AREA not in base:
        base.append(StatType.AOI_AREA)
    if StatType.DATA_AREA not in base:
        base.append(StatType.DATA_AREA)
    return base


def filter_vector_stats(stats: list[StatType] | None) -> list[StatType]:
    """Filter stats to only those valid for vector data."""
    if stats is None:
        base = [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
    else:
        base = [s for s in stats if s not in RASTER_ONLY_STATS]
    # Always include area stats
    if StatType.AOI_AREA not in base:
        base.append(StatType.AOI_AREA)
    if StatType.DATA_AREA not in base:
        base.append(StatType.DATA_AREA)
    return base


class PointGeometry(BaseModel):
    type: str = "Point"
    coordinates: list[float] = Field(description="[longitude, latitude]")
    radius: float | None = Field(default=None, description="buffer radius in meters")

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v):
        if len(v) != 2:
            raise ValueError("Point coordinates must be [longitude, latitude]")
        if not -180 <= v[0] <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        if not -90 <= v[1] <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, v):
        if v is not None and v < 0:
            raise ValueError("Radius must be non-negative")
        return v


class PolygonGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: list[list[list[float]]] = Field(
        description="[[[x1, y1], [x2, y2], ...]]",
        min_length=1,
    )

    @field_validator("coordinates")
    @classmethod
    def validate_polygon(cls, v):
        if not v or not v[0] or len(v[0]) < 3:
            raise ValueError("Polygon must have at least 3 points")
        # Check if first and last points are the same (closed polygon)
        if v[0][0] != v[0][-1]:
            raise ValueError(
                "Polygon must be closed (first and last points must be the same)"
            )
        return v


# =============================================================================
# New focused request models for the refactored API
# =============================================================================


def _validate_url(v: str, protocols: tuple[str, ...]) -> str:
    """Common URL validation helper."""
    if not v.startswith(protocols):
        raise ValueError(f"URL must start with one of: {', '.join(protocols)}")
    return v


def _validate_stats_list(v: list[StatType] | None) -> list[StatType] | None:
    """Validate that stats list is not empty if provided."""
    if v is not None and len(v) == 0:
        raise ValueError("Statistics list cannot be empty")
    return v


class RasterStatsRequest(BaseModel):
    """Request for direct COG raster statistics."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    aoi: PointGeometry | PolygonGeometry = Field(
        ..., description="Area of interest (Point or Polygon geometry)"
    )
    stats: list[StatType] | None = Field(
        default=None, description="Statistics to calculate"
    )
    url: str = Field(..., description="URL to Cloud Optimized GeoTIFF")
    bands: list[int] = Field(
        default=[1], description="Band indices to process", min_length=1
    )
    approx_stats: bool = Field(
        default=False, description="Use overviews for faster approximate stats"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        return _validate_url(v, ("http://", "https://", "s3://", "file://"))

    @field_validator("stats")
    @classmethod
    def validate_stats(cls, v):
        return _validate_stats_list(v)


class RasterStacStatsRequest(BaseModel):
    """Request for STAC-based raster statistics."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    aoi: PointGeometry | PolygonGeometry = Field(
        ..., description="Area of interest (Point or Polygon geometry)"
    )
    stats: list[StatType] | None = Field(
        default=None, description="Statistics to calculate"
    )
    url: str = Field(..., description="URL to STAC Item JSON")
    asset: str | None = Field(
        default=None, description="Asset key (uses first asset if not specified)"
    )
    bands: list[int] = Field(
        default=[1], description="Band indices to process", min_length=1
    )
    approx_stats: bool = Field(
        default=False, description="Use overviews for faster approximate stats"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        return _validate_url(v, ("http://", "https://"))

    @field_validator("stats")
    @classmethod
    def validate_stats(cls, v):
        return _validate_stats_list(v)


class VectorStatsRequest(BaseModel):
    """Request for direct GeoParquet vector statistics."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    aoi: PointGeometry | PolygonGeometry = Field(
        ..., description="Area of interest (Point or Polygon geometry)"
    )
    stats: list[StatType] | None = Field(
        default=None, description="Statistics to calculate"
    )
    url: str = Field(..., description="URL to GeoParquet file")
    columns: list[str] = Field(
        ..., description="Numeric columns to calculate statistics for", min_length=1
    )
    geometry_column: str = Field(
        default="geometry", description="Name of geometry column"
    )
    approx_stats: bool = Field(
        default=False, description="Reserved for future optimization"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        return _validate_url(v, ("http://", "https://", "s3://", "file://"))

    @field_validator("stats")
    @classmethod
    def validate_stats(cls, v):
        return _validate_stats_list(v)


class VectorStacStatsRequest(BaseModel):
    """Request for STAC-based vector statistics."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    aoi: PointGeometry | PolygonGeometry = Field(
        ..., description="Area of interest (Point or Polygon geometry)"
    )
    stats: list[StatType] | None = Field(
        default=None, description="Statistics to calculate"
    )
    url: str = Field(..., description="URL to STAC Item JSON")
    asset: str | None = Field(default=None, description="Asset key for GeoParquet")
    columns: list[str] = Field(
        ..., description="Numeric columns to calculate statistics for", min_length=1
    )
    geometry_column: str = Field(
        default="geometry", description="Name of geometry column"
    )
    approx_stats: bool = Field(
        default=False, description="Reserved for future optimization"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        return _validate_url(v, ("http://", "https://"))

    @field_validator("stats")
    @classmethod
    def validate_stats(cls, v):
        return _validate_stats_list(v)


# =============================================================================
# Response models
# =============================================================================


class BandStats(BaseModel):
    model_config = ConfigDict(
        extra="allow"  # Allow extra fields to be added dynamically
    )


class ZonalStatsResponse(RootModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    root: dict[str, BandStats] = Field(description="Statistics for each band/column")
