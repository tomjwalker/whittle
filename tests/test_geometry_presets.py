from __future__ import annotations

from pathlib import Path

from whittle.tools.geometry_presets import build_legacy_box_geometry, build_single_stl_geometry


def test_legacy_box_preset_uses_expected_split_patch_names() -> None:
    geometry = build_legacy_box_geometry()

    assert geometry.geometry_mode == "surface_set"
    assert geometry.patch_names == [
        "drone_body",
        "propeller_fr",
        "propeller_br",
        "propeller_fl",
        "propeller_bl",
    ]
    assert all(surface.source_path.exists() for surface in geometry.surfaces)


def test_single_stl_geometry_uses_one_drone_patch(tmp_path: Path) -> None:
    stl_path = tmp_path / "drone.stl"
    stl_path.write_bytes(b"short")

    geometry = build_single_stl_geometry(stl_path)

    assert geometry.geometry_mode == "single_stl"
    assert geometry.patch_names == ["drone"]
    assert geometry.surfaces[0].target_file_name == "drone.stl"

