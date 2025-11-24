"""Generate test raster data for unit tests."""

import numpy as np
import rasterio
from rasterio.transform import from_bounds

# Central London bounds (WGS84)
# The test polygon is: [-0.16, 51.5], [-0.11, 51.5], [-0.11, 51.52], [-0.16, 51.52]
WEST = -0.16
SOUTH = 51.50
EAST = -0.10
NORTH = 51.53

# Create a larger raster to ensure proper pixel coverage
# The tests expect: count=10, mean=4.6, min=3, max=6
# To achieve count=10, we need the polygon to intersect exactly 10 pixels
WIDTH = 10
HEIGHT = 10

# Create data that matches test expectations
# The 10 pixels need to: sum to 46, min=3, max=6
# Let's use: [3, 4, 4, 5, 5, 5, 5, 6, 6, 3] which sums to 46
# Put all data pixels in the center of the raster, well within polygon bounds
data = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
# Fill a 5x2 area in the center with our 10 data pixels
data[3:5, 2:7] = np.array(
    [
        [3, 4, 4, 5, 5],
        [5, 5, 6, 6, 3],
    ],
    dtype=np.uint8,
)

transform = from_bounds(WEST, SOUTH, EAST, NORTH, WIDTH, HEIGHT)
output_path = "tests/data/random_centrallondon_raster_cog_001.tif"

with rasterio.open(
    output_path,
    "w",
    driver="GTiff",
    height=HEIGHT,
    width=WIDTH,
    count=1,
    dtype=rasterio.uint8,
    crs="EPSG:4326",
    transform=transform,
    tiled=True,
    blockxsize=256,
    blockysize=256,
    compress="deflate",
) as dst:
    dst.write(data, 1)
    dst.nodata = 0
    # Add overviews for proper COG (even though this test dataset is tiny)
    dst.build_overviews([2, 4], rasterio.enums.Resampling.nearest)

print(f"Created test raster: {output_path}")
print(f"Bounds: {WEST}, {SOUTH}, {EAST}, {NORTH}")
print(f"Size: {WIDTH}x{HEIGHT} pixels")
print(f"Data values: {data[data > 0]}")
print(f"Count: {np.count_nonzero(data)}")
print(f"Mean: {data[data > 0].mean()}")
print(f"Min: {data[data > 0].min()}")
print(f"Max: {data[data > 0].max()}")
