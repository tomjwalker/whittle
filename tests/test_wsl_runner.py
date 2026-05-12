from __future__ import annotations

from pathlib import Path

from whittle.openfoam.wsl_runner import OpenFOAMRunConfig, build_wsl_openfoam_script


def test_wsl_runner_includes_toposet_when_case_has_toposet_dict(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    (case_dir / "system").mkdir(parents=True)
    (case_dir / "system" / "topoSetDict").write_text("actions();", encoding="utf-8")

    script = build_wsl_openfoam_script(
        OpenFOAMRunConfig(case_dir=case_dir, case_name="case"),
    )

    assert "snappyHexMesh -overwrite" in script
    assert "run_whittle_step topoSet topoSet" in script
    assert "run_whittle_step checkMesh checkMesh" in script
    assert "run_whittle_step simpleFoam simpleFoam" in script
    assert 'if [ "${status}" -ne 0 ] && [ "${slug}" != "checkMesh" ]; then' in script


def test_wsl_runner_skips_toposet_when_not_needed(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    script = build_wsl_openfoam_script(
        OpenFOAMRunConfig(case_dir=case_dir, case_name="case"),
    )

    assert "run_whittle_step topoSet topoSet" not in script
