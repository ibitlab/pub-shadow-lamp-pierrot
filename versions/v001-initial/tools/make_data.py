#!/usr/bin/env python3
"""Turn the line drawing into geometry data for pierrot_lamp.scad.

The lamp is a box shaped like the face. Its lid is the face (with the painted
eyes); its walls carry holes, and a small LED inside, at a fixed height, shines
through them so the light on the table draws the rest of the character.

Everything is solved in "table space": millimetres on the table, origin under
the LED, y pointing up in the picture. A wall point W at height z lights the
table point  P = W * h / (h - z)  (h = LED height), so OpenSCAD cuts the holes
by subtracting   linear_extrude(height = h, scale = 0) light_2d()   from the
wall. This script only has to say which table areas must be lit.

Because far parts of the picture land on the wall heavily squeezed, the lit
area is first unrolled onto the wall, cleaned there (thin bars thickened to
--min-solid, slivers of light narrower than --min-hole dropped, loose islands
removed) and mapped back to the table, so whatever OpenSCAD cuts is printable.

Outputs:
  generated/pierrot_data.scad   polygons + numbers used by the model
  docs/projection.png           what the table should look like
  docs/wall_unrolled.png        the wall pattern, unrolled (light = hole)
"""

import argparse
import math
import os
import sys

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
        sys.exit("empty mask")
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (lab == best).astype(np.uint8)


def find_pupils(gray, thr):
    """Two small round black blobs fully surrounded by white, side by side."""
    black = (gray <= thr).astype(np.uint8)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(black, connectivity=8)
    cands = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if not (60 <= a <= 3000) or not (0.6 <= w / h <= 1.6) or a / (w * h) < 0.6:
            continue
        roi = (slice(max(y - 4, 0), y + h + 4), slice(max(x - 4, 0), x + w + 4))
        comp = (lab[roi] == i).astype(np.uint8)
        ring = cv2.dilate(comp, disk(3)) & (1 - comp)
        if gray[roi][ring == 1].min() > thr:
            cands.append(cent[i])
    best, score = None, None
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            a, b = cands[i], cands[j]
            s = abs(a[1] - b[1]) + abs((a[0] + b[0]) / 2 - gray.shape[1] / 2)
            if score is None or s < score:
                best, score = (a, b), s
    if best is None:
        sys.exit("pupils not found; pass --pupils x1,y1,x2,y2 (image pixels)")
    return sorted(best, key=lambda p: p[0])


def contour_mm(c, to_mm):
    pts = c.reshape(-1, 2).astype(np.float64)
    return to_mm(pts[:, 0], pts[:, 1])


