from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, RootModel, validator


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
    coordinates: list[float]  # [longitude, latitude]
    buffer_size: float  # buffer size in meters

    @validator("coordinates")
    def validate_coordinates(cls, v):
        if len(v) != 2:
            raise ValueError("Point coordinates must be [longitude, latitude]")
        if not -180 <= v[0] <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        if not -90 <= v[1] <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @validator("buffer_size")
    def validate_buffer_size(cls, v):
        if v <= 0:
            raise ValueError("Buffer size must be greater than 0")
        return v


class PolygonGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: list[list[list[float]]]  # [[[x1, y1], [x2, y2], ...]]


class ImageConfig(BaseModel):
    url: str
    bands: list[int] = Field(default=[1])
    approx_stats: bool = Field(default=False)


class StacConfig(BaseModel):
    url: str
    asset: str | None = None
    bands: list[int] = Field(default=[1])
    approx_stats: bool = Field(default=False)


class ZonalStatsRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    aoi: PointGeometry | PolygonGeometry  # Can be either Point or Polygon
    stats: list[StatType] | None = None
    image: ImageConfig | None = None
    stac: StacConfig | None = None

    @validator("stats")
    def set_default_stats(cls, v):
        if v is None:
            # Default to the basic statistics
            return [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
        return v

    @validator("image", "stac")
    def validate_source(cls, v, values):
        if (
            "image" in values
            and "stac" in values
            and values["image"] is not None
            and values["stac"] is not None
        ):
            raise ValueError("Cannot specify both image and stac sources")
        return v


class BandStats(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )  # Allow extra fields to be added dynamically


class ZonalStatsResponse(RootModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    root: dict[str, BandStats]
