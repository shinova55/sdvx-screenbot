import json
from pathlib import Path
import cv2
import numpy as np
from .api import Controller
from .vision import Detector
from .tracking import Engine

# lane, expected head crossing time, hold duration. Original synthetic fixture.
NOTES = [(0,1.0,0), (1,1.35,0), (2,1.7,0), (3,2.05,0),
         (4,2.4,0), (5,2.75,0), (0,3.2,.65), (5,4.1,.8),
         (1,5.2,0), (2,5.2,0), (1,5.45,0)]


def frame_at(now, cfg):
    w,h = cfg["geometry"]["size"]
    image = np.zeros((h,w,3), np.uint8)
    judge = cfg["geometry"]["judgment_y"]
    cv2.line(image, (0,int(judge)), (w-1,int(judge)), (70,70,70), 1)
    for lane, hit, duration in NOTES:
        head = judge+(now-hit)*240
        tail = head-max(7, duration*240)
        left,right = cfg["vision"]["lanes"][lane]
        if head >= 0 and tail < h:
            color = (245,245,245) if lane < 4 else (0,160,255)
            cv2.rectangle(image, (int(left*w),max(0,int(tail))), (int(right*w)-1,min(h-1,int(head))), color, -1)
    return image


def run(cfg, output, show=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    detector, control = Detector(cfg["vision"]), Controller()
    engine = Engine(cfg, control)
    for index in range(720):
        now = index/120
        frame = frame_at(now,cfg)
        engine.step(detector.detect(frame), [None,None], now)
        if index == 370:
            cv2.imwrite(str(output/"demo-frame.png"),frame)
        if show:
            cv2.imshow("Synthetic offline demo - Esc closes",frame)
            if cv2.waitKey(8) & 255 == 27:
                break
    control.reset(terminal=True)
    cv2.destroyAllWindows()
    (output/"events.json").write_text(json.dumps(control.events,indent=2),encoding="utf-8")
    presses = [e for e in control.events if e["module"] == "buttons" and e["value"] == 1]
    summary = dict(expected_presses=len(NOTES), detected_presses=len(presses), dry_run=True)
    (output/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary))
    return control.events
