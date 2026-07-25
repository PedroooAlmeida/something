"""On-device OCR via Apple Vision. Free, local, ~25-40ms in fast mode."""
import io

import Vision
from Foundation import NSData


def ocr(img, fast=True) -> str:
    """OCR a PIL image; returns text lines top-to-bottom."""
    if img is None:
        return ""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(
        Vision.VNRequestTextRecognitionLevelFast if fast
        else Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)   # code and errors, not prose
    ok, _err = handler.performRequests_error_([req], None)
    if not ok or not req.results():
        return ""
    # Vision's origin is bottom-left: higher y = higher on screen.
    obs = sorted(req.results(),
                 key=lambda o: -o.boundingBox().origin.y)
    lines = []
    for o in obs:
        cands = o.topCandidates_(1)
        if cands and len(cands):
            lines.append(str(cands[0].string()))
    return "\n".join(lines)
