# Shadow lamp «Pierrot»

OpenSCAD shadow lamp from `initial1.jpg`: the face is the lid, light through
the walls draws the rest of the character on the table. Skills: `shadow-lamp`
(how it works, decisions), `slicer-3mf`, `scad-version`, `drawing-to-geometry`.

- Each iteration is a complete folder in `versions/vNNN-name/`; the latest is
  the one to change. A new one: `scad-version` skill, never edit an older one.
- Work from the version folder: `make data H=80`, `make build`,
  `make sweep HEIGHTS=40,60,80`. Python is `$SCAD_PY` (shared venv).
- Trust the printed checks: `open edges 0`, `stray light` ~0 mm².
- Don't open `generated/*.scad` (large coordinate data) or `out/` meshes.
- README per version, in Ukrainian; commit messages in English.
