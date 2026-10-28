#!/usr/bin/env python3
"""Cast the shadow of a rendered shell and compare it with the intended picture.

Takes the shell STL exactly as exported for printing (part="shell", which
prints the way it stands) and projects every triangle from the LED onto the
table. Whatever is not covered by any projected triangle
is lit. That is compared with the lit area in generated/pierrot_data.scad.

    python3 tools/check_shadow.py shell.stl [--lamp-height 150] [--png docs/shadow_check.png]

Prints the agreement and exits non-zero if light leaks where it should not.
"""

import argparse
import json
import re
import struct
import sys

import cv2
import numpy as np


def read_stl(path):
    data = open(path, "rb").read()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        v = re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data)
        return np.array(v, dtype=np.float64).reshape(-1, 3, 3)
    n = struct.unpack("<I", data[80:84])[0]
    rec = np.frombuffer(data[84:84 + 50 * n], dtype=np.dtype([
        ("n", "<f4", 3), ("v", "<f4", 9), ("a", "<u2")]))
    return rec["v"].astype(np.float64).reshape(-1, 3, 3)


def scad_value(text, name):
    m = re.search(rf"^{name}\s*=\s*(.*?);", text, re.M | re.S)
    return json.loads(m.group(1))


def clip_below(tri, zmax):
    """Polygon of a triangle's part with z <= zmax (Sutherland-Hodgman, one plane)."""
    out = []
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        ia, ib = a[2] <= zmax, b[2] <= zmax
        if ia:
            out.append(a)
        if ia != ib:
            t = (zmax - a[2]) / (b[2] - a[2])
            out.append(a + t * (b - a))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl")
    ap.add_argument("--data", default="generated/pierrot_data.scad")
    ap.add_argument("--lamp-height", type=float, help="default: the data's")
    ap.add_argument("--res", type=float, default=0.5, help="mm per pixel")
    ap.add_argument("--png", help="write a comparison picture")
    a = ap.parse_args()

    text = open(a.data).read()
    h = a.lamp_height or float(re.search(r"PD_LAMP_HEIGHT\s*=\s*([\d.]+)", text).group(1))
    lid = np.array(scad_value(text, "PD_LID"))
    pts = np.array(scad_value(text, "PD_LIGHT_POINTS"))
    paths = scad_value(text, "PD_LIGHT_PATHS")

    tris = read_stl(a.stl)

    span = np.abs(pts).max() + 20
    n = int(2 * span / a.res)
    S = 16                              # fillPoly sub-pixel shift (4 bits)

    def to_px(xy):
        return np.round((np.stack([xy[..., 0] + span, span - xy[..., 1]], -1) / a.res) * S
                        ).astype(np.int64)

    # Triangles below the LED block light; clip what crosses its height at a
    # magnification of 40, well past the edge of the raster.
    zmax = h * (1 - 1 / 40)
    zmin = tris[..., 2].min(axis=1)
    zhi = tris[..., 2].max(axis=1)
    polys = []
    whole = tris[zhi <= zmax]
    for t in tris[(zmin < zmax) & (zhi > zmax)]:
        polys.append(clip_below(t, zmax))
    mag = h / (h - whole[..., 2])
    proj_whole = whole[..., :2] * mag[..., None]
    shadow = np.zeros((n, n), np.uint8)
    lim = 2 ** 31 // (2 * S)
    pw = np.clip(to_px(proj_whole), -lim, lim).astype(np.int32)
    clipped = [np.clip(to_px(p[:, :2] * (h / (h - p[:, 2]))[:, None]), -lim, lim).astype(np.int32)
               for p in polys]
    # One polygon per call: fillPoly fills a list even-odd, so overlapping
    # triangles would cancel out. Edges are drawn too, or the seams between
    # neighbouring triangles leave hairlines that read as light.
    for p in list(pw) + clipped:
        cv2.fillConvexPoly(shadow, p, 1, cv2.LINE_8, shift=4) if len(p) == 3 else \
            cv2.fillPoly(shadow, [p], 1, cv2.LINE_8, shift=4)
        cv2.polylines(shadow, [p], True, 1, 1, cv2.LINE_8, shift=4)

    inside = np.zeros_like(shadow)
    cv2.fillPoly(inside, [to_px(lid).astype(np.int32)], 1, cv2.LINE_8, shift=4)
    lit = (1 - shadow) & (1 - inside)

    want = np.zeros_like(shadow)
    for p in paths:
        one = np.zeros_like(shadow)
        cv2.fillPoly(one, [to_px(pts[p]).astype(np.int32)], 1, cv2.LINE_8, shift=4)
        want ^= one

    # Ignore a one-pixel seam on every edge: sampling, not geometry.
    k = np.ones((3, 3), np.uint8)
    extra = lit & (1 - cv2.dilate(want, k))
    missing = want & (1 - cv2.dilate(lit, k))
    px2 = a.res ** 2
    iou = (lit & want).sum() / max((lit | want).sum(), 1)
    print(f"SHADOW: lit {lit.sum() * px2 / 100:.0f} cm2, intended {want.sum() * px2 / 100:.0f} cm2, "
          f"overlap {iou * 100:.1f}%")
    print(f"SHADOW: stray light {extra.sum() * px2:.0f} mm2, blocked {missing.sum() * px2:.0f} mm2")

    if a.png:
        img = np.full((n, n, 3), (38, 30, 28), np.uint8)
        img[lit == 1] = (196, 232, 250)
        img[missing == 1] = (60, 160, 255)
        img[extra == 1] = (40, 40, 230)
        img[inside == 1] = (90, 90, 90)
        ys, xs = np.nonzero((want | lit | inside))
        img = img[max(ys.min() - 40, 0):ys.max() + 40, max(xs.min() - 40, 0):xs.max() + 40]
        scale = 900 / img.shape[1]
        cv2.imwrite(a.png, cv2.resize(img, (900, int(img.shape[0] * scale)),
                                      interpolation=cv2.INTER_AREA))
    # Leaks of more than a few mm2 mean the walls let light out where the
    # picture is dark.
    return 1 if extra.sum() * px2 > 50 else 0


if __name__ == "__main__":
    sys.exit(main())
