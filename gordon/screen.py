"""macOS screen access: frontmost app, window bounds, frame grab."""
import mss
import numpy as np
from AppKit import NSWorkspace
from PIL import Image
import Quartz


def frontmost():
    """Return (app_name, bounds_dict, window_title) of the frontmost window."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return None, None, ""
    name = str(app.localizedName())
    pid = app.processIdentifier()
    wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly
        | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID) or []
    for w in wins:
        if w.get("kCGWindowOwnerPID") == pid and w.get("kCGWindowLayer", 1) == 0:
            b = w.get("kCGWindowBounds", {})
            if b.get("Width", 0) < 200 or b.get("Height", 0) < 200:
                continue   # tooltips, popovers
            bounds = {"left": int(b["X"]), "top": int(b["Y"]),
                      "width": int(b["Width"]), "height": int(b["Height"])}
            return name, bounds, str(w.get("kCGWindowName", "") or "")
    return name, None, ""


class Grabber:
    """Window-region capture. Frames live in RAM only, never written to disk."""

    def __init__(self):
        self.sct = mss.mss()
        self.shot = None   # last raw grab, for OCR crops

    def grab(self, bounds) -> np.ndarray:
        """Grab window region; return small grayscale array (~192x320) for diffing."""
        self.shot = self.sct.grab(bounds)
        raw = np.frombuffer(self.shot.bgra, dtype=np.uint8)
        raw = raw.reshape(self.shot.height, self.shot.width, 4)
        # Green channel as luma proxy; stride-subsample, then exact-resize small.
        sy = max(1, self.shot.height // 384)
        sx = max(1, self.shot.width // 640)
        g = raw[::sy, ::sx, 1]
        img = Image.fromarray(g).resize((320, 192), Image.BILINEAR)
        return np.asarray(img, dtype=np.int16)

    def crop(self, band) -> Image.Image:
        """Crop a (x0, y0, x1, y1) fractional band from the last grabbed frame."""
        if self.shot is None:
            return None
        img = Image.frombytes("RGB", self.shot.size, self.shot.rgb)
        w, h = img.size
        x0, y0, x1, y1 = band
        return img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
