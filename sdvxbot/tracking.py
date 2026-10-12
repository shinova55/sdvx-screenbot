from dataclasses import dataclass


@dataclass
class Track:
    id: int
    lane: int
    top: float
    bottom: float
    hold: bool
    last: float
    velocity: float = 0
    hits: int = 1
    fired: bool = False
    release: float = 0


class Tracker:
    def __init__(self, gate=35, ttl=.10):
        self.gate, self.ttl = gate, ttl
        self.tracks = []
        self.sequence = 0

    def update(self, detections, now, height):
        self.tracks = [t for t in self.tracks if now-t.last <= self.ttl]
        pairs = []
        for t in self.tracks:
            dt = now-t.last
            for i, d in enumerate(detections):
                if d.lane == t.lane:
                    # The tail remains observable after a long note's head clips offscreen.
                    edge_old, edge_new = (t.top, d.top) if t.hold and t.top > 0 else (t.bottom, d.bottom)
                    error = abs(edge_new-(edge_old+t.velocity*dt))
                    if error < self.gate:
                        pairs.append((error, t.id, i, edge_old, edge_new))
        used_t, used_d = set(), set()
        for _, tid, i, old, new in sorted(pairs):
            if tid in used_t or i in used_d:
                continue
            t = next(t for t in self.tracks if t.id == tid)
            d = detections[i]
            dt = now-t.last
            if dt > 0:
                v = (new-old)/dt
                if 5 < v < 6000:
                    t.velocity = v if t.hits == 1 else .65*t.velocity+.35*v
            t.top, t.bottom, t.last = d.top, d.bottom, now
            t.hold |= d.hold
            t.hits += 1
            used_t.add(tid)
            used_d.add(i)
        for i, d in enumerate(detections):
            if i not in used_d:
                self.sequence += 1
                self.tracks.append(Track(self.sequence, d.lane, d.top, d.bottom, d.hold, now))
        return self.tracks


class Engine:
    def __init__(self, cfg, controller):
        self.cfg, self.controller = cfg, controller
        self.tracker = Tracker(ttl=cfg["tracking_ttl"])
        self.active = {}
        self.laser_previous = [None, None]
        self.laser_values = [.5, .5]
        if controller.client and cfg["laser"]["enabled"]:
            states = {row[0]: row[1] for row in controller.client.call("analogs","read")}
            self.laser_values = [states[n] for n in cfg["analogs"]]
        self.last = None

    def step(self, detections, lasers, now, capture_time=None):
        c = self.cfg
        if self.last is not None and now-self.last > c["max_frame_gap"]:
            self.controller.reset()
            self.tracker = Tracker(ttl=c["tracking_ttl"])
            self.active.clear()
            for name in c["analogs"]:
                self.controller.release("analogs", name)
            self.laser_previous = [None, None]
        self.last = now
        tracks = self.tracker.update(detections, now if capture_time is None else capture_time, c["geometry"]["size"][1])
        judge = c["geometry"]["judgment_y"]
        for t in tracks:
            if t.hits < 3 or t.velocity <= 5:
                continue
            head = t.bottom + t.velocity*(now-t.last)
            tail = t.top + t.velocity*(now-t.last)
            eta = (judge-head)/t.velocity-c["latency_ms"]/1000
            if not t.fired and -.035 <= eta <= 0 and now-t.last < .04:
                t.fired = True
                duration = max(c["pulse_ms"]/1000, (judge-tail)/t.velocity-c["latency_ms"]/1000) if t.hold else c["pulse_ms"]/1000
                t.release = now + min(duration, c["max_hold_seconds"])
                self.active[t.id] = (t.lane, t.release, now+c["max_hold_seconds"])
            if t.fired and t.id in self.active and t.hold and now-t.last < .04:
                lane, _, cap = self.active[t.id]
                self.active[t.id] = (lane, min(cap, now+max(0, (judge-tail)/t.velocity-c["latency_ms"]/1000)), cap)
        visible = {t.id for t in tracks}
        self.active = {tid: v for tid, v in self.active.items() if v[1] > now and tid in visible}
        down = {v[0] for v in self.active.values()}
        self.controller.write("buttons", {n: int(i in down) for i,n in enumerate(c["buttons"])}, now)
        if c["laser"]["enabled"]:
            for i, x in enumerate(lasers):
                prev = self.laser_previous[i]
                if x is not None and prev is not None:
                    delta = x-prev
                    # No slam guessing or absolute screen-position to knob mapping.
                    if abs(delta) <= c["laser"]["max_step"]:
                        delta *= c["laser"]["gain"][i]
                        self.laser_values[i] = (self.laser_values[i]+delta) % 1.0
                        self.controller.write("analogs", {c["analogs"][i]: self.laser_values[i]}, now)
                    else:
                        self.controller.release("analogs", c["analogs"][i])
                        x = None
                elif x is None:
                    self.controller.release("analogs", c["analogs"][i])
                elif prev is None and self.controller.client:
                    states = {row[0]: row[1] for row in self.controller.client.call("analogs","read")}
                    self.laser_values[i] = states[c["analogs"][i]]
                self.laser_previous[i] = x
