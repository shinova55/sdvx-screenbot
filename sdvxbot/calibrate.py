"""OpenCV assisted geometry calibration, explicit human confirmation."""
import json
import cv2
import numpy as np
from .vision import rectify, propose_judgment


def calibrate(cfg, output, image=None):
    if image:
        raw = cv2.imread(image)
        if raw is None:
            raise ValueError("Could not open calibration image")
    else:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            raw = np.asarray(sct.grab(monitor))[:,:,:3].copy()
        x,y,w,h = cv2.selectROI("Select playfield ROI; Enter accepts", raw, False)
        cv2.destroyAllWindows()
        if not w or not h:
            raise ValueError("ROI cancelled")
        cfg["roi"] = dict(left=monitor["left"]+x, top=monitor["top"]+y, width=w, height=h)
        raw = raw[y:y+h, x:x+w]
    points = []
    title = "Click top-left, top-right, bottom-right, bottom-left; Enter; Esc cancels"
    def click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([x,y])
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()
    cv2.namedWindow(title)
    cv2.setMouseCallback(title, click)
    while True:
        canvas = raw.copy()
        for p in points:
            cv2.circle(canvas, tuple(p), 5, (0,255,0), -1)
        cv2.imshow(title, canvas)
        key = cv2.waitKey(20) & 255
        if key == 27:
            cv2.destroyAllWindows()
            raise ValueError("Calibration cancelled")
        if key == 13 and len(points) == 4:
            break
    contour = np.int32(points)
    if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 100:
        raise ValueError("Corners must form a convex quadrilateral in the requested order")
    cfg["geometry"]["corners"] = points
    frame = rectify(raw, cfg["geometry"])
    h,w = frame.shape[:2]
    judge = propose_judgment(frame) or int(h*.87)
    # Five BT boundaries also define two FX spans (0..2 and 2..4).
    boundaries = [0, w//4, w//2, 3*w//4, w-1]
    title2 = "Adjust judgment and BT boundaries; Enter saves; Esc cancels"
    cv2.destroyAllWindows()
    cv2.namedWindow(title2)
    cv2.createTrackbar("judgment", title2, judge, h-1, lambda _: None)
    for i,x in enumerate(boundaries):
        cv2.createTrackbar(f"edge{i}", title2, x, w-1, lambda _: None)
    while True:
        judge = cv2.getTrackbarPos("judgment", title2)
        edges = [cv2.getTrackbarPos(f"edge{i}", title2) for i in range(5)]
        canvas = frame.copy()
        cv2.line(canvas, (0,judge), (w-1,judge), (0,255,0), 2)
        for x in edges:
            cv2.line(canvas, (x,0), (x,h-1), (255,100,0), 1)
        cv2.imshow(title2, canvas)
        key = cv2.waitKey(20) & 255
        if key == 27:
            cv2.destroyAllWindows()
            raise ValueError("Calibration cancelled")
        if key == 13 and all(b-a > 8 for a,b in zip(edges,edges[1:])) and 0 < judge < h:
            break
    def inset(a,b):
        margin = (b-a)*.12
        return [(a+margin)/w, (b-margin)/w]
    cfg["vision"]["lanes"] = [inset(edges[i],edges[i+1]) for i in range(4)] + [inset(edges[0],edges[2]), inset(edges[2],edges[4])]
    cfg["geometry"].update(judgment_y=judge, calibrated=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    cv2.imwrite(str(output)+".png", canvas)
    cv2.destroyAllWindows()
