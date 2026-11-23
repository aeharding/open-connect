# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline integer gradient registration of the three visible Home icons."""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

p = Path(sys.argv[1])
files = sorted(p.glob("home-review-*.png"))
boxes = {
    "music": (145, 175, 285, 310),
    "communication": (420, 140, 580, 302),
    "navigation": (704, 232, 830, 350),
}


def gradient(file):
    a = np.asarray(Image.open(file).convert("L"), dtype=np.float32)
    y, x = np.gradient(a)
    return np.hypot(x, y)


ref = gradient(files[-1])
rows = []
for file in files[:-1]:
    current = gradient(file)
    row = {"file": file.name, "icons": {}}
    for name, (x0, y0, x1, y1) in boxes.items():
        template = ref[y0:y1, x0:x1].ravel()
        template = template - template.mean()
        norm = np.linalg.norm(template)
        best = (-1, 0, 0)
        for dy in range(-16, 17):
            for dx in range(-16, 17):
                candidate = current[y0 + dy : y1 + dy, x0 + dx : x1 + dx].ravel()
                candidate = candidate - candidate.mean()
                denom = np.linalg.norm(candidate) * norm
                score = float(np.dot(template, candidate) / denom) if denom else -1
                if score > best[0]:
                    best = (score, dx, dy)
        row["icons"][name] = {"correlation": best[0], "dx": best[1], "dy": best[2]}
    row["mean_gradient_correlation"] = sum(v["correlation"] for v in row["icons"].values()) / 3
    row["geometry_settled"] = all(v["dx"] == 0 and v["dy"] == 0 for v in row["icons"].values())
    rows.append(row)
result = {"reference": files[-1].name, "boxes_xyxy": boxes, "rows": rows}
(p / "home-registration.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
