# SPDX-License-Identifier: AGPL-3.0-or-later


def main():
    import json
    import subprocess
    import sys
    from pathlib import Path

    p = Path(sys.argv[1])
    start = float(sys.argv[2])
    step = float(sys.argv[3])
    r = json.loads((p / "camera-result.json").read_text())
    pts = [float(row["best_effort_timestamp_time"]) for row in r["ffprobe"]["frames"]]
    indices = sorted(
        set(min(range(len(pts)), key=lambda i: abs(pts[i] - (start + n * step))) for n in range(16))
    )
    select = "+".join("eq(n\\," + str(i) + ")" for i in indices)
    filters = (
        "select="
        + select
        + ",scale=320:180,pad=320:205:0:0:black,drawtext=text='PTS %{pts}':fontcolor=white:fontsize=16:x=5:y=183,tile=4x4"
    )
    output = p / ("contact-" + str(start) + ".png")
    r = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(p / "camera.mkv"),
            "-vf",
            filters,
            "-frames:v",
            "1",
            str(output),
        ],
        capture_output=True,
        timeout=25,
    )
    if r.returncode:
        raise SystemExit(r.stderr.decode())
    output.with_suffix(".json").write_text(
        json.dumps({"indices": indices, "pts_s": [pts[i] for i in indices]}, indent=2) + "\n"
    )
    print(output)


if __name__ == "__main__":
    main()
