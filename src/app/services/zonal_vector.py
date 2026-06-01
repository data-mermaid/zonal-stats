"""Service for calculating zonal statistics from vector data (GeoParquet)."""

import json
import logging
import os

import duckdb
from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform

from ..models.schemas import (
    BandStats,
    PointGeometry,
    PolygonGeometry,
    StatType,
    WeightingMethod,
)
from .zonal_stats import UnsupportedMediaTypeError, VectorError, create_buffer_polygon

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ZonalVectorService:
    """Service for calculating zonal statistics from vector data."""

    # Statistics that are specific to vector data
    VECTOR_SPECIFIC_STATS = {StatType.DENSITY}

    # Statistics that don't apply to vector data
    RASTER_ONLY_STATS = {
        StatType.NODATA,
        StatType.MAJORITY,
        StatType.MINORITY,
        StatType.FREQ_HIST,
    }

    # Common geometry column names to try as fallbacks
    COMMON_GEOMETRY_COLUMNS = ["geometry", "geom", "the_geom", "wkb_geometry", "shape"]

    def __init__(
        self,
        url: str,
        columns: list[str],
        geometry_column: str = "geometry",
        intersection_mode: str = "intersect",
        weighting_method: WeightingMethod = WeightingMethod.AREA,
        approx_stats: bool = False,
    ):
        self._validate_file_format(url)
        self.url = url
        self.columns = columns
        self._geometry_column_hint = geometry_column  # User-provided hint
        self._geometry_column = None  # Will be resolved lazily
        self.intersection_mode = intersection_mode
        self.weighting_method = weighting_method
        self.approx_stats = approx_stats  # Reserved for future optimization
        self._conn = None

    @property
    def geometry_column(self) -> str:
        """Get the geometry column name, auto-detecting if necessary."""
        if self._geometry_column is None:
            self._geometry_column = self._resolve_geometry_column()
        return self._geometry_column

    def _resolve_geometry_column(self) -> str:
        """Resolve the geometry column name from metadata or fallbacks."""
        conn = self._get_connection()

        # First, get available columns
        try:
            result = conn.execute(
                """
                SELECT column_name
                FROM (DESCRIBE SELECT * FROM read_parquet($1))
            """,
                [self.url],
            ).fetchall()
            available_columns = {row[0] for row in result}
        except Exception as e:
            logger.warning(f"Could not get column list: {e}")
            return self._geometry_column_hint

        # If the hint exists in the file, use it
        if self._geometry_column_hint in available_columns:
            logger.info(f"Using provided geometry column: {self._geometry_column_hint}")
            return self._geometry_column_hint

        # Try to read from GeoParquet metadata
        try:
            result = conn.execute(
                """
                SELECT value
                FROM parquet_kv_metadata($1)
                WHERE key = 'geo'
            """,
                [self.url],
            ).fetchone()

            if result and result[0]:
                geo_metadata = json.loads(result[0])
                # GeoParquet spec: primary_column indicates the primary geometry
                primary_col = geo_metadata.get("primary_column")
                if primary_col and primary_col in available_columns:
                    logger.info(
                        "Auto-detected geometry column from GeoParquet metadata: "
                        f"{primary_col}"
                    )
                    return primary_col

                # Also check columns dict for any geometry column
                columns_meta = geo_metadata.get("columns", {})
                for col_name in columns_meta:
                    if col_name in available_columns:
                        logger.info(
                            f"Found geometry column in GeoParquet metadata: {col_name}"
                        )
                        return col_name
        except Exception as e:
            logger.warning(f"Could not read GeoParquet metadata: {e}")

        # Try common geometry column names as fallbacks
        for fallback in self.COMMON_GEOMETRY_COLUMNS:
            if fallback in available_columns:
                logger.info(f"Using fallback geometry column: {fallback}")
                return fallback

        # Last resort: use the hint and let validation fail with helpful error
        logger.warning(
            "Could not auto-detect geometry column, using hint: "
            f"{self._geometry_column_hint}"
        )
        return self._geometry_column_hint

    @staticmethod
    def _quote_identifier(name: str) -> str:
        """Quote a SQL identifier to prevent injection.

        Uses DuckDB's double-quote identifier syntax and escapes any embedded
        double quotes by doubling them.
        """
        # Escape embedded double quotes by doubling them
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    @staticmethod
    def _validate_file_format(url: str) -> None:
        """Validate that the URL points to a GeoParquet file.

        Only GeoParquet is supported because it stores CRS metadata that DuckDB
        can read. Other vector formats would require explicit SRID handling.

        Raises:
            UnsupportedMediaTypeError: If the file is not a GeoParquet file.
        """
        # Extract path without query params for extension check
        url_path = url.split("?")[0].lower()
        if not url_path.endswith((".parquet", ".geoparquet")):
            raise UnsupportedMediaTypeError(
                "Unsupported vector format. Only GeoParquet files "
                "(.parquet, .geoparquet) are supported."
            )

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get or create a DuckDB connection with required extensions.

        Extensions should be pre-installed at build/deploy time (e.g., in Docker
        or Lambda layer). This method attempts to LOAD them first (fast, no network).
        Falls back to INSTALL for local development if LOAD fails.
        """
        if self._conn is None:
            self._conn = duckdb.connect(":memory:")
            self._configure_writable_dirs()
            self._load_extension("spatial")
            self._load_extension("httpfs")
            # Configure for HTTP/S3 access
            if self.url.startswith("s3://"):
                # For S3 support - use unsigned requests for public buckets
                self._conn.execute("SET s3_url_style='path';")
        return self._conn

    def _configure_writable_dirs(self) -> None:
        """Point DuckDB at a writable home and the pre-installed extensions.

        On AWS Lambda ``$HOME`` is unset (or non-writable), so DuckDB raises
        "Can't find the home directory at ''" the first time it needs to
        resolve extensions, secrets, or the httpfs cache. ``/tmp`` is the only
        writable location in the Lambda runtime, so use it when no usable home
        is available.

        ``extension_directory`` is pointed at the location where extensions are
        baked into the image (``DUCKDB_EXTENSION_DIRECTORY``) so ``LOAD`` reads
        the build-time copy instead of downloading at runtime — a runtime
        download pulls a binary that may be incompatible with the image's
        glibc. Falls back gracefully for local development.
        """
        home = os.environ.get("HOME")
        # Use /tmp when HOME is missing/empty or not writable (e.g. Lambda).
        if not home or not os.access(home, os.W_OK):
            home = "/tmp"

        # Prefer the extension directory baked into the image; otherwise let
        # DuckDB use its default under the (writable) home directory.
        ext_dir = os.environ.get("DUCKDB_EXTENSION_DIRECTORY")

        try:
            self._conn.execute(f"SET home_directory='{home}';")
            if ext_dir:
                self._conn.execute(f"SET extension_directory='{ext_dir}';")
        except duckdb.Error as e:
            logger.warning(f"Could not configure DuckDB directories: {e}")

    def _load_extension(self, extension: str) -> None:
        """Load a DuckDB extension, installing if necessary for local development."""
        try:
            self._conn.execute(f"LOAD {extension};")
        except duckdb.IOException:
            # Extension not pre-installed - install it (requires network)
            # This path is for local development; production should have pre-installed
            logger.info(f"Extension {extension} not found, installing...")
            self._conn.execute(f"INSTALL {extension}; LOAD {extension};")

    def _close_connection(self):
        """Close the DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _get_vector_crs(self) -> CRS:
        """Read CRS from GeoParquet metadata."""
        try:
            conn = self._get_connection()
            # Read CRS from GeoParquet file metadata (stored under 'geo' key)
            result = conn.execute(
                """
                SELECT value
                FROM parquet_kv_metadata($1)
                WHERE key = 'geo'
            """,
                [self.url],
            ).fetchone()

            if result and result[0]:
                geo_metadata = json.loads(result[0])
                # GeoParquet stores CRS per column in columns.<column_name>.crs
                columns = geo_metadata.get("columns", {})
                col_meta = columns.get(self.geometry_column, {})
                crs_info = col_meta.get("crs")

                if crs_info:
                    # CRS can be a PROJJSON object or an identifier
                    if isinstance(crs_info, dict):
                        return CRS.from_json_dict(crs_info)
                    elif isinstance(crs_info, str):
                        return CRS.from_string(crs_info)

            # Default to WGS84 if no CRS found
            logger.info("No CRS found in vector data, defaulting to WGS84")
            return CRS.from_epsg(4326)
        except Exception as e:
            logger.warning(f"Could not read CRS from vector data: {e}")
            return CRS.from_epsg(4326)

    def _validate_columns(self) -> None:
        """Validate that requested columns exist and are numeric.

        Performs case-insensitive matching and updates self.columns with
        the actual column names from the file. If requested columns don't
        exist, falls back to auto-detecting numeric columns.
        """
        try:
            conn = self._get_connection()

            # Get column info from the parquet file
            result = conn.execute(
                """
                SELECT column_name, column_type
                FROM (DESCRIBE SELECT * FROM read_parquet($1))
            """,
                [self.url],
            ).fetchall()

            available_columns = {row[0]: row[1] for row in result}
            # Create case-insensitive lookup: lowercase -> actual name
            columns_lower = {name.lower(): name for name in available_columns}

            # Check geometry column exists (case-insensitive)
            # Use the user-provided hint directly to validate before any fallback
            geom_col_lower = self._geometry_column_hint.lower()
            if geom_col_lower not in columns_lower:
                raise VectorError(
                    f"Geometry column '{self._geometry_column_hint}' not found in "
                    f"vector data. Available columns: {list(available_columns.keys())}"
                )
            # Update to actual case from file
            self._geometry_column = columns_lower[geom_col_lower]

            # Numeric types for validation
            numeric_types = {
                "TINYINT",
                "SMALLINT",
                "INTEGER",
                "BIGINT",
                "HUGEINT",
                "FLOAT",
                "DOUBLE",
                "DECIMAL",
                "REAL",
                "NUMERIC",
            }

            def is_numeric_type(col_type: str) -> bool:
                base_type = col_type.upper().split("(")[0]
                return base_type in numeric_types

            # Try to resolve requested columns (case-insensitive)
            resolved_columns = []
            missing_columns = []
            for col in self.columns:
                col_lower = col.lower()
                if col_lower not in columns_lower:
                    missing_columns.append(col)
                    continue

                # Get actual column name from file
                actual_col = columns_lower[col_lower]
                col_type = available_columns[actual_col]

                if is_numeric_type(col_type):
                    resolved_columns.append(actual_col)
                else:
                    logger.warning(
                        f"Column '{col}' is not numeric (type: {col_type}), skipping"
                    )

            # Raise error if any requested columns were not found
            if missing_columns:
                raise VectorError(
                    f"Column(s) not found in vector data: {missing_columns}. "
                    f"Available columns: {list(available_columns.keys())}"
                )

            # Raise error if no valid numeric columns remain
            if not resolved_columns:
                raise VectorError(
                    f"No numeric columns found among requested columns. "
                    f"Available columns: {list(available_columns.keys())}"
                )

            # Update columns to use actual names from file
            self.columns = resolved_columns
            logger.info(f"Validated columns: {self.columns}")
        except VectorError:
            raise
        except Exception as e:
            raise VectorError(f"Error validating columns: {e}") from e

    def _prepare_geometry(
        self, geometry: PointGeometry | PolygonGeometry
    ) -> tuple[dict, shape]:
        """Convert geometry to GeoJSON dict and Shapely shape."""
        try:
            if isinstance(geometry, PointGeometry):
                if geometry.radius and geometry.radius > 0:
                    geometry_dict = create_buffer_polygon(geometry)
                else:
                    # Raw point — no buffering
                    geometry_dict = {
                        "type": "Point",
                        "coordinates": geometry.coordinates,
                    }
            else:
                geometry_dict = geometry.model_dump()

            shapely_geom = shape(geometry_dict)
            if not shapely_geom.is_valid:
                raise VectorError(
                    "Invalid geometry: self-intersection or other topological error"
                )

            logger.info(f"Processing geometry: {shapely_geom.bounds}")
            return geometry_dict, shapely_geom
        except VectorError:
            raise
        except Exception as e:
            raise VectorError(f"Error preparing geometry: {e}") from e

    def _transform_aoi_to_vector_crs(
        self, aoi_geom: shape, vector_crs: CRS
    ) -> tuple[shape, str]:
        """Transform AOI from WGS84 to vector dataset CRS.

        Returns the transformed geometry and its WKT representation.
        """
        try:
            source_crs = CRS.from_epsg(4326)

            if vector_crs == source_crs:
                return aoi_geom, aoi_geom.wkt

            transformer = Transformer.from_crs(source_crs, vector_crs, always_xy=True)
            transformed = transform(transformer.transform, aoi_geom)
            logger.info(f"Transformed AOI from WGS84 to {vector_crs}")
            return transformed, transformed.wkt
        except Exception as e:
            raise VectorError(f"Error transforming AOI to vector CRS: {e}") from e

    def _calculate_aoi_area_m2(self, aoi_geom: shape) -> float:
        """Calculate AOI area in square meters using equal-area projection."""
        try:
            # Use Albers Equal Area projection centered on the geometry
            center = aoi_geom.centroid
            proj_crs = CRS.from_proj4(
                f"+proj=aea +lat_1={center.y - 1} +lat_2={center.y + 1} "
                f"+lat_0={center.y} +lon_0={center.x} +x_0=0 +y_0=0 "
                f"+ellps=WGS84 +units=m +no_defs"
            )

            transformer = Transformer.from_crs(
                CRS.from_epsg(4326), proj_crs, always_xy=True
            )
            transformed_geom = transform(transformer.transform, aoi_geom)
            return transformed_geom.area
        except Exception as e:
            raise VectorError(f"Error calculating AOI area: {e}") from e

    def _convert_area_to_m2(self, area: float, crs: CRS, center_lat: float) -> float:
        """Convert area from CRS units to square meters.

        For geographic CRS (lat/lon), converts from square degrees to square meters.
        For projected CRS in meters, returns as-is.
        """
        import math

        if crs.is_geographic:
            # Convert from square degrees to square meters
            # 1 degree latitude ≈ 110,540 meters
            # 1 degree longitude ≈ 111,320 * cos(latitude) meters
            meters_per_degree_lat = 110540
            meters_per_degree_lon = 111320 * math.cos(math.radians(center_lat))
            conversion_factor = meters_per_degree_lat * meters_per_degree_lon
            return area * conversion_factor
        elif crs.is_projected:
            # Check if units are meters
            unit = crs.axis_info[0].unit_name.lower() if crs.axis_info else "metre"
            if unit in ["metre", "meter", "m"]:
                return area
            else:
                # For other units, log a warning and return as-is
                logger.warning(
                    f"Projected CRS uses non-meter units ({unit}), "
                    f"data_area may not be in square meters"
                )
                return area
        return area

    def _build_intersection_select_clause(
        self, stats: list[StatType]
    ) -> tuple[str, list[str]]:
        """Build SELECT clause with only requested aggregates for intersection mode.

        Returns tuple of (select_clause, column_names) where column_names
        indicates which fields are present in the result row.
        """
        # Always need count for COUNT and DENSITY stats
        select_parts = ["COUNT(*) AS count"]
        result_fields = ["count"]

        # MEAN needs both total_weight and weighted_sum
        # SUM only needs weighted_sum
        needs_weighted_sum = StatType.MEAN in stats or StatType.SUM in stats
        needs_total_weight = StatType.MEAN in stats

        if needs_total_weight:
            select_parts.append("SUM(weight) AS total_weight")
            result_fields.append("total_weight")

        if needs_weighted_sum:
            select_parts.append("SUM(value * weight) AS weighted_sum")
            result_fields.append("weighted_sum")

        if StatType.MIN in stats:
            select_parts.append("MIN(value) AS min_val")
            result_fields.append("min_val")

        if StatType.MAX in stats:
            select_parts.append("MAX(value) AS max_val")
            result_fields.append("max_val")

        # DATA_AREA needs total intersection area
        if StatType.DATA_AREA in stats:
            select_parts.append("SUM(intersection_area) AS total_intersection_area")
            result_fields.append("total_intersection_area")

        return ", ".join(select_parts), result_fields

    def _calculate_intersection_stats(
        self,
        wkt: str,
        aoi_area_m2: float,
        stats: list[StatType],
        vector_crs: CRS,
        center_lat: float,
    ) -> dict[str, dict]:
        """Calculate weighted statistics using intersection mode."""
        conn = self._get_connection()
        results = {}

        # Determine weight expression based on weighting method
        if self.weighting_method == WeightingMethod.AREA:
            # Standard areal interpolation: weight by intersection area
            weight_expr = "intersection_area"
        else:
            # Ratio method: weight by proportion of feature inside AOI
            weight_expr = "intersection_area / NULLIF(feature_area, 0)"

        # Quote geometry column identifier
        geom_col = self._quote_identifier(self.geometry_column)

        # Build SELECT clause with only requested aggregates
        select_clause, result_fields = self._build_intersection_select_clause(stats)

        for column in self.columns:
            # Quote column identifier to prevent SQL injection
            col = self._quote_identifier(column)

            # Build the query for weighted statistics
            # Use parameter binding for url ($1) and wkt ($2)
            query = f"""
            WITH aoi AS (
                SELECT ST_GeomFromText($2) AS geom
            ),
            intersected AS (
                SELECT
                    t.{col} as value,
                    ST_Area(
                        ST_Intersection(t.{geom_col}, aoi.geom)
                    ) AS intersection_area,
                    ST_Area(t.{geom_col}) AS feature_area
                FROM read_parquet($1) t, aoi
                WHERE ST_Intersects(t.{geom_col}, aoi.geom)
                  AND t.{col} IS NOT NULL
            ),
            weighted AS (
                SELECT
                    value,
                    intersection_area,
                    feature_area,
                    {weight_expr} AS weight
                FROM intersected
                WHERE intersection_area > 0
            )
            SELECT {select_clause}
            FROM weighted
            """

            try:
                result = conn.execute(query, [self.url, wkt]).fetchone()

                # Map result tuple to dict based on which fields were requested
                result_dict = dict(zip(result_fields, result, strict=False))
                count = result_dict.get("count", 0)

                # Handle empty results
                if count == 0 or count is None:
                    results[column] = self._empty_stats(stats, aoi_area_m2)
                    continue

                # Build stats dict with only computed values
                stats_dict = {"count": int(count)}

                # Calculate weighted mean if both components are available
                if "weighted_sum" in result_dict and "total_weight" in result_dict:
                    total_weight = result_dict["total_weight"]
                    weighted_sum = result_dict["weighted_sum"]
                    if total_weight and total_weight > 0:
                        stats_dict["mean"] = float(weighted_sum / total_weight)
                    else:
                        stats_dict["mean"] = None
                    # SUM is the weighted_sum itself
                    if StatType.SUM in stats:
                        stats_dict["sum"] = (
                            float(weighted_sum) if weighted_sum is not None else None
                        )
                elif "weighted_sum" in result_dict and StatType.SUM in stats:
                    # Only SUM requested, no MEAN
                    weighted_sum = result_dict["weighted_sum"]
                    stats_dict["sum"] = (
                        float(weighted_sum) if weighted_sum is not None else None
                    )

                if "min_val" in result_dict:
                    stats_dict["min"] = (
                        float(result_dict["min_val"])
                        if result_dict["min_val"] is not None
                        else None
                    )

                if "max_val" in result_dict:
                    stats_dict["max"] = (
                        float(result_dict["max_val"])
                        if result_dict["max_val"] is not None
                        else None
                    )

                # Calculate density (features per km²)
                if StatType.DENSITY in stats:
                    density = (
                        count / (aoi_area_m2 / 1_000_000) if aoi_area_m2 > 0 else 0
                    )
                    stats_dict["density"] = float(density)

                # AOI area (computed in Python, not SQL)
                if StatType.AOI_AREA in stats:
                    stats_dict["aoi_area"] = float(aoi_area_m2)

                # Convert data_area to square meters
                if "total_intersection_area" in result_dict:
                    total_area = result_dict["total_intersection_area"] or 0
                    data_area_m2 = self._convert_area_to_m2(
                        total_area, vector_crs, center_lat
                    )
                    stats_dict["data_area"] = float(data_area_m2)

                # Calculate additional stats if requested (std, range)
                if StatType.STD in stats or StatType.RANGE in stats:
                    extra_stats = self._calculate_extra_stats(
                        column, wkt, weighted=True
                    )
                    stats_dict.update(extra_stats)

                if StatType.MEDIAN in stats:
                    median = self._calculate_median(column, wkt)
                    stats_dict["median"] = median

                if StatType.UNIQUE in stats:
                    unique = self._calculate_unique(column, wkt)
                    stats_dict["unique"] = unique

                results[column] = stats_dict

            except Exception as e:
                logger.error(f"Error calculating stats for column {column}: {e}")
                raise VectorError(
                    f"Error calculating statistics for column '{column}': {e}"
                ) from e

        return results

    def _build_touch_select_clause(
        self, col: str, geom_col: str, stats: list[StatType]
    ) -> tuple[str, list[str]]:
        """Build SELECT clause with only requested aggregates for touch mode.

        Returns tuple of (select_clause, column_names) where column_names
        indicates which fields are present in the result row.
        """
        # Always need count for COUNT and DENSITY stats
        select_parts = ["COUNT(*) AS count"]
        result_fields = ["count"]

        # Map stats to their SQL aggregates
        if StatType.MEAN in stats:
            select_parts.append(f"AVG({col}) AS mean")
            result_fields.append("mean")

        # MIN is needed for MIN and RANGE
        if StatType.MIN in stats or StatType.RANGE in stats:
            select_parts.append(f"MIN({col}) AS min_val")
            result_fields.append("min_val")

        # MAX is needed for MAX and RANGE
        if StatType.MAX in stats or StatType.RANGE in stats:
            select_parts.append(f"MAX({col}) AS max_val")
            result_fields.append("max_val")

        if StatType.SUM in stats:
            select_parts.append(f"SUM({col}) AS sum_val")
            result_fields.append("sum_val")

        if StatType.STD in stats:
            select_parts.append(f"STDDEV({col}) AS std_val")
            result_fields.append("std_val")

        # Always need total_feature_area for DATA_AREA
        if StatType.DATA_AREA in stats:
            select_parts.append(f"SUM(ST_Area(t.{geom_col})) AS total_feature_area")
            result_fields.append("total_feature_area")

        return ", ".join(select_parts), result_fields

    def _calculate_touch_stats(
        self,
        wkt: str,
        aoi_area_m2: float,
        stats: list[StatType],
        vector_crs: CRS,
        center_lat: float,
    ) -> dict[str, dict]:
        """Calculate unweighted statistics using touch mode."""
        conn = self._get_connection()
        results = {}

        # Quote geometry column identifier
        geom_col = self._quote_identifier(self.geometry_column)

        for column in self.columns:
            # Quote column identifier to prevent SQL injection
            col = self._quote_identifier(column)

            # Build SELECT clause with only requested aggregates
            select_clause, result_fields = self._build_touch_select_clause(
                col, geom_col, stats
            )

            # Use parameter binding for url ($1) and wkt ($2)
            query = f"""
            WITH aoi AS (
                SELECT ST_GeomFromText($2) AS geom
            )
            SELECT {select_clause}
            FROM read_parquet($1) t, aoi
            WHERE ST_Intersects(t.{geom_col}, aoi.geom)
              AND t.{col} IS NOT NULL
            """

            try:
                result = conn.execute(query, [self.url, wkt]).fetchone()

                # Map result tuple to dict based on which fields were requested
                result_dict = dict(zip(result_fields, result, strict=False))
                count = result_dict.get("count", 0)

                # Handle empty results
                if count == 0 or count is None:
                    results[column] = self._empty_stats(stats, aoi_area_m2)
                    continue

                # Build stats dict with only computed values
                stats_dict = {"count": int(count)}

                if "mean" in result_dict:
                    stats_dict["mean"] = (
                        float(result_dict["mean"])
                        if result_dict["mean"] is not None
                        else None
                    )

                if "min_val" in result_dict:
                    stats_dict["min"] = (
                        float(result_dict["min_val"])
                        if result_dict["min_val"] is not None
                        else None
                    )

                if "max_val" in result_dict:
                    stats_dict["max"] = (
                        float(result_dict["max_val"])
                        if result_dict["max_val"] is not None
                        else None
                    )

                if "sum_val" in result_dict:
                    stats_dict["sum"] = (
                        float(result_dict["sum_val"])
                        if result_dict["sum_val"] is not None
                        else None
                    )

                if "std_val" in result_dict:
                    stats_dict["std"] = (
                        float(result_dict["std_val"])
                        if result_dict["std_val"] is not None
                        else None
                    )

                # Calculate density (features per km²)
                if StatType.DENSITY in stats:
                    density = (
                        count / (aoi_area_m2 / 1_000_000) if aoi_area_m2 > 0 else 0
                    )
                    stats_dict["density"] = float(density)

                # AOI area (computed in Python, not SQL)
                if StatType.AOI_AREA in stats:
                    stats_dict["aoi_area"] = float(aoi_area_m2)

                # Convert data_area to square meters
                if "total_feature_area" in result_dict:
                    total_area = result_dict["total_feature_area"] or 0
                    data_area_m2 = self._convert_area_to_m2(
                        total_area, vector_crs, center_lat
                    )
                    stats_dict["data_area"] = float(data_area_m2)

                # Calculate range if requested (needs both min and max)
                if StatType.RANGE in stats:
                    min_val = result_dict.get("min_val")
                    max_val = result_dict.get("max_val")
                    if min_val is not None and max_val is not None:
                        stats_dict["range"] = float(max_val - min_val)
                    else:
                        stats_dict["range"] = None

                if StatType.MEDIAN in stats:
                    median = self._calculate_median(column, wkt)
                    stats_dict["median"] = median

                if StatType.UNIQUE in stats:
                    unique = self._calculate_unique(column, wkt)
                    stats_dict["unique"] = unique

                results[column] = stats_dict

            except Exception as e:
                logger.error(f"Error calculating stats for column {column}: {e}")
                raise VectorError(
                    f"Error calculating statistics for column '{column}': {e}"
                ) from e

        return results

    def _calculate_extra_stats(
        self, column: str, wkt: str, weighted: bool = False
    ) -> dict:
        """Calculate additional statistics (std, range) for intersection mode."""
        conn = self._get_connection()

        # Quote identifiers to prevent SQL injection
        col = self._quote_identifier(column)
        geom_col = self._quote_identifier(self.geometry_column)

        if weighted:
            # Determine weight expression based on weighting method
            if self.weighting_method == WeightingMethod.AREA:
                weight_expr = "intersection_area"
            else:
                weight_expr = "intersection_area / NULLIF(ST_Area(t.{geom_col}), 0)"
                weight_expr = weight_expr.format(geom_col=geom_col)

            # For weighted std, we need a different approach
            # Use parameter binding for url ($1) and wkt ($2)
            # Filter intersection_area > 0 to match main intersect-mode stats
            query = f"""
            WITH aoi AS (
                SELECT ST_GeomFromText($2) AS geom
            ),
            intersected AS (
                SELECT
                    t.{col} as value,
                    ST_Area(
                        ST_Intersection(t.{geom_col}, aoi.geom)
                    ) AS intersection_area
                FROM read_parquet($1) t, aoi
                WHERE ST_Intersects(t.{geom_col}, aoi.geom)
                  AND t.{col} IS NOT NULL
            ),
            weighted AS (
                SELECT
                    value,
                    {weight_expr} AS weight
                FROM intersected
                WHERE intersection_area > 0
            ),
            weighted_stats AS (
                SELECT
                    SUM(value * weight) / NULLIF(SUM(weight), 0) AS weighted_mean,
                    SUM(weight) AS total_weight
                FROM weighted
            )
            SELECT
                SQRT(
                    SUM(weight * POWER(value - weighted_mean, 2))
                    / NULLIF(total_weight, 0)
                ) AS weighted_std,
                MAX(value) - MIN(value) AS range_val
            FROM weighted, weighted_stats
            """
        else:
            # Use parameter binding for url ($1) and wkt ($2)
            query = f"""
            WITH aoi AS (
                SELECT ST_GeomFromText($2) AS geom
            )
            SELECT
                STDDEV({col}) AS std_val,
                MAX({col}) - MIN({col}) AS range_val
            FROM read_parquet($1) t, aoi
            WHERE ST_Intersects(t.{geom_col}, aoi.geom)
              AND t.{col} IS NOT NULL
            """

        try:
            result = conn.execute(query, [self.url, wkt]).fetchone()
            std_val, range_val = result
            return {
                "std": float(std_val) if std_val is not None else None,
                "range": float(range_val) if range_val is not None else None,
            }
        except Exception:
            return {"std": None, "range": None}

    def _calculate_median(self, column: str, wkt: str) -> float | None:
        """Calculate median value (unweighted)."""
        conn = self._get_connection()

        # Quote identifiers to prevent SQL injection
        col = self._quote_identifier(column)
        geom_col = self._quote_identifier(self.geometry_column)

        # Use parameter binding for url ($1) and wkt ($2)
        query = f"""
        WITH aoi AS (
            SELECT ST_GeomFromText($2) AS geom
        )
        SELECT MEDIAN({col})
        FROM read_parquet($1) t, aoi
        WHERE ST_Intersects(t.{geom_col}, aoi.geom)
          AND t.{col} IS NOT NULL
        """

        try:
            result = conn.execute(query, [self.url, wkt]).fetchone()
            return float(result[0]) if result and result[0] is not None else None
        except Exception:
            return None

    def _calculate_unique(self, column: str, wkt: str) -> list:
        """Calculate unique values."""
        conn = self._get_connection()

        # Quote identifiers to prevent SQL injection
        col = self._quote_identifier(column)
        geom_col = self._quote_identifier(self.geometry_column)

        # Use parameter binding for url ($1) and wkt ($2)
        query = f"""
        WITH aoi AS (
            SELECT ST_GeomFromText($2) AS geom
        )
        SELECT DISTINCT {col}
        FROM read_parquet($1) t, aoi
        WHERE ST_Intersects(t.{geom_col}, aoi.geom)
          AND t.{col} IS NOT NULL
        ORDER BY {col}
        """

        try:
            result = conn.execute(query, [self.url, wkt]).fetchall()
            return [row[0] for row in result]
        except Exception:
            return []

    def _empty_stats(self, stats: list[StatType], aoi_area_m2: float = 0) -> dict:
        """Return empty statistics matching raster behavior."""
        result = {}
        for stat in stats:
            if stat == StatType.COUNT:
                result["count"] = 0
            elif stat == StatType.UNIQUE:
                result["unique"] = []
            elif stat == StatType.DENSITY:
                result["density"] = 0
            elif stat == StatType.AOI_AREA:
                result["aoi_area"] = float(aoi_area_m2)
            elif stat == StatType.DATA_AREA:
                result["data_area"] = 0
            elif stat in self.RASTER_ONLY_STATS:
                # Skip raster-only stats
                continue
            else:
                result[stat.value] = None
        return result

    def _process_stats_list(self, stats: list[StatType] | None) -> list[StatType]:
        """Process and filter the stats list for vector data."""
        default_stats = [StatType.MIN, StatType.MAX, StatType.MEAN, StatType.COUNT]
        if stats is None:
            base_stats = default_stats
        else:
            # Filter out raster-only stats with a warning
            filtered = []
            for stat in stats:
                if stat in self.RASTER_ONLY_STATS:
                    logger.warning(
                        f"Statistic '{stat.value}' is not applicable to vector data "
                        f"and will be ignored"
                    )
                else:
                    filtered.append(stat)
            base_stats = filtered if filtered else default_stats

        # Always include aoi_area and data_area
        if StatType.AOI_AREA not in base_stats:
            base_stats.append(StatType.AOI_AREA)
        if StatType.DATA_AREA not in base_stats:
            base_stats.append(StatType.DATA_AREA)
        return base_stats

    def _filter_stats_for_response(
        self, all_stats: dict, requested_stats: list[StatType]
    ) -> dict:
        """Filter computed stats to only include requested ones."""
        requested_names = {stat.value for stat in requested_stats}
        return {k: v for k, v in all_stats.items() if k in requested_names}

    def calculate_stats(
        self, geometry: PointGeometry | PolygonGeometry, stats: list[StatType] | None
    ) -> dict[str, BandStats]:
        """Calculate zonal statistics for vector data."""
        try:
            # Process stats list
            stats_to_use = self._process_stats_list(stats)

            # Prepare geometry
            geometry_dict, shapely_geom = self._prepare_geometry(geometry)

            # Validate columns exist and are numeric
            self._validate_columns()

            # Get vector CRS and transform AOI
            vector_crs = self._get_vector_crs()
            transformed_aoi, wkt = self._transform_aoi_to_vector_crs(
                shapely_geom, vector_crs
            )

            # Calculate AOI area for density calculation
            aoi_area_m2 = self._calculate_aoi_area_m2(shapely_geom)
            logger.info(f"AOI area: {aoi_area_m2:.2f} m²")

            # Get center latitude for area conversion (use original WGS84 geometry)
            center_lat = shapely_geom.centroid.y

            # Calculate statistics based on intersection mode
            if self.intersection_mode == "intersect":
                raw_results = self._calculate_intersection_stats(
                    wkt, aoi_area_m2, stats_to_use, vector_crs, center_lat
                )
            else:
                raw_results = self._calculate_touch_stats(
                    wkt, aoi_area_m2, stats_to_use, vector_crs, center_lat
                )

            # Filter and format results
            results = {}
            for column, column_stats in raw_results.items():
                # Filter to only requested stats
                filtered_stats = self._filter_stats_for_response(
                    column_stats, stats_to_use
                )
                results[column] = BandStats(**filtered_stats)

            return results

        except VectorError:
            raise
        except Exception as e:
            raise VectorError(f"Error calculating vector statistics: {e}") from e
        finally:
            self._close_connection()

    @staticmethod
    def validate_geometry(geometry: PointGeometry | PolygonGeometry) -> bool:
        """Validate that the geometry is valid."""
        try:
            if isinstance(geometry, PointGeometry):
                return True

            shapely_geom = shape(geometry.model_dump())
            return shapely_geom.is_valid and not shapely_geom.is_empty
        except Exception:
            return False
