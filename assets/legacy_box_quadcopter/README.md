# Legacy Box Quadcopter Assets

This directory contains the split quadcopter STL geometry used by the
`--preset legacy-box` workflow. These are the public out-of-the-box assets for
the MRF, rotor-disk, and roll/pitch/yaw attitude cases.

The original development geometry was copied from the prior local OpenFOAM
case:

```text
\\wsl$\Ubuntu-22.04\home\tjwalker\OpenFOAM\cases\BoxQuadcopterCase\constant\triSurface
```

They are retained because they are already split into body and propeller
surfaces and were referenced by a prior OpenFOAM case.

Included surfaces:

- `drone_model_box__body.stl` -> `drone_body`
- `drone_model_box__prop_fr.stl` -> `propeller_fr`
- `drone_model_box__prop_br.stl` -> `propeller_br`
- `drone_model_box__prop_fl.stl` -> `propeller_fl`
- `drone_model_box__prop_bl.stl` -> `propeller_bl`

The current monolithic hexacopter STL remains a local ignored input under
`cad/` or `CAD/` and is not committed here.
