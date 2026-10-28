#!/usr/bin/env python3
"""Slice an STL into print layers and find what would be printed in the air.

    check_overhang.py part.stl [--first 0.2] [--layer 0.28] [--angle 30]
                               [--bridge 15] [--res 0.1] [--png map.png]

Layer by layer (sliced at mid-height, as a slicer does): material within reach
of the layer below - reach = layer / tan(angle), angle being the slicer's
support threshold measured from horizontal - is supported. So is material
right above the layer two below: the one-layer gap a support leaves under the
part it holds.

  FLOAT - a piece of a layer with nothing under it at all: it starts in mid-air.
  SPAN  - unsupported material further than bridge/2 from anything supported
          in its own layer: a bridge or cantilever too long to print.

Prints OVERHANG lines; exit status 1 if anything floats.
"""

import argparse
import math
import sys

import cv2
import numpy as np
import trimesh


def disk(r):
    r = max(1, int(round(r)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl")
    ap.add_argument("--first", type=float, default=0.2, help="first layer height, mm")
    ap.add_argument("--layer", type=float, default=0.28, help="layer height, mm")
    ap.add_argument("--angle", type=float, default=30,
                    help="support threshold angle from horizontal, degrees")
    ap.add_argument("--bridge", type=float, default=15, help="longest printable bridge, mm")
    ap.add_argument("--res", type=float, default=0.1, help="raster step, mm")
    ap.add_argument("--min-area", type=float, default=0.3,
                    help="ignore floating specks below this, mm2 (slicer noise)")
    ap.add_argument("--png", help="top view of the problem spots")
    a = ap.parse_args()

    mesh = trimesh.load(a.stl, force="mesh")
    (x0, y0, z0), (x1, y1, z1) = mesh.bounds
    x0, y0 = x0 - 2, y0 - 2
    W, H = int((x1 + 2 - x0) / a.res) + 1, int((y1 + 2 - y0) / a.res) + 1
    zs = [z0 + a.first / 2]
    while zs[-1] + a.layer / 2 + a.layer < z1 + 1e-6:
        zs.append(z0 + a.first + (len(zs) - 0.5) * a.layer)
    reach = disk(a.layer / math.tan(math.radians(a.angle)) / a.res)
    half_bridge = a.bridge / 2 / a.res
    min_px = a.min_area / a.res ** 2

    def raster(z):
        """The layer at height z, filled by scanline parity straight from the
        cut segments. No loop reconstruction: with a slightly pinched mesh that
        joins the wrong ends and paints chords across empty space."""
        m = np.zeros((H, W), np.uint8)
        seg = trimesh.intersections.mesh_plane(mesh, [0, 0, 1], [0, 0, z])
        if len(seg) == 0:
            return m
        (xa, ya), (xb, yb) = seg[:, 0, :2].T, seg[:, 1, :2].T
        keep = ya != yb
        xa, ya, xb, yb = xa[keep], ya[keep], xb[keep], yb[keep]
        lo, hi = np.minimum(ya, yb), np.maximum(ya, yb)
        r0 = np.ceil((lo - y0) / a.res - 0.5).astype(int)   # rows whose centre is in [lo, hi)
        r1 = np.ceil((hi - y0) / a.res - 0.5).astype(int)
        n = np.maximum(r1 - r0, 0)
        idx = np.repeat(np.arange(len(n)), n)
        rows = np.repeat(r0, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
        yc = y0 + (rows + 0.5) * a.res
        xc = xa[idx] + (yc - ya[idx]) * (xb[idx] - xa[idx]) / (yb[idx] - ya[idx])
        cols = np.clip(np.ceil((xc - x0) / a.res - 0.5).astype(int), 0, W)
        ok = (rows >= 0) & (rows < H)
        hits = np.zeros((H, W + 1), np.int32)
        np.add.at(hits, (rows[ok], cols[ok]), 1)
        return (np.cumsum(hits, axis=1)[:, :W] % 2).astype(np.uint8)

    prev = prev2 = None
    floats, spans = [], []
    hot = np.zeros((H, W), np.float32)
    for k, z in enumerate(zs):
        M = raster(z)
        if prev is None:                      # first layer: on the bed
            prev2, prev = prev, M
            continue
        under = prev if prev2 is None else (prev | prev2)
        sup = M & cv2.dilate(under, reach)
        n, lab, st, ce = cv2.connectedComponentsWithStats(M, connectivity=8)
        has = np.zeros(n, bool)
        has[np.unique(lab[sup == 1])] = True
        for i in range(1, n):
            if not has[i] and st[i, cv2.CC_STAT_AREA] >= min_px:
                floats.append((z, st[i, cv2.CC_STAT_AREA] * a.res ** 2,
                               ce[i][0] * a.res + x0, ce[i][1] * a.res + y0))
                hot[lab == i] = max(hot.max(), 1)
        if sup.any():
            dist = cv2.distanceTransform((1 - sup).astype(np.uint8), cv2.DIST_L2, 5)
            far = ((M == 1) & (dist > half_bridge) & has[lab]).astype(np.uint8)
            nf, fl, fs, fc = cv2.connectedComponentsWithStats(far, connectivity=8)
            for i in range(1, nf):
                if fs[i, cv2.CC_STAT_AREA] >= min_px:
                    spans.append((z, fs[i, cv2.CC_STAT_AREA] * a.res ** 2,
                                  fc[i][0] * a.res + x0, fc[i][1] * a.res + y0))
                    hot[fl == i] = 1
        prev2, prev = prev, M

    print(f"OVERHANG: {len(zs)} layers ({a.first:g} + {a.layer:g} mm), threshold {a.angle:g} deg, "
          f"bridge {a.bridge:g} mm")
    print(f"OVERHANG: floating starts {len(floats)} ({sum(f[1] for f in floats):.1f} mm2), "
          f"long spans {len(spans)} ({sum(s[1] for s in spans):.1f} mm2)")
    for z, ar, x, y in sorted(floats, key=lambda f: -f[1])[:6]:
        print(f"  FLOAT z={z:.2f} at {x:.1f},{y:.1f}: {ar:.1f} mm2")
    for z, ar, x, y in sorted(spans, key=lambda s: -s[1])[:4]:
        print(f"  SPAN  z={z:.2f} near {x:.1f},{y:.1f}: {ar:.1f} mm2")
    if a.png:
        img = np.full((H, W, 3), 245, np.uint8)
        img[hot > 0] = (40, 40, 220)
        img = cv2.flip(img, 0)
        sc = 800 / max(W, H)
        cv2.imwrite(a.png, cv2.resize(cv2.dilate(img if False else img, None), (int(W * sc), int(H * sc)),
                                      interpolation=cv2.INTER_AREA))
    return 1 if floats else 0


if __name__ == "__main__":
    sys.exit(main())
