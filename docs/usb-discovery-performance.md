# Ordinary-USB discovery — dev.22 and dev.23 candidates

The first dev.23 receiver added ordinary-USB discovery work. Adaptive backoff in
`b386f803` reduced **130 → 34 immediate-empty reads in a 65 s host replay**.
The earlier **+2,048 KiB Opera PSS** difference against historical dev.22 did
**not reproduce against a fresh published-dev.22 control**: b386's median was
**164 KiB lower**. Its CPU medians were **+0.1865 and +0.2676 percentage points**
higher in the two primary windows, with overlapping run ranges.

These are bounded bench findings for [#184](https://github.com/aeharding/open-connect/issues/184)
and [#9](https://github.com/aeharding/open-connect/issues/9).
These historical measurements do not qualify final source, establish blanket
non-regression or imply owner acceptance of RAM overhead. See
[PR #179](https://github.com/aeharding/open-connect/pull/179) for separate native
functional evidence; the original missing-popup report remains tracked in
[#185](https://github.com/aeharding/open-connect/issues/185).

The [final baff018 resource append](#final-baff018-resource-measurements-november-26-2026)
adds predeclared primary and all-attempts groups without changing these historical blocks.

## Results and the changed reference

Each cell is a **median (minimum–maximum) of three per-boot values**. Blocks
remain separate; fresh22 does not replace or enlarge historical22.

| Metric | Historical dev.22, trials 2–4 | Original ed4 CI, trials 2–4 | Backoff b386 CI, trials 8–10 | Fresh published dev.22, trials 5–7 |
| --- | ---: | ---: | ---: | ---: |
| CPU 20–170 s, % | 29.2829 (29.0819–29.4169) | 29.8021 (29.6745–29.9940) | 29.3862 (29.3630–29.6771) | 29.1997 (29.0164–30.5324) |
| CPU 60–170 s, % | 13.1310 (13.0269–13.3682) | 13.1924 (13.1535–13.5894) | 13.0017 (12.4052–13.4547) | 12.7341 (12.6000–15.1673) |
| Post-window Opera PSS, KiB | 50,704 (50,216–52,532) | 53,144 (52,884–53,216) | 52,752 (50,776–52,892) | 52,916 (52,652–52,980) |
| Post-window Opera private, KiB | 50,260 (49,772–52,088) | 52,700 (52,440–52,772) | 52,308 (50,332–52,448) | 52,472 (52,208–52,536) |
| Own allocated tmpfs, KiB | 396 (396–396) | 396 (396–396) | 396 (396–396) | 396 (396–396) |

The original ed4 block exceeded historical22's 20–170 s CPU range; its median
was **+0.5192 pp**. Backoff reduced that median by **0.4159 pp** and Opera PSS
by **392 KiB**. Against historical22, b386 still has **+2,048 KiB PSS/private**.
Against fresh22, it has **−164 KiB PSS/private**, with own allocated files
unchanged. The fresh baseline itself is **2,212 KiB higher** than historical22.
This supports drift or confounding as a possibility; it does not identify a
cause, prove maps causation or establish an XHR leak. Whole-process snapshots
cannot isolate a JavaScript heap or first-use HTTP allocation.

The high-CPU fresh22 observation remains included. CPU ranges overlap between
b386 and fresh22; neither CPU parity nor a consistent causal regression is
established. The [per-run CSV](assets/performance/dev23-usb-discovery/runs.csv)
also retains minimum MemFree, ending available-RAM proxy and AnonPages. Different
memory counters can move in different directions; the Opera result is not a
whole-system or peak-RAM claim.

## Polling and I/O

The receiver originally retried empty offers every 500 ms for up to 65 s from a
connection trigger, including an ordinary drive with no installer offer.
Backoff keeps the immediate first read, then 500/1,000/2,000 ms capped retries,
reset by each new connection with its own 65 s deadline. The **130/34 counts
are host replay counts**, not measured native HTTP-request counts. Immediate
replies move the last read from 64.5 to 63.5 s; an offer first available in that
last second can miss the window.

Native loopback RX rates in uptime 50–110 s had medians **38.41 / 64.29 / 44.84
packets/s** for historical22 / ed4 / b386. Relative to historical22, backoff
removed **75.16% of ed4's excess rate**; residual traffic remained. Aggregate
traffic and global task creation support polling as a CPU contributor, but do
not identify requests, processes or all CPU/RAM costs. RX and TX are the same
loopback traffic and are not added together.

All b386 I/O observations remain in [io.csv](assets/performance/dev23-usb-discovery/io.csv).
The unexplained large persistent-partition burst belongs to **trial 8**:
**4,783 read / 553 written sectors**, **16,350 / 5,100 ms summed read/write
ticks**, in 20–170 s. Trial 10 has **610 / 186 sectors** and **130 / 870 ms**.
This corrects the inherited trial-10 label without changing historical receipts.
Disk ticks are not isolated elapsed boot delay. Navigation read volume was
**53,366 sectors = 26.0576 MiB** in every retained run; equal volume does not
prove equal bytes, cache state or memory use.

## Fixture, coverage and exclusions

One **74.00.324A NA/cmu150_NA** bench; each start followed approximately **30 s
ACC-off with B+ retained**. Blocks were acquired in order historical22 → ed4 →
CF7 → b386 → fresh22, with setup operations between them. Base and Wireless
were off; Android Auto, Pandora and SiriusXM were on; touchscreen Allow,
disclaimer Skip and CarPlay autoshow Factory were fixed. Saved raw values were
`base=0, wireless=0, service.android-auto=1, service.pandora=1,
service.siriusxm=1, touch=1, warning=1, carplay-autoshow=0`.
The workload was ordinary idle Mazda Home, without foreground projection.
Phone model/OS and all peripheral state were not fully inventoried; this is not
a matched projection, real-car, driving or long-parked workload.

The as-found Navigation setup was preserved. Closeout found matching content
hashes/sizes for the previously checked setup files and matching previously
inventoried metadata. A broader inventory included an additional hidden entry
outside the earlier scope; that alone is not evidence of creation or change.
Whole map contents were not hashed. Navigation roles come from each boot's
native mount receipt; the remaining USB source role is inferred from the
two-media fixture. SD letter ordering is not a role identity.

The finite local collector ran for **180 s**, with a **one-second minimum pause**
plus read/loop overhead, under a **190 s deadline**, without process discovery.
No UI or SSH work ran during the 225 s startup observation window. Collection
starts around 10–11 s; earlier RAM is unobserved. All 13 retained traces were
reparsed and checked against their saved traces for this publication.

- **Historical22 2/3/4, ed4 2/3/4, b386 8/9/10 and fresh22 5/6/7:** four separate n=3 blocks. No run was removed for a high value or I/O burst.
- **CF7 (dev23 trial 7):** separate n=1 diagnostic on ed4, with a flat 2,000 ms timer override, extra observer/held index and `String(fn)` inspection confounds. CPU was 28.7485% / 12.5615%; Opera PSS/private 50,656 / 50,212 KiB. It is not an adaptive-backoff CI qualification or an isolated RAM mechanism test.
- **Dev23 trial 5:** invalid edited-shared-runtime experiment; manifest publication refused and the endpoint failed. No valid CPU comparison.
- **Dev23 trial 6:** admission failed before instruments opened; no measured boot.
- **Dev22 trial 1:** camera-enumeration admission failed before instruments opened; no measured boot. Setup/install/restart operations are outside the measured blocks.

Previously reviewed Home frame estimates are retained for historical22, ed4,
CF7 and b386 only. Their midpoint medians for the three n=3 blocks were
**34.555 / 35.548 / 34.948 s**. Approximately **0.201 s frame spacing** and
uncalibrated camera origin, relay and sensor latency prevent a **0.1 s Home
parity** claim. Fresh22 has no new video scoring here; blank Home values are
unobserved, not zero. No accepted-input, helper-age-matched, JavaScript-heap,
whole-startup peak or stock-parity conclusion follows. Late helper snapshots
at different ages are not pooled with these post-window snapshots.
[#166 / PR #186](https://github.com/aeharding/open-connect/pull/186) is separate
from ordinary Opera RAM; this record makes no claim about later #167 results.

## Source and acquisition pins

The pins identify measured inputs, not qualification of a later final source.
Historical manifest provenance is retained as recorded; VERSION alone does not
bind it to a later tag or archive.

| Block | Source / artifact identity |
| --- | --- |
| Historical22 | Build receipt source `f4d473ad1aa6ed6a4b30979865e6a64567ff73d1`; payload manifest SHA-256 `0f91527fb97a9905a0b5a5ff66b9e3c1843c9ab07c873c9f292f6ae6b6b5f924`. No archive identity inferred. |
| Fresh22 | Published v0.3.0-dev.22 tag `a5d0ba8070caed4c0bf26266beb517aa30f65d0d`; ZIP SHA-256 `06785a1db57b614c22044c9deb829a8cdb2908343d3754f7a9f1227b5eeb2bb4`; same payload manifest as above. |
| Original ed4 | Source `ed4f750ade78a588e55e0b872e1080b22d747f7f`, [CI 45739503889](https://github.com/aeharding/open-connect/actions/runs/45739503889); ZIP `1a2d11a6e6fa9a0748a5de6165638f9034fba1eee6f970cf038047ae8f59d94a`; manifest `2bd3b5f2beb707d8ee104a6750886097d373662342255e38677c6c551b411a10`. |
| Backoff b386 | Source `b386f8036ef57f44f1142147339cae30c21a1a63`, [CI 45747411076](https://github.com/aeharding/open-connect/actions/runs/45747411076); ZIP `c0e32e66fb7f9fbe086f443c88d3b7ea4f1adbe744a321a1a1554778b8778193`; manifest `e2a8074edbf05a7ef935e3771db5189f9901bb6d846247e810c350dec3de5cc3`. |

All hashes here are SHA-256. The collector is
[`metrics.sh` at 95f1eae](https://github.com/aeharding/open-connect/blob/95f1eae00007e59fe5700a2ef08fd8107aa15bde/cmu/bench/metrics.sh),
**`04ce5017e08a4e62823135eb6a560cefbc51289edda256ff5f2b1946b3d5a109`**.
The existing [parser](https://github.com/aeharding/open-connect/blob/b386f8036ef57f44f1142147339cae30c21a1a63/tooling/open_connect/metrics.py)
has hash `d0e93378c264d274d01019026c7d192e10875adc3fe8fe1d13dff5554fdd63d5`.
The normal observer profile manifest is
`b1e86f8d3c67d4f8784043222d95483d5123e7e7f6eb49b90bd415bf9907316c`.
The collector invocation within the boot-local observer was:

```sh
timeout -t 190 sh "$metrics" 180 1 "$token" > "$output" 2> "$errors"
```

`metrics` was the verified collector, `token` a fresh 32-hex frame token, and
outputs were RAM files retrieved after observation. This command describes
collection inside the prepared observer; it does not install the boot hook.
See the [boot-local method and its limits](performance.md#startup-observer-coverage-november-21-2026).

The private capture commands, with private roots replaced by `$EVIDENCE`, were
`python "$EVIDENCE/perf-start.py" dev22 N` for historical22 N=2,3,4 and fresh22
N=5,6,7; the same command with `dev23` for ed4 N=2,3,4;
`perf-start-backoff.py dev23 N` for b386 N=8,9,10; and
`perf-start-timer2000.py dev23 7` for CF7. These drivers are not distributed.
Their recorded source hashes are respectively
`c3028661e1de091325d5381576ded33c2fce946f0d8f247f97ae324c8670dd79`,
`b63608dc152e569a9e96002ab5930141f74d3d064bd1829bbe965b8a0c3dfb55` and
`1cbdecb3664af82ed449af30791f97d9fdf083fce91c3cc80e2881b3edd8287e`.
Explicit routing binds fresh22 membership to its archive and operator receipts
without rewriting capture results or historical manifests.

The host-only receiver replay is reproducible at b386 with
`node tests/fixtures/usb-receiver.js cmu/installer`.
The reviewed receiver hash is
`cee1cbaca2d910fc79299db9367347f5238f2136cc40cb609bf6b2ef1d2521d7`;
the fixture hash is
`2c6461db0b00533562f899229081e7cb1a86a78b3a76b80195709c316ef03d2f`.
The fixture checks bounded polling and lifecycle behavior. To reproduce the
exact immediate-empty counts, use the b386 checkout's existing fixture with each
pinned runtime (all simulated; no file changes or device access):

```sh
node <<'JS'
const fixture = require('./tests/fixtures/runtime-fixture.js');
const {execFileSync} = require('node:child_process');
for (const pin of ['ed4f750ade78a588e55e0b872e1080b22d747f7f',
                   'b386f8036ef57f44f1142147339cae30c21a1a63']) {
  const runtime = execFileSync('git', ['show', pin+':cmu/installer/runtime.js'],
                               {encoding:'utf8'});
  const app = {_connectedDevs:{A:{},B:{}},
               _messageTable:{TimedSbn_ConnectionStatus(){}}};
  const f = fixture('cmu/installer', {usbApp:app,
    sourceFor(url, source){return url.endsWith('runtime.js') ? runtime : source;}});
  f.install();
  const before = f.mediaRequests.length;
  app._messageTable.TimedSbn_ConnectionStatus.call(app,
    {params:{payload:{status:'Connected',type:'UMASS',usb:'A'}}});
  f.advance(65000);
  console.log(pin.slice(0,8), 'immediate-empty reads', f.mediaRequests.length-before);
}
JS
```

## Public data and arithmetic

These explicit exports are original Open Connect work, **AGPL-3.0-or-later**:

- [runs.csv](assets/performance/dev23-usb-discovery/runs.csv): 13 per-run observations, window bounds/counts, collector coverage, named RAM and prior Home estimates.
- [samples.csv](assets/performance/dev23-usb-discovery/samples.csv): 1,877 numeric samples covering the selected 20–170 s span and its immediate neighboring samples; only uptime, first-eight CPU counters, named memory fields, loopback RX packets and global task creation.
- [io.csv](assets/performance/dev23-usb-discovery/io.csv): 65 role-based partition deltas over each run's selected 20–170 s endpoints. Do not sum these into whole-device traffic.

No OEM code/binary, Navigation implementation or licence data, private driver,
raw capture, credentials, device/boot identifiers or owner paths are included.
Raw-input hashes and receipts remain private. These exports reproduce numeric
selection and arithmetic; they do not recreate capture acquisition, independently
review video or verify physical identity.

Select samples **wholly inside** uptime 20–170 or 60–170 s (`start >= lower`,
`end <= upper`), then difference the first and last aggregate counters. For the
first eight `/proc/stat` fields, `busy = total − idle − iowait`;
`CPU% = 100 × Δbusy / Δtotal`. **Two cores' total capacity is 100%**.
Compute per-run rates first, then median/range across boots; do not pool samples.

RAM minima use all selected 20–170 s samples; ending values use the last one.
Linux kB here is KiB. `available proxy = MemFree + Buffers + Cached +
SReclaimable − Shmem`; Linux 3.0.35 has no kernel `MemAvailable`. AnonPages is
resident anonymous memory, not Committed_AS. Divide KiB by 1,024 for MiB.
Opera PSS/private cover the **whole process** after the 225 s observation window;
`snapshot_end_s` is the end of the whole scan, not each mapping's timestamp.
Private is Private_Clean + Private_Dirty. Own allocated files sum
`st_blocks` once per unique `(device,inode)` pair × 512 bytes, excluding persistent
symlink targets. This is not logical file size and **is not added to PSS**.

From the repository root, the following standard-library-only command opens
only the public CSVs, verifies CPU/window and RAM arithmetic, and prints all
cohort medians/ranges and primary differences, and checks the final positive
arithmetic audit against public per-boot inputs. CF7 stays n=1. The historical
blocks remain separate from the explicit final groups.

```sh
python3 - <<'PY'
import csv
from pathlib import Path
from statistics import median

folder = Path("docs/assets/performance/dev23-usb-discovery")
def read(name, source=folder):
    with (source / name).open(newline="") as stream:
        return list(csv.DictReader(stream))

candidate = Path("docs/assets/performance/dev23-final-resources")
runs = read("runs.csv") + read("runs.csv", candidate)
samples = read("samples.csv") + read("samples.csv", candidate)
io_rows = read("io.csv") + read("io.csv", candidate)
groups = {name: [r for r in runs if r["cohort"] == name]
          for name in ("historical22", "ed4", "b386", "fresh22", "cf7")}
groups["home12-14"] = [r for r in runs if r["cohort"] == "baff018" and r["trial"] in ("12", "13", "14")]
groups["all11-14"] = [r for r in runs if r["cohort"] == "baff018"]
assert [r["trial"] for r in groups["home12-14"]] == ["12", "13", "14"]
assert [r["trial"] for r in groups["all11-14"]] == ["11", "12", "13", "14"]
for run in runs:
    run["end_raw_used_kib"] = int(run["end_MemTotal_kib"]) - int(run["end_MemFree_kib"])
ticks = "user nice system idle iowait irq softirq steal".split()
metrics = ("cpu_20_170_pct", "cpu_60_170_pct", "opera_pss_kib",
           "opera_private_kib", "own_tmpfs_kib", "min_MemFree_kib",
           "end_available_proxy_kib", "end_AnonPages_kib", "end_raw_used_kib",
           "end_Shmem_kib", "end_Slab_kib", "end_Cached_kib", "end_Buffers_kib")
for run in runs:
    rows = [s for s in samples if (s["cohort"], s["trial"]) ==
            (run["cohort"], run["trial"])]
    for lower in (20, 60):
        selected = [s for s in rows if float(s["uptime_start_s"]) >= lower
                    and float(s["uptime_end_s"]) <= 170]
        first, last = selected[0], selected[-1]
        delta = [int(last[k+"_ticks"]) - int(first[k+"_ticks"]) for k in ticks]
        assert min(delta) >= 0 and sum(delta) > 0
        cpu = 100 * (sum(delta)-delta[3]-delta[4]) / sum(delta)
        assert abs(cpu-float(run[f"cpu_{lower}_170_pct"])) < 1e-10
        prefix = f"window_{lower}_170_"
        assert len(selected) == int(run[prefix+"samples"])
        for side, sample in (("first", first), ("last", last)):
            for edge in ("start", "end"):
                assert sample[f"uptime_{edge}_s"] == run[prefix+f"{side}_{edge}_s"]
        if lower == 20:
            assert min(int(s["MemFree_kib"]) for s in selected) == int(run["min_MemFree_kib"])
            proxy = sum(int(last[k+"_kib"]) for k in
                        ("MemFree", "Buffers", "Cached", "SReclaimable")) - int(last["Shmem_kib"])
            assert proxy == int(run["end_available_proxy_kib"])
    assert int(run["opera_private_kib"]) == (int(run["opera_private_clean_kib"]) +
                                            int(run["opera_private_dirty_kib"]))

summary = {}
for cohort, n in (("historical22", 3), ("ed4", 3), ("b386", 3), ("fresh22", 3),
                  ("cf7", 1), ("home12-14", 3), ("all11-14", 4)):
    rows = groups[cohort]
    assert len(rows) == n
    summary[cohort] = {}
    for metric in metrics:
        values = [float(r[metric]) for r in rows]
        summary[cohort][metric] = median(values)
        print(cohort, metric, "median/range", median(values), min(values), max(values))
for current, reference in (("ed4", "historical22"), ("b386", "ed4"),
                           ("b386", "historical22"), ("b386", "fresh22"),
                           ("fresh22", "historical22"), ("home12-14", "fresh22"),
                           ("home12-14", "b386"), ("all11-14", "fresh22"),
                           ("all11-14", "b386")):
    print("delta", current, reference,
          {k: summary[current][k]-summary[reference][k] for k in metrics})
for row in io_rows:
    if row["cohort"] == "b386" and row["role"] == "persistent":
        print("retained persistent I/O", row)

def resource_values(run, rows, io_rows):
    """Derive named per-boot scalars from the public numeric inputs."""
    values = {}
    aliases = {'own_tmpfs_kib':'own_allocated_tmpfs_kib',
               'opera_pss_kib':'post225_opera_pss_kib',
               'opera_private_kib':'post225_opera_private_kib',
               'own_unique_files':'own_unique_files'}
    for role in ('logger','kapture'):
        for kind in ('pss','private'):
            aliases[f'{role}_{kind}_kib']=f'post225_{role}_{kind}_kib'
    for field,metric in aliases.items():
        if field in run: values[metric]=float(run[field])
    def select(lo, hi):
        return [s for s in rows if float(s['uptime_start_s'])>=lo
                and float(s['uptime_end_s'])<=hi]
    def cpu(selected):
        delta=[int(selected[-1][k+'_ticks'])-int(selected[0][k+'_ticks']) for k in ticks]
        assert min(delta)>=0 and sum(delta)>0
        busy=sum(delta)-delta[3]-delta[4]
        return 100*busy/sum(delta),busy/100
    for lo in (20,60):
        selected=select(lo,170); prefix=f'{lo}_170.'
        values[prefix+'cpu_busy_pct'],values[prefix+'busy_cpu_seconds_assuming_hz100']=cpu(selected)
        for name in selected[0]:
            if not name.endswith('_kib'):continue
            numbers=[int(s[name]) for s in selected]
            for label,value in (('first',numbers[0]),('end',numbers[-1]),('min',min(numbers)),('max',max(numbers))):
                values[prefix+name[:-4]+'_'+label+'_kib']=value
        proxies=[sum(int(s[k+'_kib']) for k in ('MemFree','Buffers','Cached','SReclaimable'))-int(s['Shmem_kib']) for s in selected]
        for label,value in (('first',proxies[0]),('end',proxies[-1]),('min',min(proxies)),('max',max(proxies))):
            values[prefix+'available_proxy_'+label+'_kib']=value
        values[prefix+'raw_used_end_kib']=int(selected[-1]['MemTotal_kib'])-int(selected[-1]['MemFree_kib'])
    io_names={'read_sectors':'sectors_read','write_sectors':'sectors_written',
              'read_ticks_ms':'read_ticks_ms','write_ticks_ms':'write_ticks_ms',
              'reads':'reads','writes':'writes','io_ticks_ms':'io_ticks_ms',
              'weighted_io_ticks_ms':'weighted_io_ticks_ms'}
    for row in io_rows:
        prefix=row.get('window','20_170')+'.';role=row['role']
        roles=[role]
        if role=='navigation':roles+=['physical_role.navigation']
        if role=='remaining_usb_inferred':roles+=['physical_role.remaining_usb_source_inferred']
        for field,metric in io_names.items():
            if field in row:
                for name in roles:values[prefix+name+'.'+metric]=int(row[field])
    windows=[(20,60),(20,65),(20,170),(50,110),(60,170),(65,170),(110,170)]
    windows += [(lo,lo+10) for lo in range(20,170,10)]
    for lo,hi in windows:
        selected=select(lo,hi)
        elapsed=float(selected[-1]['uptime_start_s'])-float(selected[0]['uptime_start_s'])
        net={'cpu_busy_pct':cpu(selected)[0]}
        fields={'loopback_rx_packets':'rx_packets','loopback_tx_packets':'tx_packets',
                'loopback_rx_bytes':'rx_bytes','loopback_tx_bytes':'tx_bytes',
                'global_task_creations':'global_task_creations'}
        for field,name in fields.items():
            if field not in selected[0]:continue
            delta=int(selected[-1][field])-int(selected[0][field]);assert delta>=0
            net[name]=delta;net[name+'_per_s']=delta/elapsed
        prefix=f'curve.{lo}.' if hi-lo==10 else f'loopback.{lo}_{hi}.'
        values.update({prefix+k:v for k,v in net.items()})
    return values

per_boot = {}
for run in runs:
    identity = (run["cohort"], run["trial"])
    match = lambda r: (r["cohort"], r["trial"]) == identity
    per_boot[identity] = resource_values(run, list(filter(match, samples)),
                                         list(filter(match, io_rows)))
# Only scalars missing from the original control exports are supplemented.
for row in read("control-inputs.csv", candidate):
    values = per_boot[(row["cohort"], row["trial"])]
    assert row["metric"] not in values
    values[row["metric"]] = float(row["value"])
for row in read("positive-deltas.csv", candidate):
    def observations(group):
        return [per_boot[(r["cohort"], r["trial"])][row["metric"]] for r in groups[group]]
    current, reference = observations(row["group"]), observations(row["reference"])
    expected = [median(current)-median(reference), median(current), min(current),
                max(current), median(reference), min(reference), max(reference)]
    fields = ("delta_median", "candidate_median", "candidate_min", "candidate_max",
              "reference_median", "reference_min", "reference_max")
    assert [float(row[k]) for k in fields] == expected
    assert expected[0] > 0
print("Every positive arithmetic row reproduced; positive is not a regression label.")
for group in ("fresh22", "b386", "home12-14", "all11-14"):
    for metric in ("own_unique_files", "post225_logger_pss_kib", "post225_logger_private_kib",
                   "post225_kapture_pss_kib", "post225_kapture_private_kib",
                   "loopback.50_110.rx_packets_per_s", "loopback.50_110.global_task_creations_per_s"):
        values = [per_boot[(r["cohort"], r["trial"])][metric] for r in groups[group]]
        print(group, metric, "median/range", median(values), min(values), max(values))
    for role in ("firmware_root", "firmware_resources", "persistent", "navigation", "remaining_usb_inferred"):
        for counter in ("sectors_read", "sectors_written", "read_ticks_ms", "write_ticks_ms"):
            key = "20_170." + role + "." + counter
            values = [per_boot[(r["cohort"], r["trial"])][key] for r in groups[group]]
            print(group, role, counter, "median/range", median(values), min(values), max(values))
PY
```

For loopback, select wholly contained 50–110 s samples in the same way;
`rate = Δloopback_rx_packets / Δuptime_start_s`. Take each cohort's median rate.
The excess reduction is
`100 × (ed4_rate − b386_rate) / (ed4_rate − historical22_rate)`.
Global task-creation rates use the corresponding counter and duration; neither
counter is a per-process execution count. Home midpoints use
`(home_lower_estimate_s + home_upper_estimate_s) / 2` per nonblank row.
Round differences only after subtracting unrounded per-run medians.

Private authored analysis attribution: `analysis.json` records analyzer SHA-256
`29b1022daf1b2fa592d90241ee7e452915378e5b811237af7d4c536c20f0adde`;
the later fresh22 quick comparison records
`6930d307ce1af6bd33da4c1ff1fa699d69da6e6e02f2670c0f0ff594c55e2085`.
Those private reports supplied interpretation and prior Home estimates. The
public command above independently recomputes the numeric resource comparison
from the sanitized exports, without requiring those scripts or raw captures.

## Final baff018 resource measurements — November 26, 2026

Primary Opera PSS/private and CPU medians are lower than both current-setup
controls; Opera ranges overlap controls, while several global RAM, I/O and
traffic counters rose. **No blanket performance acceptance or RAM waiver follows.**
Native functional evidence is recorded separately in
[PR #179](https://github.com/aeharding/open-connect/pull/179); these resource trials
do not test installation, phone projection or physical controls.

**Primary: Home-prepared trials 12/13/14 (n=3)**, predeclared at 08:10:58 UTC
before trial 14 acquisition to resolve a visually verified preparation mismatch.
**Secondary: all attempts 11–14 (n=4)**, retaining trial 11’s Install/Done/Settings
Display preparation; its median averages the middle two observations. The other
nine starts began on Home; all ten returned to ordinary Home. The final groups
share three boots. Controls are only fresh published dev.22 5–7 and b386 8–10;
no high-CPU control or I/O outlier was removed.

Each cell is **median (minimum–maximum)** of per-boot values, using the CPU,
RAM and snapshot definitions above. End counters use the last sample wholly
inside 20–170 s. Raw-used proxy is `MemTotal − MemFree`, including cache;
it is not application allocation.

| Metric | Fresh published dev.22, 5–7 | b386, 8–10 | Primary final, 12–14 | All final attempts, 11–14 |
| --- | ---: | ---: | ---: | ---: |
| CPU 20–170 s, % | 29.1997 (29.0164–30.5324) | 29.3862 (29.3630–29.6771) | 29.0768 (28.6078–29.1622) | 28.8423 (28.5733–29.1622) |
| CPU 60–170 s, % | 12.7341 (12.6000–15.1673) | 13.0017 (12.4052–13.4547) | 12.6897 (12.1979–13.0207) | 12.5096 (12.1979–13.0207) |
| Post-225 s Opera PSS, KiB | 52,916 (52,652–52,980) | 52,752 (50,776–52,892) | 50,876 (50,256–52,812) | 51,098 (50,256–52,812) |
| Post-225 s Opera private, KiB | 52,472 (52,208–52,536) | 52,308 (50,332–52,448) | 50,432 (49,812–52,368) | 50,654 (49,812–52,368) |
| Own allocated regular RAM files, KiB | 396 (396–396) | 396 (396–396) | 396 (396–396) | 396 (396–396) |
| Minimum MemFree, KiB | 116,788 (116,532–117,260) | 117,792 (117,048–118,828) | 119,124 (116,868–120,924) | 119,784 (116,868–120,924) |
| End available-RAM proxy, KiB | 381,648 (381,152–382,392) | 383,052 (382,432–383,760) | 383,764 (382,248–385,828) | 384,500 (382,248–385,828) |
| End raw-used proxy, KiB | 638,128 (637,388–638,636) | 636,728 (636,028–637,924) | 636,164 (634,104–637,704) | 635,432 (634,104–637,704) |
| End AnonPages, KiB | 279,284 (279,152–280,196) | 279,472 (277,416–279,544) | 277,104 (276,556–278,664) | 277,212 (276,556–278,664) |
| End Shmem, KiB | 6,180 (4,692–6,184) | 4,676 (4,672–6,172) | 6,180 (4,672–6,184) | 5,426 (4,672–6,184) |
| End Slab, KiB | 22,288 (22,244–22,332) | 22,280 (22,260–22,452) | 22,336 (22,244–22,348) | 22,324 (22,244–22,348) |
| End Cached, KiB | 247,248 (245,772–247,248) | 245,912 (245,760–247,248) | 247,288 (245,780–247,320) | 246,538 (245,780–247,320) |
| End Buffers, KiB | 7,508 (7,504–7,512) | 7,516 (7,492–7,776) | 7,600 (7,596–7,612) | 7,604 (7,596–7,612) |

Primary Opera PSS/private medians are **2,040 / 1,876 KiB lower** against
fresh22 / b386; all-attempts differences are **1,818 / 1,654 KiB lower**.
The final 20–170 s CPU range is below b386’s and overlaps fresh22’s; later CPU
ranges overlap both controls. Small ordered blocks prevent causal speedup or
non-regression conclusions.

Against fresh22 / b386, primary Slab is **+48 / +56 KiB**, Cached
**+40 / +1,376 KiB**, Buffers **+92 / +84 KiB**, and Shmem **0 / +1,504 KiB**.
Primary SReclaimable is +12 / +16 KiB and SUnreclaim +32 / +28 KiB;
all-attempts values are +10 / +14 and +26 / +22 KiB. All-attempts KernelStack
is +4 KiB against fresh22. Global counters overlap and do not identify product
allocation; positive free/cache arithmetic is not automatically a cost.

Own allocated regular RAM files were **405,504 bytes (396 KiB)** every boot:
31 unique files in final/b386, 33 in fresh22. This is separate from PSS and
Shmem. Final whole-scan endpoints were 226.27–226.32 s. Logger median PSS/private
was 683/560 KiB in fresh22/final versus 687/564 in b386; Kapture was 498/420
throughout. The name filter missed the BusyBox listener and ignition shell;
unobserved helpers are not zero RAM. Per-process ages and identity guards were
unavailable. These snapshots cannot isolate JavaScript heaps or startup peaks.

For I/O, each cell below is the median of **read sectors / written sectors /
read ticks ms / write ticks ms** in 20–170 s. Sectors are 512 bytes; ticks
are summed counters, not elapsed boot latency.

| Partition role | Fresh22 | b386 | Primary final | All final attempts |
| --- | ---: | ---: | ---: | ---: |
| Firmware root | 209,696 / 0 / 64,940 / 0 | 208,960 / 0 / 63,250 / 0 | 210,064 / 0 / 62,410 / 0 | 210,064 / 0 / 60,680 / 0 |
| Writable firmware data (`firmware_resources`) | 4,696 / 1,080 / 3,320 / 7,810 | 4,704 / 1,072 / 3,520 / 4,770 | 4,704 / 1,080 / 3,200 / 8,520 | 4,704 / 1,076 / 3,340 / 8,925 |
| Persistent data | 539 / 186 / 150 / 670 | 610 / 188 / 130 / 870 | 618 / 181 / 120 / 700 | 617.5 / 182 / 125 / 675 |
| Navigation | 53,366 / 0 / 4,260 / 0 | 53,366 / 0 / 4,310 / 0 | 53,366 / 0 / 4,290 / 0 | 53,366 / 0 / 4,300 / 0 |
| Remaining USB (inferred) | 192 / 0 / 40 / 0 | 160 / 0 / 60 / 0 | 384 / 0 / 70 / 0 | 384 / 0 / 70 / 0 |

Writable firmware-data write ticks rose **710 / 3,750 ms** (primary) and
**1,115 / 4,155 ms** (all) against fresh22 / b386; USB reads rose **192 / 224
sectors**. The unexplained b386 burst remains **trial 8**. Navigation role
follows native mount receipts; remaining USB is inferred from the two-media
fixture. Whole-map contents and cache state were not verified.

Loopback RX median was **45.20 packets/s** in both final groups versus
**38.06 / 44.84** in fresh22 / b386. Global task-creation medians were
**91.46 / 91.45 tasks/s** (primary / all) versus **90.05 / 91.08** in the
controls, wholly within 50–110 s. These counters do not identify native request
counts or per-process CPU. RX and TX describe the same traffic and are not summed.

The firmware, preset, held USB, approximately 30 s ACC-off/B+ retained,
225 s without SSH, collector cadence and deadlines match the method above.
Developer access remained off and transaction notices clear. Ten-start coverage
began at uptime 10.31–10.79 s and ended at 189.63–190.63 s; earlier RAM and
between-sample peaks are unknown.
Actual final profile SHA-256 is
`5841121864430cc80110d41c908a1ec5e58cb9456b64b3774706a6997d7acfcd`.
Its complete 1,467-byte ordinary branch is byte-identical to B1, SHA-256
`27f72409f1ba392fe4d9a28decd7b5fc02f4499d3e25ff3ac27661c36e99b0a6`,
and exits before observer injection; ordinary product code had no injected
observer load. Collector/parser and the normal `perf-start.py` retain their
full source hashes above. Acquisition was `python "$EVIDENCE/perf-start.py"
dev23 N` for N=11,12,13,14, with explicit final-source routing; the original
capture manifests were not relabeled.
The preparation-controlled private arithmetic wrapper has SHA-256
`7163e39cfc8c8654546ed051c091770f9276557f8e6192a63d1905f83e5f3b95`;
the public command reproduces its resource summaries without private files.

Visible Home witnesses the workload. The new offline template score is a
**late animation endpoint**, not first usable Home. Icons/labels can still
animate; camera/relay latency is uncalibrated and trial 11 preparation differs.
No new Home timing is exported or backfilled: historical b386 cells and
fresh22 blanks stay exact. Usable-Home latency, accepted input, stock parity and
native install-completion timing are unmeasured here.

The measured final input is source
[`baff018e18e45fb26c752fd016c1fe1df5f85ece`](https://github.com/aeharding/open-connect/tree/baff018e18e45fb26c752fd016c1fe1df5f85ece),
[CI 45773095807](https://github.com/aeharding/open-connect/actions/runs/45773095807),
artifact **15096145857**. ZIP SHA-256:
`3045ab0a2b4408a670a812d16bdde21046d33c88d89b2ff1df948c3696e22272`;
payload manifest SHA-256:
`87ce6e12c7a759780350f8355b1679c86236bfdd6894ba26cafd95bb51dd931b`.
Native completion evidence in PR #179 is separate.

The following sanitized exports are original **AGPL-3.0-or-later** numeric data:

- [Final runs](assets/performance/dev23-final-resources/runs.csv): four per-boot resource observations, preparation, snapshot phase and exact source/CI provenance.
- [Final samples](assets/performance/dev23-final-resources/samples.csv): 577 numeric samples over 20–170 s and its immediate neighbors; CPU, named RAM and traffic/task counters.
- [Final I/O](assets/performance/dev23-final-resources/io.csv): 48 role/window rows for 20–170 and 60–170 s, including operation and busy/weighted-tick counters.
- [Supplemental control inputs](assets/performance/dev23-final-resources/control-inputs.csv): only per-boot scalars missing from the unchanged public fresh22/b386 exports, including diagnostic phase counters and named native snapshots.
- [Positive arithmetic audit](assets/performance/dev23-final-resources/positive-deltas.csv): both final groups against both controls, with every positive resource delta and both ranges; includes increases in free/cache counters and extra I/O operations/weighted ticks. These are not regression labels.

The [public command above](#public-data-and-arithmetic) reuses unchanged controls,
supplements only missing scalars, recomputes resource summaries and checks every
audit row from public per-boot inputs. Numeric inputs do not establish physical
identity or timing. Device identifiers, PIDs, private paths/licences, OEM frames
and raw captures remain excluded.
