"""
FWRL screen-region calibration helper.

Run this while the race game is on screen (or with a saved screenshot) to
visually select the crop boxes for each HUD element, then save them into
config.json so capture_agent.py knows exactly where to look.

Usage:
    python calibrate.py                # captures your primary monitor now
    python calibrate.py --image shot.png   # calibrate against a saved screenshot

Controls:
    - A window opens for each region ("position", "lap", "pit_indicator").
    - Click-drag a box around the element, press ENTER/SPACE to confirm,
      or press "c" to cancel the selection and retry.
    - Press ESC at any point to skip a region (keeps the old box).
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import mss
import numpy as np

CONFIG_PATH = Path(__file__).parent / "config.json"
REGIONS_TO_CALIBRATE = ["position", "lap", "pit_indicator"]


def grab_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        shot = np.array(sct.grab(monitor))
        return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def select_region(img, label):
    print(f"\nSelect the '{label}' region. Drag a box, then press ENTER. Press ESC to skip.")
    box = cv2.selectROI(f"Calibrate: {label}", img, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(f"Calibrate: {label}")
    x, y, w, h = box
    if w == 0 or h == 0:
        print(f"  Skipped '{label}' (no box drawn).")
        return None
    return [int(x), int(y), int(w), int(h)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="Path to a saved screenshot to calibrate against instead of live capture.")
    args = parser.parse_args()

    if args.image:
        img = cv2.imread(args.image)
        if img is None:
            print(f"Could not load image: {args.image}")
            sys.exit(1)
    else:
        img = grab_screen()

    cfg = load_config()
    h, w = img.shape[:2]
    cfg["resolution"] = [w, h]

    for region_name in REGIONS_TO_CALIBRATE:
        box = select_region(img, region_name)
        if box is not None:
            cfg["regions"][region_name]["box"] = box
            if region_name == "pit_indicator":
                x, y, bw, bh = box
                crop = img[y:y + bh, x:x + bw]
                template_path = Path(__file__).parent / "pit_icon_template.png"
                cv2.imwrite(str(template_path), crop)
                print(f"  Saved pit indicator template to {template_path}")

    save_config(cfg)
    print(f"\nSaved regions to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
