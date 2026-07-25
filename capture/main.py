"""Gordon live watcher: the 10Hz perception loop.

Layers per capture.md — focus gate -> grab+diff -> OCR changed region ->
state machine -> local triggers -> JSON events in roast_events/.
"""
import argparse
import sys
import time

import numpy as np
import Quartz

from . import config as config_mod
from .emitter import Emitter
from .machine import Machine
from .ocr import ocr
from .screen import Grabber, frontmost
from .textutil import clean_ocr, detect_model
from .triggers import TriggerEngine

GRID_ROWS, GRID_COLS = 6, 8
CELL_H, CELL_W = 192 // GRID_ROWS, 320 // GRID_COLS


class Watcher:
    def __init__(self, cfg, debug=False):
        self.cfg = cfg
        self.debug = debug
        self.grabber = Grabber()
        self.emitter = Emitter(cfg.events_dir)
        self.triggers = TriggerEngine(cfg, self.emitter, debug=debug)
        self.machines = {}          # app name -> Machine
        self.prev_gray = None
        self.prev_app = None
        self.last_ocr_ts = 0.0
        self.pending_ocr = False   # composer changed but OCR was rate-limited
        self.cur_app = ""
        self.cur_title = ""
        self.model_by_app = {}     # app name -> last model id seen in its picker

    # -- helpers ------------------------------------------------------------

    def machine_for(self, app):
        if app not in self.machines:
            self.machines[app] = Machine(
                self.cfg, read_conversation=self.read_conversation)
        return self.machines[app]

    def read_conversation(self):
        """OCR the conversation band of the current frame (submit/done ticks only)."""
        return ocr(self.grabber.crop(self.cfg.conversation_band), fast=True)

    # -- loop ---------------------------------------------------------------

    def run(self):
        interval = 1.0 / self.cfg.fps
        print(f"[gordon] watching apps: {', '.join(self.cfg.allowlist)}")
        print(f"[gordon] events -> {self.cfg.events_dir}/  (ctrl-c to stop)")
        while True:
            start = time.time()
            try:
                self.tick(start)
            except Exception as e:   # transient CGWindow / grab weirdness
                if self.debug:
                    print(f"[gordon:err] {type(e).__name__}: {e}")
                self.prev_gray = None
            time.sleep(max(0.0, interval - (time.time() - start)))

    def tick(self, now):
        app, bounds, title = frontmost()
        if app not in self.cfg.allowlist or bounds is None:
            # Non-allowlisted app: no capture at all. Absence, not a filter.
            self.prev_gray = None
            self.prev_app = None
            time.sleep(0.4)
            return

        self.cur_app, self.cur_title = app, title
        gray = self.grabber.grab(bounds)

        if app != self.prev_app or self.prev_gray is None \
                or gray.shape != self.prev_gray.shape:
            self.prev_app = app
            self.prev_gray = gray
            return

        diff = np.abs(gray - self.prev_gray)
        self.prev_gray = gray
        cells = diff[:GRID_ROWS * CELL_H, :GRID_COLS * CELL_W] \
            .reshape(GRID_ROWS, CELL_H, GRID_COLS, CELL_W).mean(axis=(1, 3))
        changed = cells > self.cfg.cell_diff_threshold
        machine = self.machine_for(app)

        scrolled = False
        conv_changed = False
        if changed.any():
            row_frac = (np.arange(GRID_ROWS) + 0.5) / GRID_ROWS
            composer_rows = row_frac >= self.cfg.composer_y0
            conv_rows = (row_frac >= 0.10) & ~composer_rows
            scrolled = changed.mean() >= self.cfg.scroll_cell_fraction
            conv_changed = bool(changed[conv_rows].any())
            if bool(changed[composer_rows].any()):
                # Never drop a composer change (it may be the submit-empty
                # frame) — defer it past the rate limit instead.
                self.pending_ocr = True

        composer_text = None
        if self.pending_ocr and now - self.last_ocr_ts >= self.cfg.ocr_min_interval_s:
            self.pending_ocr = False
            self.last_ocr_ts = now
            # Accurate mode: composer text feeds the trigger rules, garbled
            # chars would break vagueness/affirmation matching. ~120ms, small crop.
            raw = ocr(self.grabber.crop(self.cfg.composer_band), fast=False)
            composer_text = clean_ocr(raw, self.cfg.placeholders)
            model = detect_model(raw)   # picker label is chrome; scan pre-clean
            if model:
                self.model_by_app[app] = model
            if self.debug:
                print(f"[gordon:ocr] {app}: {composer_text[:100]!r}")

        self.emitter.selected_model = self.model_by_app.get(app, "unknown")
        for sem in machine.feed(now, composer_text=composer_text,
                                conv_changed=conv_changed, scrolled=scrolled):
            self.dispatch(sem)

    def dispatch(self, sem):
        if self.debug:
            print(f"[gordon:sem] {sem.kind} {sem.data}")
        self.triggers.process(sem, app=self.cur_app, window_title=self.cur_title)


def check_permission():
    """Screen Recording permission, without which mss returns wallpaper-only
    frames and the watcher silently sees nothing."""
    if Quartz.CGPreflightScreenCaptureAccess():
        return True
    Quartz.CGRequestScreenCaptureAccess()
    print("[gordon] Screen Recording permission missing.")
    print("         System Settings > Privacy & Security > Screen Recording")
    print("         -> enable this terminal, then restart the terminal and rerun.")
    return False


def main():
    ap = argparse.ArgumentParser(description="Gordon live roast watcher")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--debug", action="store_true",
                    help="print state transitions and gate decisions")
    ap.add_argument("--submit-only", action="store_true",
                    help="demo/privacy mode: fire only on submissions")
    args = ap.parse_args()
    if not check_permission():
        sys.exit(1)
    cfg = config_mod.load(args.config)
    if args.submit_only:
        cfg.submit_only = True
    try:
        Watcher(cfg, debug=args.debug).run()
    except KeyboardInterrupt:
        print("\n[gordon] stopped")


if __name__ == "__main__":
    main()
