from __future__ import annotations

import struct
from pathlib import Path

from whittle.tools.stl_tools import read_stl_metadata


def test_binary_stl_metadata_reads_triangle_count_and_bounds(tmp_path: Path) -> None:
    stl_path = tmp_path / "triangle.stl"
    _write_binary_stl(stl_path)

    metadata = read_stl_metadata(stl_path)

    assert metadata.format == "binary"
    assert metadata.triangle_count == 1
    assert metadata.bounds_min == (0.0, 0.0, 0.0)
    assert metadata.bounds_max == (1.0, 1.0, 0.0)
    assert metadata.dimensions_raw == (1.0, 1.0, 0.0)


def _write_binary_stl(path: Path) -> None:
    header = b"test binary stl".ljust(80, b" ")
    triangle_count = struct.pack("<I", 1)
    triangle = struct.pack(
        "<12fH",
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0,
    )
    path.write_bytes(header + triangle_count + triangle)

