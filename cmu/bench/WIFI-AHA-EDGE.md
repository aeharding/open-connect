# Experimental Wi-Fi dependency pilot

Question: does allowing Wi-Fi startup after `stage_3`, without waiting for Aha,
improve wireless projection? This branch is a one-variable experiment, not a
qualified addition to Base optimizations.

Control: final dev.8 CI bundle from source `764d76e0`, Base1/Wireless1/Pandora1,
Allow/Skip1, product UART/SSH0. Keep the existing stage-1 collector, receive-only
UART/video, reference SD/Ethernet, paired iPhone8,4 with iOS15.8.8 and USB on the
Mac, Apple CarPlay Wi-Fi mode, 12.02V/2A supply and fixed exposure105/gain32.
Retain the idle night dashboard, no route or playing audio. Measurements stay
passive until capture finishes.

The existing Base bit gates one removal in both selected RAM SM profiles:
`stage_wifi` no longer depends on `blm_ira_aha`. Preserve its existing `stage_3`
dependency. Aha still starts; its service, the `stage_vr` and `gap2` dependencies,
BDS logging, hardware detection and all other SM policy remain unchanged. Do not
combine this with the separately parked BDS warning experiment. The composer
refuses missing/duplicate required edges before publishing selected RAM state.
No new setting, snapshot field, boot hook or persistent trial mechanism is added.

Build with `make release OUT=runs/wifi-aha-edge-build`. If the local native compiler
differs from the control CI compiler, retain the unchanged compiled members from
CI44951500558 and package the authored static delta through the existing Make/
shell build. Record actual source, ZIP, public/private manifests and this local
assembly provenance; do not label the result CI-qualified. Verify both real OEM
profiles privately: Base0 must match the control byte for byte and Base1 must
remove exactly one Aha dependency line inside `stage_wifi`.

Use the maintained installer for one update and unmeasured setup restart,
preserving current settings, baseline and undo. Verify selected profiles, loaded
processes and root mount. Then run one passive 30-second ACC-off pilot with the
frozen capture runner `ab8993a5`, Base1/Wireless1/Pandora1 and actual installed
instance hash. Use analysis `4da76e1` and the published milestone definitions.
Retain failures and partial observations. Compare AP/DHCP, Bluetooth OOB,
association/WPA, session activation, visible dashboard and matched CPU/RAM/I/O.
UART delivery timestamps remain separate from calibrated camera/collector clocks.
Check NMS, BLM, jciITTS, jciITT and jcitraffic after capture. This does not qualify
physical audio/input, all phone types or long-parked reliability. A single pilot
can select a candidate for repetition; it cannot establish a general speedup.

Undo independently with the pinned CI control ZIP through native maintenance,
then a fresh ACC boot. Verify restored Aha dependency, retained settings and
baseline, original loaded BDS arguments/Info level, healthy native services,
wireless reconnection and physical root read-only. Existing bench SSH recovery
and stage-1 restore remain independent. Keep OEM profiles, raw captures, phone
identifiers and credentials private; publish authored source and reviewed,
sanitized evidence only.
