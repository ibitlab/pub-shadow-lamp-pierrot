"""Helpers for turning a black-and-white line drawing into geometry.

Import it from a script that lives next to it (projects keep their own copy in
tools/, so they stay self-contained):

    from drawlib import disk, fill_holes, find_pupils, polygons_to_scad, ...

Conventions: masks are uint8 arrays of 0/1; "white" is gray > threshold;
image coordinates are pixels with y down; to_mm(x, y) callbacks return
millimetres with y up.
"""

import cv2
import numpy as np


def disk(r):
    r = max(1, int(round(r)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def fill_holes(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = np.zeros_like(mask)
    cv2.drawContours(out, cnts, -1, 1, -1)
    return out


def largest_component(mask):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    if n <= 1:
        raise ValueError("empty mask")
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (lab == best).astype(np.uint8)


def touching(mask, seed):
    """Components of mask (8-connected) that touch seed."""
    _, cl = cv2.connectedComponents(mask, connectivity=8)
    keep = np.unique(cl[(seed == 1) & (mask == 1)])
    return np.isin(cl, keep[keep > 0]).astype(np.uint8)


def background(white):
    """White regions connected to the image border (outside the drawing)."""
    _, lab = cv2.connectedComponents(white, connectivity=4)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    return np.isin(lab, border[border > 0]).astype(np.uint8)


def stroke_width_px(gray, thr=128):
    """Median line weight of the drawing, in pixels."""
    black = (gray <= thr).astype(np.uint8)
    dt = cv2.distanceTransform(black, cv2.DIST_L2, 5)
    ridge = (dt >= cv2.dilate(dt, np.ones((3, 3), np.uint8))) & (dt > 1)
    return float(np.median(2 * dt[ridge]))


def round_blobs(gray, thr=128, area=(60, 3000)):
    """Small round black blobs fully surrounded by white (pupils, dots).
    Returns [(x, y, area)]."""
    black = (gray <= thr).astype(np.uint8)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(black, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if not (area[0] <= a <= area[1]) or not (0.6 <= w / h <= 1.6) or a / (w * h) < 0.6:
            continue
        roi = (slice(max(y - 4, 0), y + h + 4), slice(max(x - 4, 0), x + w + 4))
        comp = (lab[roi] == i).astype(np.uint8)
        ring = cv2.dilate(comp, disk(3)) & (1 - comp)
        if gray[roi][ring == 1].min() > thr:
            out.append((float(cent[i][0]), float(cent[i][1]), int(a)))
    return out


def find_pupils(gray, thr=128):
    """The pair of round blobs most like two eyes: level, centred. None if absent."""
    c = round_blobs(gray, thr)
    best, score = None, None
    for i in range(len(c)):
        for j in range(i + 1, len(c)):
            a, b = c[i], c[j]
            s = abs(a[1] - b[1]) + abs((a[0] + b[0]) / 2 - gray.shape[1] / 2)
            if score is None or s < score:
                best, score = (np.array(a[:2]), np.array(b[:2])), s
    return None if best is None else sorted(best, key=lambda p: p[0])


def polygons_to_scad(mask, to_mm, eps_px, min_area_px):
    """All contours of a mask as one OpenSCAD polygon(points, paths).
    OpenSCAD fills multiple paths even-odd, which matches outer/hole nesting."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    points, paths = [], []
    for c in cnts:
        if abs(cv2.contourArea(c)) < min_area_px:
            continue
        c = cv2.approxPolyDP(c, eps_px, True)
        if len(c) < 3:
            continue
        p = c.reshape(-1, 2).astype(np.float64)
        x, y = to_mm(p[:, 0], p[:, 1])
        paths.append(list(range(len(points), len(points) + len(x))))
        points.extend(zip(x, y))
    return points, paths


def fmt_points(points):
    return "[" + ",".join(f"[{x:.2f},{y:.2f}]" for x, y in points) + "]"


def fmt_paths(paths):
    return "[" + ",".join("[" + ",".join(map(str, p)) + "]" for p in paths) + "]"


def montage(images, labels=None, width=1600, crop=None):
    """Side by side, one picture to look at instead of several.
    crop = (top, bottom) as fractions of height."""
    tiles = []
    for i, im in enumerate(images):
        if crop:
            h = im.shape[0]
            im = im[int(h * crop[0]):int(h * crop[1])]
        tiles.append(im)
    h = min(t.shape[0] for t in tiles)
    tiles = [cv2.resize(t, (int(t.shape[1] * h / t.shape[0]), h)) for t in tiles]
    out = np.hstack(tiles)
    if labels:
        x = 0
        for t, lab in zip(tiles, labels):
            cv2.putText(out, str(lab), (x + 10, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 2)
            x += t.shape[1]
    if out.shape[1] > width:
        out = cv2.resize(out, (width, int(out.shape[0] * width / out.shape[1])),
                         interpolation=cv2.INTER_AREA)
    return out
