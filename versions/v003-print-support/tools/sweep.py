#!/usr/bin/env python3
"""How low can the lamp go? Run the generator at several LED heights.

    tools/sweep.py IMAGE --heights 40,60,80,100 [any make_data.py options]

Prints one SWEEP line per height (how much of the picture the wall cleanup has
to drop, how high the holes reach, total lamp height) and writes one labelled
picture, docs/sweep.png, so the variants cost one look instead of several.
The project's own generated data is not touched.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from drawlib import montage  # noqa: E402

# Height above the LED: board drop + ceiling + lid, as in lamp.scad's defaults.
ABOVE_LED = 1.5 + 6 + 3.5


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--heights", default="40,60,80,100")
    ap.add_argument("--png", default="docs/sweep.png")
    a, rest = ap.parse_known_args()

    pics, labels = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for h in [float(v) for v in a.heights.split(",")]:
            d = os.path.join(tmp, f"h{h:g}")
            r = subprocess.run([sys.executable, os.path.join(HERE, "make_data.py"), a.image,
                                "--lamp-height", f"{h:g}", "--out", os.path.join(d, "data.scad"),
                                "--docs", d] + rest, capture_output=True, text=True)
            if r.returncode:
                print(f"SWEEP h={h:g}: failed: {r.stderr.strip().splitlines()[-1:]}")
                continue
            lost = re.search(r"cleanup removed ([\d.]+)%", r.stdout)
            top = re.search(r"holes reach z ([\d.]+)", r.stdout)
            print(f"SWEEP h={h:g}: lost {lost.group(1)}% of the picture, holes up to z={top.group(1)}, "
                  f"lamp ~{h + ABOVE_LED:.0f} mm tall")
            pics.append(cv2.imread(os.path.join(d, "projection.png")))
            labels.append(f"h={h:g}")
    if pics:
        os.makedirs(os.path.dirname(a.png) or ".", exist_ok=True)
        cv2.imwrite(a.png, montage(pics, labels, 1600, (0.15, 0.95)))
        print(f"SWEEP: picture {a.png}")


if __name__ == "__main__":
    main()
