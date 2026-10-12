import json
import math


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        c = json.load(f)
    def positive(value, label):
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid {label}")
    for key in ("fps", "pulse_ms", "tracking_ttl", "max_frame_gap", "max_hold_seconds"):
        positive(c[key], key)
    if not 10 <= c["fps"] <= 500 or not 0 <= c["latency_ms"] <= 300:
        raise ValueError("fps or latency outside supported bounds")
    for key in ("width", "height"):
        positive(c["roi"][key], key)
    w, h = c["geometry"]["size"]
    if not 64 <= w <= 4096 or not 64 <= h <= 4096:
        raise ValueError("Rectified size out of bounds")
    if not 0 < c["geometry"]["judgment_y"] < h:
        raise ValueError("Judgment line outside image")
    if len(c["geometry"]["corners"]) != 4:
        raise ValueError("Four ordered corners required")
    if len(c["vision"]["lanes"]) != 6 or any(not 0 <= a < b <= 1 for a,b in c["vision"]["lanes"]):
        raise ValueError("Six lane intervals required")
    if len(c["buttons"]) != 6 or len(set(c["buttons"])) != 6 or len(c["analogs"]) != 2:
        raise ValueError("Expected six unique button names and two analog names")
    if not 0 < c["api"]["timeout"] <= 2:
        raise ValueError("API timeout must be in (0,2]")
    if not 0 < c["vision"]["occupancy"] <= 1:
        raise ValueError("Invalid occupancy")
    if not 0 < c["laser"]["max_step"] <= .1:
        raise ValueError("Conservative laser max_step must be in (0,.1]")
    return c
