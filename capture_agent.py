"""
FWRL capture agent.

Runs alongside the race on the host PC. Periodically screenshots the
calibrated HUD regions, reads position/lap via OCR and pit status via
template matching, applies a confirm-frames smoothing filter to avoid
pushing single-frame misreads, and POSTs confirmed updates to the bot's
local endpoint.

This does NOT talk to Discord directly -- it only talks to bot.py over
localhost. Run bot.py first, then this.

Usage:
    python capture_agent.py --driver "K. Reyes"
    python capture_agent.py --driver "K. Reyes" --dry-run
    python capture_agent.py --driver "K. Reyes" --verbose
"""

import argparse
import json
import logging
import re
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import mss
import numpy as np
import requests

try:
    import pytesseract
except ImportError:
    pytesseract = None

CONFIG_PATH = Path(__file__).parent / "config.json"

log = logging.getLogger("fwrl.capture")


def setup_logging(verbose):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def check_tesseract():
    if pytesseract is None:
        log.error("pytesseract is not installed. Run: pip install -r requirements.txt")
        sys.exit(1)
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        log.error("Tesseract OCR binary not found. Install it and ensure it is on PATH.")
        sys.exit(1)


def load_config():
    if not CONFIG_PATH.exists():
        log.error("config.json not found at %s", CONFIG_PATH)
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def validate_regions(regions):
    uncalibrated = []
    for name, r in regions.items():
        box = list(r.get("box", [0, 0, 0, 0]))
        if box == [0, 0, 0, 0]:
            uncalibrated.append(name)
    if uncalibrated:
        log.warning("Uncalibrated regions (run calibrate.py): %s", ", ".join(uncalibrated))


def grab_region(sct, box):
    x, y, w, h = box
    if w == 0 or h == 0:
        return None
    monitor = {"left": x, "top": y, "width": w, "height": h}
    shot = np.array(sct.grab(monitor))
    return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)


def frame_changed(prev_gray, new_img, threshold=2.0):
    new_gray = cv2.cvtColor(new_img, cv2.COLOR_BGR2GRAY)
    if prev_gray is None or prev_gray.shape != new_gray.shape:
        return True, new_gray
    diff = cv2.absdiff(prev_gray, new_gray)
    changed = float(np.mean(diff)) > threshold
    return changed, new_gray


def preprocess_for_ocr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def read_text(img, whitelist=""):
    processed = preprocess_for_ocr(img)
    config = "--psm 7"
    if whitelist:
        config = config + " -c tessedit_char_whitelist=" + whitelist
    text = pytesseract.image_to_string(processed, config=config)
    return text.strip()


def parse_position(raw_text):
    match = re.search(r"P?\s*(\d{1,2})", raw_text)
    if not match:
        return None
    value = int(match.group(1))
    if value < 1 or value > 20:
        return None
    return value


def parse_lap(raw_text):
    match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", raw_text)
    if match:
        return match.group(1) + "/" + match.group(2)
    return None


