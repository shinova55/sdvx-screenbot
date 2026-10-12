from dataclasses import dataclass
import cv2
import numpy as np

LANES = ["BT-A", "BT-B", "BT-C", "BT-D", "FX-L", "FX-R"]


def rectify(frame, cfg):
    w, h = cfg["size"]
    source = np.float32(cfg["corners"])
    target = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
    return cv2.warpPerspective(frame, cv2.getPerspectiveTransform(source, target), (w, h))


def propose_judgment(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 70, 160)
    h, w = gray.shape
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=w*.55, maxLineGap=15)
    candidates = [] if lines is None else [int((y1+y2)/2) for x1,y1,x2,y2 in lines.reshape(-1,4)
                                           if abs(y1-y2) < 4 and h*.55 < y1 < h*.98]
    return max(candidates) if candidates else None


def mask_hsv(frame, ranges):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = np.zeros(frame.shape[:2], np.uint8)
    for low, high in ranges:
        mask |= cv2.inRange(hsv, np.uint8(low), np.uint8(high))
    return mask


@dataclass
class Detection:
    lane: int
    top: float
    bottom: float
    hold: bool


class Detector:
    def __init__(self, cfg):
        self.cfg = cfg

    def detect(self, frame):
        out = []
        h, w = frame.shape[:2]
        for lane, (left, right) in enumerate(self.cfg["lanes"]):
            group = "bt" if lane < 4 else "fx"
            x1, x2 = int(left*w), int(right*w)
            mask = mask_hsv(frame[:, x1:x2], self.cfg["colors"][group])
            # Require horizontal occupancy; vertical rails and sparse effects are rejected.
            occupied = (mask > 0).mean(axis=1) >= self.cfg["occupancy"]
            changes = np.diff(np.r_[False, occupied, False].astype(int))
            for top, end in zip(np.where(changes == 1)[0], np.where(changes == -1)[0]):
                height = end-top
                if height >= self.cfg["min_height"]:
                    out.append(Detection(lane, float(top), float(end-1), height >= self.cfg["hold_height"]))
        return out

    def lasers(self, frame, judge):
        result = []
        strip = frame[max(0, int(judge)-8):int(judge)+1]
        for side in ("laser_l", "laser_r"):
            mask = mask_hsv(strip, self.cfg["colors"][side])
            count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
            valid = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= 12
                     and stats[i, cv2.CC_STAT_WIDTH] < frame.shape[1]*.15]
            result.append(float(centers[valid[0],0]/(frame.shape[1]-1)) if len(valid) == 1 else None)
        return result
