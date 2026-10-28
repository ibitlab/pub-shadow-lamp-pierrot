#!/bin/sh
# Render every printable part into out/ and check them.
#   tools/build.sh                 all parts
#   PY=.venv/bin/python tools/build.sh
set -e
cd "$(dirname "$0")/.."
PY=${PY:-python3}
OPENSCAD=${OPENSCAD:-openscad}
mkdir -p out

for p in shell shell_print ceiling lid lid_ink pins; do
    "$OPENSCAD" --backend=manifold --export-format binstl -D "part=\"$p\"" \
        -o "out/pierrot_$p.stl" pierrot_lamp.scad 2>&1 | grep -E "^(ECHO: \"WARNING|ERROR|WARNING)" || true
done
# Lid in two colours: two bodies, one per filament, in a single 3MF.
"$OPENSCAD" --backend=manifold --enable=lazy-union -O export-3mf/add-meta-data=false \
    -D 'part="lid_2color"' -o out/pierrot_lid_2color.3mf pierrot_lamp.scad 2>&1 | grep -E "^(ERROR|WARNING)" || true
"$PY" tools/lid_3mf.py out/pierrot_lid_2color.3mf
"$OPENSCAD" --backend=manifold -D 'part="assembly"' --render --imgsize=1200,1000 \
    --camera=0,0,30,62,0,20,800 --colorscheme=Tomorrow -o docs/assembly.png pierrot_lamp.scad 2>/dev/null

"$PY" tools/check_mesh.py out/pierrot_*.stl
"$PY" tools/check_shadow.py out/pierrot_shell.stl --png docs/shadow_check.png
"$PY" tools/check_overhang.py out/pierrot_shell_print.stl --png docs/overhang_check.png || true