def polygons_to_scad(mask, to_mm, eps_px, min_area_px):
    """All contours of a mask as one OpenSCAD polygon (even-odd paths)."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    points, paths = [], []
    for c in cnts:
        if abs(cv2.contourArea(c)) < min_area_px:
            continue
        c = cv2.approxPolyDP(c, eps_px, True)
        if len(c) < 3:
            continue
        x, y = contour_mm(c, to_mm)
        paths.append(list(range(len(points), len(points) + len(x))))
        points.extend(zip(x, y))
    return points, paths


def fmt_points(points):
    return "[" + ",".join(f"[{x:.2f},{y:.2f}]" for x, y in points) + "]"


def fmt_paths(paths):
    return "[" + ",".join("[" + ",".join(map(str, p)) + "]" for p in paths) + "]"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", nargs="?", default="initial1.jpg")
    ap.add_argument("--out", default="generated/pierrot_data.scad")
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--pupil-mm", type=float, default=100.0,
                    help="distance between the pupils, sets the scale")
    ap.add_argument("--pupils", help="x1,y1,x2,y2 in image pixels (auto if omitted)")
    ap.add_argument("--lamp-height", type=float, default=150.0,
                    help="LED emitter height above the table, mm")
    ap.add_argument("--wall", type=float, default=2.4, help="wall thickness, mm")
    ap.add_argument("--base", type=float, default=4.0, help="solid bottom band, mm")
    ap.add_argument("--min-solid", type=float, default=1.2,
                    help="thinnest bar left in the wall, mm")
    ap.add_argument("--min-hole", type=float, default=1.0,
                    help="narrowest hole kept in the wall, mm")
    ap.add_argument("--rib-width", type=float, default=7.0,
                    help="width of the wire rib, used to place it, mm")
    ap.add_argument("--res", type=float, default=0.25, help="raster step, mm")
    ap.add_argument("--threshold", type=int, default=128)
    # Lid outline, in image pixels (tied to this drawing's line weight).
    ap.add_argument("--lid-close", type=int, default=30)
    ap.add_argument("--lid-grow", type=int, default=14)
    ap.add_argument("--lid-smooth", type=float, default=5.0)
    ap.add_argument("--lid-star-smooth", type=float, default=1.5,
                    help="angular smoothing of the outline, degrees")
    a = ap.parse_args()

    gray0 = cv2.imread(a.image, cv2.IMREAD_GRAYSCALE)
    if gray0 is None:
        sys.exit(f"cannot read {a.image}")
    H0, W0 = gray0.shape

    if a.pupils:
        v = [float(t) for t in a.pupils.split(",")]
        pupils = [np.array(v[0:2]), np.array(v[2:4])]
    else:
        pupils = find_pupils(gray0, a.threshold)
    pupil_px = float(np.hypot(*(pupils[1] - pupils[0])))
    k = a.pupil_mm / pupil_px          # mm per image pixel
    f = k / a.res                      # raster pixels per image pixel
    print(f"pupils {pupils[0].round(1)} {pupils[1].round(1)}  {pupil_px:.1f}px  "
          f"-> {k:.4f} mm/px, drawing {W0 * k:.0f} x {H0 * k:.0f} mm")

    # --- Raster in table space ------------------------------------------------
    W, H = int(round(W0 * f)), int(round(H0 * f))
    gray = cv2.resize(gray0, (W, H), interpolation=cv2.INTER_LINEAR)
    white = (gray > a.threshold).astype(np.uint8)
    n, lab = cv2.connectedComponents(white, connectivity=4)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    background = np.isin(lab, border[border > 0]).astype(np.uint8)

    def img2r(p):                      # image pixel -> raster pixel
        return (p + 0.5) * f - 0.5

    pr = [img2r(p) for p in pupils]
    mid = (pr[0] + pr[1]) / 2
    face_label = lab[int(round(mid[1])), int(round(mid[0]))]
    if face_label == 0 or face_label in border:
        sys.exit("point between the pupils is not inside the face")
    keep = {face_label}
    for p in pr:                       # the eye white around each pupil
        y, x = int(round(p[1])), int(round(p[0]))
        rr = int(round(12 * f))
        win = lab[y - rr:y + rr, x - rr:x + rr]
        vals, cnt = np.unique(win[win > 0], return_counts=True)
        ok = ~np.isin(vals, border) & (vals != face_label)
        if ok.any():
            keep.add(vals[ok][np.argmax(cnt[ok])])
    core = np.isin(lab, list(keep)).astype(np.uint8)

    lid = cv2.morphologyEx(core, cv2.MORPH_CLOSE, disk(a.lid_close * f))
    lid = cv2.dilate(lid, disk(a.lid_grow * f))
    lid &= 1 - (white & (1 - core))    # stop at the hair / collar whites
    lid = cv2.morphologyEx(lid, cv2.MORPH_OPEN, disk(4 * f))
    lid = fill_holes(largest_component(lid))
    sm = cv2.GaussianBlur(lid.astype(np.float32), (0, 0), a.lid_smooth * f)
    lid = fill_holes(largest_component((sm > 0.5).astype(np.uint8)))

    m = cv2.moments(lid, binaryImage=True)
    cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]   # lamp axis (raster px)

    # Star-shaped around the lamp axis: every ray from the LED has to cross the
    # wall exactly once, otherwise a fold of the wall shades its own holes.
    nphi = 1440
    phis = np.linspace(-np.pi, np.pi, nphi, endpoint=False)
    rr = np.arange(0, np.hypot(W, H) / 2, 0.5)
    sx = np.clip(np.round(cx + np.cos(phis)[:, None] * rr), 0, W - 1).astype(int)
    sy = np.clip(np.round(cy - np.sin(phis)[:, None] * rr), 0, H - 1).astype(int)
    hit = lid[sy, sx] == 1
    R = rr[hit.shape[1] - 1 - np.argmax(hit[:, ::-1], axis=1)]
    g = cv2.getGaussianKernel(41, a.lid_star_smooth / 360 * nphi).ravel()
    R = np.convolve(np.concatenate([R[-20:], R, R[:20]]), g, "valid")
    star = np.stack([cx + R * np.cos(phis), cy - R * np.sin(phis)], axis=1)
    lid = np.zeros_like(lid)
    cv2.fillPoly(lid, [np.round(star * 16).astype(np.int32)], 1, cv2.LINE_8, shift=4)

    def to_mm(x, y):
        return (np.asarray(x) - cx) * a.res, -(np.asarray(y) - cy) * a.res

    def to_px(X, Y):
        return np.asarray(X) / a.res + cx, -np.asarray(Y) / a.res + cy

    light = white & (1 - background) & (1 - lid)
    ink = (1 - white) & lid
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, disk(0.3 / a.res))

    # --- Wall, unrolled: columns = arc length along mid-wall, rows = height ----
    mid_wall = cv2.erode(lid, disk(a.wall / 2 / a.res))
    c = max(cv2.findContours(mid_wall, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0],
            key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
    Xc, Yc = to_mm(c[:, 0], c[:, 1])
    if np.sum(Xc * np.roll(Yc, -1) - np.roll(Xc, -1) * Yc) < 0:   # make CCW
        Xc, Yc = Xc[::-1], Yc[::-1]
    seg = np.hypot(np.diff(Xc, append=Xc[0]), np.diff(Yc, append=Yc[0]))
    s_acc = np.concatenate([[0], np.cumsum(seg)])
    L = s_acc[-1]
    ns = int(round(L / a.res))
    s = (np.arange(ns) + 0.5) * L / ns
    Ws_x = np.interp(s, s_acc, np.append(Xc, Xc[0]))
    Ws_y = np.interp(s, s_acc, np.append(Yc, Yc[0]))
    phi_s = np.unwrap(np.arctan2(Ws_y, Ws_x))
    R_s = np.hypot(Ws_x, Ws_y)
    fold = np.maximum.accumulate(phi_s) - phi_s     # pixel-step noise is tiny
    if fold.max() > math.radians(0.5):
        print(f"WARNING: wall folds back by {math.degrees(fold.max()):.1f} deg "
              "as seen from the LED; holes there will be shaded")

    h = a.lamp_height
    nz = int(math.ceil(h / a.res))
    z = (np.arange(nz) + 0.5) * a.res
    mag = h / (h - z)
    mx, my = to_px(Ws_x[None, :] * mag[:, None], Ws_y[None, :] * mag[:, None])
    wall_light = cv2.remap(light.astype(np.float32), mx.astype(np.float32),
                           my.astype(np.float32), cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0.5
    lit_rows = np.nonzero(wall_light.any(axis=1))[0]
    z_top_raw = z[lit_rows[-1]] if len(lit_rows) else 0

    # Clean up on the wall. Roll so the seam sits in the most solid column.
    seam = int(np.argmin(wall_light.sum(axis=0)))
    wl = np.roll(wall_light, -seam, axis=1).astype(np.uint8)
    wl[z < a.base, :] = 0
    pad = int(3 * max(a.min_solid, a.min_hole) / a.res) + 2
    wlp = np.pad(wl, ((pad, pad), (pad, pad)), mode="wrap")
    wlp[:pad, :] = 0
    wlp[-pad:, :] = 0
    solid = 1 - wlp
    rs = a.min_solid / 2 / a.res
    thin = solid & (1 - cv2.morphologyEx(solid, cv2.MORPH_OPEN, disk(rs)))
    solid = solid | cv2.dilate(thin, disk(rs))
    lightp = cv2.morphologyEx(1 - solid, cv2.MORPH_OPEN, disk(a.min_hole / 2 / a.res))
    wl2 = lightp[pad:-pad, pad:-pad]
    # Solid islands would fall out of the wall: tie each one to the nearest
    # solid with a bar of --min-solid (a thin dark line on the table).
    nsol, slab, sst, scent = cv2.connectedComponentsWithStats(1 - wl2, connectivity=8)
    main = slab[0, 0]
    islands = [i for i in range(1, nsol) if i != main]
    dist = cv2.distanceTransform((slab != main).astype(np.uint8), cv2.DIST_L2, 5)
    bar = max(2, int(round(a.min_solid / a.res)))
    for i in islands:
        iy, ix = np.nonzero(slab == i)
        q = int(np.argmin(dist[iy, ix]))
        py, px = iy[q], ix[q]
        d = int(math.ceil(dist[py, px])) + 2
        wy, wx = np.nonzero(slab[max(py - d, 0):py + d + 1, max(px - d, 0):px + d + 1] == main)
        t = int(np.argmin((wy + max(py - d, 0) - py) ** 2 + (wx + max(px - d, 0) - px) ** 2))
        ty, tx = wy[t] + max(py - d, 0), wx[t] + max(px - d, 0)
        cv2.line(wl2, (int(px), int(py)), (int(tx), int(ty)), 0, bar)
        col_ = (scent[i][0] + seam) % ns
        print(f"  island {sst[i, cv2.CC_STAT_AREA] * a.res ** 2:.1f} mm2 at "
              f"s={col_ * L / ns:.0f} z={scent[i][1] * a.res:.0f} mm, "
              f"bridged {dist[py, px] * a.res:.1f} mm")
    wall_clean = np.roll(wl2, seam, axis=1)
    removed = 1 - wall_clean.sum() / max(wall_light.sum(), 1)
    lit_rows = np.nonzero(wall_clean.any(axis=1))[0]
    z_top = z[lit_rows[-1]] if len(lit_rows) else 0

    # --- Back to the table -----------------------------------------------------
    yy, xx = np.mgrid[0:H, 0:W]
    TX, TY = to_mm(xx, yy)
    r = np.hypot(TX, TY)
    ph = np.arctan2(TY, TX)
    # s and R as functions of the azimuth, continuous across the seam
    pk = np.maximum.accumulate(phi_s)
    pk = np.concatenate([pk[-1:] - 2 * np.pi, pk, pk[:1] + 2 * np.pi])
    sk = np.concatenate([s[-1:] - L, s, s[:1] + L])
    Rk = np.concatenate([R_s[-1:], R_s, R_s[:1]])
    php = phi_s[0] + np.mod(ph - phi_s[0], 2 * np.pi)
    S = np.mod(np.interp(php, pk, sk), L)
    Rw = np.interp(php, pk, Rk)
    Z = np.where(r > Rw, h * (1 - Rw / np.maximum(r, 1e-9)), -1.0)
    col = (S / (L / ns) - 0.5).astype(np.float32)
    row = (Z / a.res - 0.5).astype(np.float32)
    row[Z < 0] = -10
    light_final = cv2.remap(wall_clean.astype(np.float32), col, row, cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0.5
    light_final = light_final.astype(np.uint8) & (1 - lid)

    # --- Pins, wire rib --------------------------------------------------------
    rib_cols = max(1, int(round(a.rib_width / (L / ns))))
    # A wall pixel at height z covers a table patch growing as (h / (h - z))^3:
    # weigh by that, so the rib goes where it darkens the least table.
    lit_per_col = (wall_clean * (mag ** 3)[:, None]).sum(axis=0)
    win = np.convolve(np.concatenate([lit_per_col, lit_per_col[:rib_cols]]),
                      np.ones(rib_cols), "valid")[:ns]
    j = (int(np.argmin(win)) + rib_cols // 2) % ns
    wire_dir = math.atan2(Ws_y[j], Ws_x[j])
    lid_c = max(cv2.findContours(lid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0],
                key=cv2.contourArea)
    LX, LY = contour_mm(lid_c, to_mm)
    ang = np.arctan2(LY, LX)

    def outer_at(t):
        d = np.angle(np.exp(1j * (ang - t)))
        i = int(np.argmin(np.abs(d) - 1e-6 * np.hypot(LX, LY)))
        return LX[i], LY[i]

    wire = outer_at(wire_dir)
    pins = []
    for off in (60, 180, 300):
        t = wire_dir + math.radians(off)
        px_, py_ = outer_at(t)
        pins.append((0.55 * px_, 0.55 * py_))

    # --- Write SCAD ------------------------------------------------------------
    lid_pts = cv2.approxPolyDP(lid_c, 0.4, True)
    LXs, LYs = contour_mm(lid_pts, to_mm)
    lid_poly = list(zip(LXs, LYs))
    if np.sum(LXs * np.roll(LYs, -1) - np.roll(LXs, -1) * LYs) < 0:
        lid_poly = lid_poly[::-1]
    light_pts, light_paths = polygons_to_scad(light_final, to_mm, 0.6, (0.5 / a.res) ** 2)
    ink_pts, ink_paths = polygons_to_scad(ink, to_mm, 0.5, (0.8 / a.res) ** 2)
    ex = np.nonzero(light_final.any(axis=0))[0]
    ey = np.nonzero(light_final.any(axis=1))[0]
    x0, y1 = to_mm(ex[0], ey[0])
    x1, y0 = to_mm(ex[-1], ey[-1])
    pmm = [to_mm(*img2r(p)) for p in pupils]

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fo:
        fo.write("// Generated by tools/make_data.py from the drawing. Do not edit by hand;\n")
        fo.write("// rerun the script instead (see README). Units: mm, origin under the LED.\n\n")
        fo.write(f"PD_PUPIL_MM = {a.pupil_mm:g};\n")
        fo.write(f"PD_LAMP_HEIGHT = {h:g};   // LED height the cleanup was done for\n")
        fo.write(f"PD_WALL = {a.wall:g};\n")
        fo.write(f"PD_BASE = {a.base:g};\n")
        fo.write(f"PD_MIN_SOLID = {a.min_solid:g};\n")
        fo.write(f"PD_MIN_HOLE = {a.min_hole:g};\n")
        fo.write(f"PD_Z_TOP = {z_top:.1f};   // highest hole in the wall\n")
        fo.write(f"PD_EXTENT = [{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}];   // lit area on the table\n")
        fo.write(f"PD_PUPILS = {fmt_points(pmm)};\n")
        fo.write(f"PD_WIRE = [{wire[0]:.2f},{wire[1]:.2f}];   // outer wall point of the wire rib\n")
        fo.write(f"PD_PINS = {fmt_points(pins)};\n\n")
        fo.write(f"PD_LID = {fmt_points(lid_poly)};\n\n")
        fo.write(f"PD_INK_POINTS = {fmt_points(ink_pts)};\n")
        fo.write(f"PD_INK_PATHS = {fmt_paths(ink_paths)};\n\n")
        fo.write(f"PD_LIGHT_POINTS = {fmt_points(light_pts)};\n")
        fo.write(f"PD_LIGHT_PATHS = {fmt_paths(light_paths)};\n")

    # --- Previews --------------------------------------------------------------
    os.makedirs(a.docs, exist_ok=True)
    prev = np.full((H, W, 3), (38, 30, 28), np.uint8)
    prev[light_final == 1] = (196, 232, 250)
    prev[lid == 1] = (245, 245, 245)
    prev[(ink == 1)] = (20, 20, 20)
    cv2.circle(prev, (int(cx), int(cy)), int(2 / a.res), (0, 0, 255), -1)
    sc = 900 / W
    cv2.imwrite(os.path.join(a.docs, "projection.png"),
                cv2.resize(prev, (900, int(H * sc)), interpolation=cv2.INTER_AREA))
    wimg = np.flipud(np.where(wall_clean[:, :, None] == 1,
                              np.array([196, 232, 250], np.uint8),
                              np.array([38, 30, 28], np.uint8)))
    wimg = wimg[nz - int(min(h, z_top + 10) / a.res):]
    cv2.imwrite(os.path.join(a.docs, "wall_unrolled.png"),
                cv2.resize(wimg, (1600, int(wimg.shape[0] * 1600 / ns)),
                           interpolation=cv2.INTER_AREA))

    print(f"lid {np.ptp(LXs):.0f} x {np.ptp(LYs):.0f} mm, wall length {L:.0f} mm, "
          f"R {R_s.min():.0f}..{R_s.max():.0f} mm")
    print(f"lit table area {x0:.0f}..{x1:.0f} x {y0:.0f}..{y1:.0f} mm, "
          f"max r/R {(np.max(r[light_final == 1]) / R_s.min()):.2f}")
    print(f"holes reach z {z_top:.1f} mm (raw {z_top_raw:.1f}) of LED {h:g} mm; "
          f"cleanup removed {removed * 100:.1f}% of the wall light; "
          f"{len(islands)} islands bridged")
    print(f"wire rib at {math.degrees(wire_dir):.1f} deg, "
          f"light polygon {len(light_pts)} pts/{len(light_paths)} paths, "
          f"ink {len(ink_pts)} pts/{len(ink_paths)} paths")


if __name__ == "__main__":
    main()
