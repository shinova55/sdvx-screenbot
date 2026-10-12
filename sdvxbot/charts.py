"""Comparison only. No functions in this module send game inputs."""
import csv
import math
import re
from pathlib import Path
import numpy as np
from .vision import LANES


def parse_ksh(path):
    lines = [s.strip() for s in Path(path).read_text(encoding="utf-8-sig").splitlines()
             if s.strip() and not s.lstrip().startswith("//")]
    if "--" not in lines:
        raise ValueError("Missing KSH header delimiter")
    split = lines.index("--")
    header = dict(s.split("=",1) for s in lines[:split] if "=" in s)
    tempo = header.get("t", "120")
    bpm = float(tempo) if re.fullmatch(r"\d+(\.\d+)?",tempo) else None
    signature = header.get("beat","4/4")
    now = float(header.get("o",0))/1000
    events, active, warnings = [], {}, set()
    body = re.split(r"(?m)^--$", "\n".join(lines[split+1:]))
    def emit(lane, start, end):
        events.append(dict(lane=LANES[lane], time=start, duration=end-start))
    for block in body:
        entries = [s for s in block.splitlines() if s]
        rows = [s for s in entries if "|" in s and "=" not in s]
        if not rows:
            continue
        before_row = True
        for s in entries:
            if "|" in s and "=" not in s:
                before_row = False
            elif s.startswith("beat="):
                if not before_row:
                    raise ValueError("Mid-measure beat changes unsupported in comparison parser")
                signature = s.split("=",1)[1]
        n,d = map(int,signature.split("/"))
        if n <= 0 or d <= 0:
            raise ValueError("Invalid time signature")
        beats_per_row = n*4/d/len(rows)
        for s in entries:
            if "=" in s:
                key,value = s.split("=",1)
                if key == "t":
                    bpm = float(value)
                elif key in {"stop", "scroll_speed", "rotation_deg"}:
                    raise ValueError(f"Unsupported timing/visual directive: {key}")
                elif key != "beat":
                    warnings.add(f"Ignored body option: {key}")
                continue
            if s.startswith("#"):
                warnings.add("Effect definitions ignored")
                continue
            match = re.fullmatch(r"([012]{4})\|([^|]{2})\|([^|]{2})(.*)", s)
            if not match:
                raise ValueError(f"Unsupported KSH row: {s}")
            if bpm is None or not math.isfinite(bpm) or bpm <= 0:
                raise ValueError("A positive numeric BPM is required before notes")
            bt,fx,laser,suffix = match.groups()
            if laser != "--":
                warnings.add("Laser coordinates/interpolation not decoded")
            if suffix:
                warnings.add("Spin/tilt suffix ignored")
            for lane, symbol in enumerate(bt+fx):
                hold = symbol == "2" if lane < 4 else symbol not in "02"
                chip = symbol == "1" if lane < 4 else symbol == "2"
                if lane in active and not hold:
                    emit(lane,active.pop(lane),now)
                if hold and lane not in active:
                    active[lane] = now
                if chip:
                    emit(lane,now,now)
            now += beats_per_row*60/bpm
    for lane,start in active.items():
        emit(lane,start,now)
    return dict(format="ksh-subset", events=sorted(events,key=lambda e:(e["time"],e["lane"])), warnings=sorted(warnings))


def parse_vox(path):
    """Lossless section/token reader, deliberately no undocumented timing conversion."""
    sections, current = {}, None
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(),1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "#END":
            current = None
        elif line.startswith("#"):
            current = line[1:]
            sections.setdefault(current,[])
        elif current:
            tokens = line.split()
            row = dict(line=number, fields=tokens)
            if re.fullmatch(r"\d+,\d+,\d+", tokens[0]):
                row["raw_position"] = list(map(int,tokens[0].split(",")))
            sections[current].append(row)
        else:
            raise ValueError(f"VOX data outside a section at line {number}")
    if "FORMAT VERSION" not in sections:
        raise ValueError("Expected text SDVX VOX sections; binary VOX is unsupported")
    return dict(format="vox-structural-only", sections=sections, warnings=[
        "VOX versions, lane mapping, tick resolution, hold/laser flags and time conversion are UNVERIFIED; raw fields only."])


def fit_sync(path):
    """CSV of manually matched chart_seconds,observed_seconds -> affine fit."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    x = np.array([float(r["chart_seconds"]) for r in rows])
    y = np.array([float(r["observed_seconds"]) for r in rows])
    if len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(y).all() or np.ptp(x) < 1:
        raise ValueError("Need >=3 finite matched pairs spanning >=1 second")
    a,b = np.polyfit(x,y,1)
    residual = y-(a*x+b)
    return dict(clock_scale=float(a), offset_seconds=float(b),
                residual_rms_ms=float(np.sqrt(np.mean(residual**2))*1000),
                residual_max_ms=float(np.max(np.abs(residual))*1000), count=len(x),
                note="observed = scale * chart + offset; this does not measure input latency")
