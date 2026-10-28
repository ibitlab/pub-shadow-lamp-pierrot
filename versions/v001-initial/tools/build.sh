#!/bin/sh
# Render every printable part into out/ and check them.
#   tools/build.sh                 all parts
#   PY=.venv/bin/python tools/build.sh
set -e
cd "$(dirname "$0")/.."
PY=${PY:-python3}
OPENSCAD=${OPENSCAD:-openscad}
mkdir -p out

for p in shell ceiling lid lid_ink; do
    "$OPENSCAD" --backend=manifold --export-format binstl -D "part=\"$p\"" \
        -o "out/pierrot_$p.stl" pierrot_lamp.scad 2>&1 | grep -E "^(ECHO: \"WARNING|ERROR|WARNING)" || true
done
"$OPENSCAD" --backend=manifold -D 'part="assembly"' --render --imgsize=1200,1000 \
    --camera=0,0,60,65,0,20,900 --colorscheme=Tomorrow -o docs/assembly.png pierrot_lamp.scad 2>/dev/null

"$PY" tools/check_mesh.py out/pierrot_*.stl
"$PY" tools/check_shadow.py out/pierrot_shell.stl --png docs/shadow_check.png
