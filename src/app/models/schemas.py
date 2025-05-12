from enum import Enum
from typing import Any

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

    aoi: dict[str, Any]  # GeoJSON geometry
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
