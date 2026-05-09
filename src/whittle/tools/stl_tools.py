"""Small STL metadata reader used before OpenFOAM case generation."""

from __future__ import annotations

import math
import struct
from pathlib import Path

from whittle.models.geometry import StlMetadata, Vector3

_BINARY_TRIANGLE_RECORD = struct.Struct("<12x9f2x")


def read_stl_metadata(path: Path) -> StlMetadata:
    """Read lightweight STL metadata without depending on CAD libraries."""

    path = Path(path)
    warnings: list[str] = []
    if not path.exists():
        return StlMetadata(
            source_path=path,
            file_size_bytes=0,
            format="unknown",
            warnings=[f"Geometry file does not exist: {path}"],
        )

    size = path.stat().st_size
    with path.open("rb") as file:
        header = file.read(84)
    if len(header) < 84:
        return StlMetadata(
            source_path=path,
            file_size_bytes=size,
            format="unknown",
            warnings=["STL file is too small to contain a valid header."],
        )

    binary_triangle_count = struct.unpack("<I", header[80:84])[0]
    expected_binary_size = 84 + binary_triangle_count * _BINARY_TRIANGLE_RECORD.size

    if expected_binary_size == size:
        metadata = _read_binary_stl(path, size, binary_triangle_count, warnings)
    elif header[:5].lower() == b"solid":
        metadata = _read_ascii_stl(path, size, warnings)
    else:
        metadata = StlMetadata(
            source_path=path,
            file_size_bytes=size,
            format="unknown",
            warnings=["STL format could not be identified as binary or ASCII."],
        )

    if size > 50 * 1024 * 1024:
        metadata.warnings.append(
            "Large STL input; meshing may be slow or require later decimation/splitting."
        )
    return metadata


def _read_binary_stl(
    path: Path,
    size: int,
    triangle_count: int,
    warnings: list[str],
) -> StlMetadata:
    mins = [math.inf, math.inf, math.inf]
    maxs = [-math.inf, -math.inf, -math.inf]
    finite_vertices = True

    with path.open("rb") as file:
        file.seek(84)
        chunk_size = _BINARY_TRIANGLE_RECORD.size * 50_000
        while data := file.read(chunk_size):
            usable = len(data) - (len(data) % _BINARY_TRIANGLE_RECORD.size)
            for values in _BINARY_TRIANGLE_RECORD.iter_unpack(data[:usable]):
                for index in range(0, 9, 3):
                    x, y, z = values[index], values[index + 1], values[index + 2]
                    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                        finite_vertices = False
                    mins[0] = min(mins[0], x)
                    mins[1] = min(mins[1], y)
                    mins[2] = min(mins[2], z)
                    maxs[0] = max(maxs[0], x)
                    maxs[1] = max(maxs[1], y)
                    maxs[2] = max(maxs[2], z)

    if not finite_vertices:
        warnings.append("STL contains non-finite vertex coordinates.")

    bounds_min = _to_vector(mins)
    bounds_max = _to_vector(maxs)
    dimensions = _dimensions(bounds_min, bounds_max)
    inferred_units, scale_to_m = _infer_units(dimensions)

    if inferred_units == "mm":
        warnings.append("STL dimensions look millimetre-scale; using scale_to_m=0.001.")
    elif inferred_units == "unknown":
        warnings.append("Could not infer STL units from dimensions.")

    return StlMetadata(
        source_path=path,
        file_size_bytes=size,
        format="binary",
        triangle_count=triangle_count,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        dimensions_raw=dimensions,
        inferred_units=inferred_units,
        scale_to_m=scale_to_m,
        warnings=warnings,
    )


def _read_ascii_stl(path: Path, size: int, warnings: list[str]) -> StlMetadata:
    mins = [math.inf, math.inf, math.inf]
    maxs = [-math.inf, -math.inf, -math.inf]
    vertex_count = 0

    with path.open("r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            parts = line.strip().split()
            if len(parts) == 4 and parts[0].lower() == "vertex":
                try:
                    x, y, z = (float(parts[1]), float(parts[2]), float(parts[3]))
                except ValueError:
                    warnings.append(f"Could not parse STL vertex line: {line.strip()}")
                    continue
                vertex_count += 1
                mins[0] = min(mins[0], x)
                mins[1] = min(mins[1], y)
                mins[2] = min(mins[2], z)
                maxs[0] = max(maxs[0], x)
                maxs[1] = max(maxs[1], y)
                maxs[2] = max(maxs[2], z)

    if vertex_count == 0:
        return StlMetadata(
            source_path=path,
            file_size_bytes=size,
            format="ascii",
            warnings=warnings + ["ASCII STL contained no parseable vertex lines."],
        )

    bounds_min = _to_vector(mins)
    bounds_max = _to_vector(maxs)
    dimensions = _dimensions(bounds_min, bounds_max)
    inferred_units, scale_to_m = _infer_units(dimensions)
    return StlMetadata(
        source_path=path,
        file_size_bytes=size,
        format="ascii",
        triangle_count=vertex_count // 3,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        dimensions_raw=dimensions,
        inferred_units=inferred_units,
        scale_to_m=scale_to_m,
        warnings=warnings,
    )


def _to_vector(values: list[float]) -> Vector3:
    return (float(values[0]), float(values[1]), float(values[2]))


def _dimensions(bounds_min: Vector3, bounds_max: Vector3) -> Vector3:
    return (
        bounds_max[0] - bounds_min[0],
        bounds_max[1] - bounds_min[1],
        bounds_max[2] - bounds_min[2],
    )


def _infer_units(dimensions: Vector3 | None) -> tuple[str, float]:
    if not dimensions:
        return "unknown", 1.0

    max_dim = max(dimensions)
    if max_dim > 10.0:
        return "mm", 0.001
    if 0.001 <= max_dim <= 10.0:
        return "m", 1.0
    return "unknown", 1.0