def check_pit(img, template, threshold):
    if template is None:
        return False
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_tpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    if gray_img.shape[0] < gray_tpl.shape[0] or gray_img.shape[1] < gray_tpl.shape[1]:
        return False
    result = cv2.matchTemplate(gray_img, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= threshold


class ConfirmedValue(object):
    def __init__(self, confirm_frames):
        self.confirm_frames = confirm_frames
        self.history = deque(maxlen=confirm_frames)
        self.confirmed = None

    def update(self, value):
        if value is None:
            self.history.clear()
            return self.confirmed
        self.history.append(value)
        if len(self.history) == self.confirm_frames and len(set(self.history)) == 1:
            self.confirmed = value
        return self.confirmed


def post_with_retry(endpoint, payload, attempts=3, base_delay=0.4, timeout=1.5):
    last_error = None
    attempt = 1
    while attempt <= attempts:
        try:
            resp = requests.post(endpoint, json=payload, timeout=timeout)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            last_error = e
            if attempt < attempts:
                time.sleep(base_delay * (2 ** (attempt - 1)))
            attempt = attempt + 1
    log.warning("Failed to reach bot endpoint after %d attempts: %s", attempts, last_error)
    return False


def run_capture_loop(cfg, driver, dry_run):
    regions = cfg["regions"]
    interval = cfg.get("capture_interval_seconds", 0.75)
    confirm_frames = cfg.get("confirm_frames", 3)
    endpoint = cfg.get("bot_endpoint")

    template_name = regions["pit_indicator"].get("template_image", "pit_icon_template.png")
    template_path = Path(__file__).parent / template_name
    pit_template = None
    if template_path.exists():
        pit_template = cv2.imread(str(template_path))
    if pit_template is None:
        log.warning("No pit icon template found at %s. Run calibrate.py first.", template_path)

    position_filter = ConfirmedValue(confirm_frames)
    lap_filter = ConfirmedValue(confirm_frames)
    last_pushed = {"position": None, "lap": None, "pit": None}
    prev_gray_position = None
    prev_gray_lap = None

    log.info("Capturing for driver '%s'. Press Ctrl+C to stop.", driver)
    consecutive_failures = 0

    sct = mss.mss()
    try:
        while True:
            try:
                pos_img = grab_region(sct, regions["position"]["box"])
                lap_img = grab_region(sct, regions["lap"]["box"])
                pit_img = grab_region(sct, regions["pit_indicator"]["box"])

                position = None
                lap = None
                in_pit = False

                if pos_img is not None:
                    changed, prev_gray_position = frame_changed(prev_gray_position, pos_img)
                    if changed:
                        raw = read_text(pos_img, regions["position"].get("whitelist", ""))
                        position = parse_position(raw)
                        log.debug("position OCR raw=%r parsed=%s", raw, position)
                    else:
                        position = position_filter.confirmed

                if lap_img is not None:
                    changed, prev_gray_lap = frame_changed(prev_gray_lap, lap_img)
                    if changed:
                        raw = read_text(lap_img, regions["lap"].get("whitelist", ""))
                        lap = parse_lap(raw)
                        log.debug("lap OCR raw=%r parsed=%s", raw, lap)
                    else:
                        lap = lap_filter.confirmed

                if pit_img is not None:
                    in_pit = check_pit(pit_img, pit_template, regions["pit_indicator"].get("match_threshold", 0.8))

                confirmed_position = position_filter.update(position)
                confirmed_lap = lap_filter.update(lap)

                update = {}
                if confirmed_position is not None and confirmed_position != last_pushed["position"]:
                    update["position"] = confirmed_position
                if confirmed_lap is not None and confirmed_lap != last_pushed["lap"]:
                    update["lap"] = confirmed_lap
                if in_pit != last_pushed["pit"]:
                    update["pit"] = in_pit

                if update:
                    payload = {"driver": driver}
                    payload.update(update)
                    if dry_run:
                        log.info("READ: %s", payload)
                    else:
                        ok = post_with_retry(endpoint, payload)
                        if ok:
                            log.info("SENT: %s", payload)
                            consecutive_failures = 0
                        else:
                            consecutive_failures = consecutive_failures + 1
                            if consecutive_failures == 5:
                                log.error("5 consecutive failed posts -- is bot.py running?")
                    last_pushed["position"] = update.get("position", last_pushed["position"])
                    last_pushed["lap"] = update.get("lap", last_pushed["lap"])
                    last_pushed["pit"] = update.get("pit", last_pushed["pit"])

                time.sleep(interval)
            except KeyboardInterrupt:
                log.info("Stopped.")
                break
            except Exception:
                log.exception("Unexpected error in capture loop -- continuing.")
                time.sleep(interval)
    finally:
        sct.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--driver", required=True, help="Driver name this capture session tracks.")
    parser.add_argument("--dry-run", action="store_true", help="Print readings instead of posting to the bot.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    setup_logging(args.verbose)
    check_tesseract()
    cfg = load_config()
    validate_regions(cfg["regions"])
    run_capture_loop(cfg, args.driver, args.dry_run)


if __name__ == "__main__":
    main()
