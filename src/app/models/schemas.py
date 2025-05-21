from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, ValidationError, model_validator


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

    # Special statistics
    AREA = "area"
    FREQ_HIST = "freq_hist"


class PointGeometry(BaseModel):
    type: str = "Point"
    coordinates: list[float] = Field(description="[longitude, latitude]")
    buffer_size: float = Field(description="buffer size in meters")

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

    @field_validator("buffer_size")
    @classmethod
    def validate_buffer_size(cls, v):
        if v <= 0:
            raise ValueError("Buffer size must be greater than 0")
        return v


class PolygonGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: list[list[list[float]]] = Field(
        description="[[[x1, y1], [x2, y2], ...]]",
        min_items=1,
    )

    @field_validator("coordinates")
    @classmethod
    def validate_polygon(cls, v):
        if not v or not v[0] or len(v[0]) < 3:
            raise ValueError("Polygon must have at least 3 points")
        # Check if first and last points are the same (closed polygon)
        if v[0][0] != v[0][-1]:
            raise ValueError("Polygon must be closed (first and last points must be the same)")
        return v


class ImageConfig(BaseModel):
    url: str = Field(description="URL to the raster image")
    bands: list[int] = Field(
        default=[1],
        description="List of band indices to process",
        min_items=1,
    )
    approx_stats: bool = Field(
        default=False,
        description="Whether to use approximate statistics for large areas",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://", "s3://", "file://")):
            raise ValueError("URL must start with http://, https://, s3://, or file://")
        return v


class StacConfig(BaseModel):
    url: str = Field(description="URL to the STAC item")
    asset: str | None = Field(
        default=None,
        description="Name of the asset to use (if None, first asset will be used)",
    )
    bands: list[int] = Field(
        default=[1],
        description="List of band indices to process",
        min_items=1,
    )
    approx_stats: bool = Field(
        default=False,
        description="Whether to use approximate statistics for large areas",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("STAC URL must start with http:// or https://")
        return v


class ZonalStatsRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    aoi: PointGeometry | PolygonGeometry = Field(
        description="Area of interest (Point or Polygon geometry)"
    )
    stats: list[StatType] | None = Field(
        default=None,
        description="List of statistics to calculate",
    )
    image: ImageConfig | None = Field(
        default=None,
        description="Image configuration",
    )
    stac: StacConfig | None = Field(
        default=None,
        description="STAC configuration",
    )

    @model_validator(mode='after')
    def validate_sources(self):
        """Validate that exactly one source (image or stac) is provided."""
        if self.image is not None and self.stac is not None:
            raise ValueError("Cannot specify both image and stac sources")
        if self.image is None and self.stac is None:
            raise ValueError("Must specify either image or stac source")
        return self

    @field_validator("stats")
    @classmethod
    def set_default_stats(cls, v):
        if v is None:
            # Default to the basic statistics
            return [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
        if not v:
            raise ValueError("Statistics list cannot be empty")
        return v


class BandStats(BaseModel):
    model_config = ConfigDict(
        extra="allow"  # Allow extra fields to be added dynamically
    )


class ZonalStatsResponse(RootModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    root: dict[str, BandStats] = Field(description="Statistics for each band")
