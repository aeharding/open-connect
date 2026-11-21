# Collector overhead experiment

Playground code, not a supported benchmark command. Keep one idle CarPlay scene,
phone, firmware and feature/service configuration fixed across the whole batch.
Use an existing trusted UID-0 SSH alias on exact 74.00.324A NA.

```sh
python -m open_connect.metrics_overhead --host my-cmu \
  --bundle runs/overhead-1 --label 'stock services; wired CarPlay idle dashboard'
```

Add `--ssh-config /path/to/config` for a separate SSH configuration. No device
setup or persistent writes are performed. The command is live and finite.

The default is three control/sampling pairs, alternating their order. Each
45-second reference window records two CPU, uptime and free-RAM endpoints.
Sampling windows run the normal one-second-pause collector for 40 seconds,
starting two seconds inside the window. Both reference and collector must stay
on the same boot, and all collector samples must fall inside their reference.
The extra SSH session is part of the cost being measured.

CPU busy excludes idle and iowait and uses aggregate tick deltas over the actual
reference interval. Report all windows and paired percentage-point differences;
three pairs are an initial overhead check, not a rare-latency or significance
study. Endpoint free RAM does not measure peak collector memory. This script
does not assess startup or physical input latency.

Retain the immutable experiment/collector commits, exact command/configuration
and all failures. Raw output remains private; publish reviewed derived results.
