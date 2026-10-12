import json
import logging
import threading
import time
from pathlib import Path
import cv2
import numpy as np
from .api import APIError
from .vision import Detector, rectify
from .tracking import Engine

LOG = logging.getLogger(__name__)


def run(cfg, controller, seconds, output, preview=True):
    import mss
    from pynput import keyboard
    stop = threading.Event()
    heartbeat = [time.monotonic()]
    reset_errors = []
    def panic(reason):
        if stop.is_set():
            return
        LOG.warning("Stopping: %s", reason)
        stop.set()
        try:
            controller.reset(terminal=True)
        except APIError as exc:
            reset_errors.append(str(exc))
            LOG.error("%s", exc)
    try:
        key = getattr(keyboard.Key,cfg["panic_key"])
    except AttributeError as exc:
        raise ValueError("panic_key must name a pynput special key, e.g. f12") from exc
    detector, engine = Detector(cfg["vision"]), Engine(cfg,controller)
    listener = keyboard.Listener(on_press=lambda pressed: panic("panic key") if pressed == key else None)
    listener.start()
    listener.wait()
    def watchdog():
        while not stop.wait(.025):
            if not listener.is_alive():
                panic("panic key listener stopped")
            if time.monotonic()-heartbeat[0] > cfg["max_frame_gap"]:
                panic("capture/processing watchdog expired")
    thread = threading.Thread(target=watchdog,daemon=True)
    started = time.monotonic()
    previous, last_change = None, started
    thread.start()
    try:
        with mss.mss() as sct:
            while not stop.is_set() and time.monotonic()-started < seconds:
                before = time.monotonic()
                raw = np.asarray(sct.grab(cfg["roi"]))[:,:,:3].copy()
                captured = (before+time.monotonic())/2
                frame = rectify(raw,cfg["geometry"])
                # Frozen capture must not continue a held input indefinitely.
                if previous is None or not np.array_equal(frame,previous):
                    last_change = captured
                elif captured-last_change > .5:
                    panic("unchanged capture for 0.5 seconds")
                    break
                previous = frame
                detections = detector.detect(frame)
                lasers = detector.lasers(frame,cfg["geometry"]["judgment_y"])
                engine.step(detections,lasers,time.monotonic()-started,capture_time=captured-started)
                heartbeat[0] = time.monotonic()
                if preview:
                    judge = int(cfg["geometry"]["judgment_y"])
                    cv2.line(frame,(0,judge),(frame.shape[1]-1,judge),(0,255,0),1)
                    for d in detections:
                        a,b = cfg["vision"]["lanes"][d.lane]
                        cv2.rectangle(frame,(int(a*frame.shape[1]),int(d.top)),(int(b*frame.shape[1]),int(d.bottom)),(0,0,255),1)
                    cv2.imshow("Screenbot preview - F12 panic / Esc",frame)
                    if cv2.waitKey(1) & 255 == 27:
                        panic("preview Escape")
                stop.wait(max(0,1/cfg["fps"]-(time.monotonic()-before)))
    finally:
        panic("run ended")
        thread.join(timeout=3)
        listener.stop()
        cv2.destroyAllWindows()
        Path(output).write_text(json.dumps(controller.events,indent=2),encoding="utf-8")
    if reset_errors:
        raise APIError(reset_errors[0])
