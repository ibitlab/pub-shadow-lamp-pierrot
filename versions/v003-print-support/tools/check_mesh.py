#!/usr/bin/env python3
"""Closed-mesh check for STL files: every edge must be shared by an even
number of triangles (2, or 4 where two bodies just touch at a vertex line).

    python3 tools/check_mesh.py out/*.stl
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from check_shadow import read_stl  # noqa: E402


def main(paths):
    bad = 0
    for p in paths:
        tris = read_stl(p)
        v, idx = np.unique(tris.reshape(-1, 3), axis=0, return_inverse=True)
        f = idx.reshape(-1, 3)
        e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
        _, cnt = np.unique(e, axis=0, return_counts=True)
        odd = int((cnt % 2 == 1).sum())
        pinch = int((cnt > 2).sum())
        lo, hi = v.min(axis=0), v.max(axis=0)
        size = " x ".join(f"{d:.1f}" for d in hi - lo)
        print(f"MESH {os.path.basename(p)}: {len(f)} triangles, {size} mm, "
              f"open edges {odd}, pinched edges {pinch}")
        bad += odd > 0
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
