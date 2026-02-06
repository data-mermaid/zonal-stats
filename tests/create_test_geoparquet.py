# ruff: noqa: E501
"""Script to create a test GeoParquet file for vector stats testing."""

import duckdb


def create_test_geoparquet():
    """Create a test GeoParquet file with known values for testing."""
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")

    # Create test data with known values in central London area
    # These polygons are within the test raster extent
    conn.execute("""
        CREATE TABLE test_data AS
        SELECT
            id,
            population,
            median_income,
            ST_GeomFromText(wkt) as geometry
        FROM (
            VALUES
            -- Polygon 1: Small square in central London
            (1, 1000, 50000.0,
             'POLYGON((-0.15 51.505, -0.14 51.505, -0.14 51.515, -0.15 51.515, -0.15 51.505))'),
            -- Polygon 2: Adjacent to polygon 1
            (2, 2000, 60000.0,
             'POLYGON((-0.14 51.505, -0.13 51.505, -0.13 51.515, -0.14 51.515, -0.14 51.505))'),
            -- Polygon 3: Partially overlapping with test AOI
            (3, 1500, 55000.0,
             'POLYGON((-0.13 51.505, -0.12 51.505, -0.12 51.515, -0.13 51.515, -0.13 51.505))'),
            -- Polygon 4: Outside the typical test AOI
            (4, 3000, 70000.0,
             'POLYGON((-0.20 51.48, -0.19 51.48, -0.19 51.49, -0.20 51.49, -0.20 51.48))')
        ) AS t(id, population, median_income, wkt)
    """)

    # Export to GeoParquet
    conn.execute("""
        COPY test_data TO 'tests/data/test_vector.parquet'
        (FORMAT PARQUET)
    """)

    print("Created tests/data/test_vector.parquet")

    # Verify the file
    result = conn.execute("""
        SELECT COUNT(*), MIN(population), MAX(population)
        FROM read_parquet('tests/data/test_vector.parquet')
    """).fetchone()
    print(f"Verification: {result[0]} rows, population range: {result[1]}-{result[2]}")

    conn.close()


if __name__ == "__main__":
    create_test_geoparquet()
