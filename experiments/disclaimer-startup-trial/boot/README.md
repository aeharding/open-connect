# Candidate C startup observer (review only)

This adapter is offline preparation. It has not observed a modified startup.
No current reboot, CMU open, source change, remount or restore is authorized.

The adapter imports the pinned corrected stock BootGate, Video, credential reader,
Session and port/lock behavior. Stock files, profiles and core remain untouched.
It uses the stock read-only source check, with a C-specific verifier and C labels.

## Actual apply evidence contract

Write a small private JSON file after the actual root apply transaction finishes:

    {"schema":1,"core_bundle":"/absolute/workspace/runs/.../apply","trial_nonce":"32lowercasehex"}

The last non-identity operation in that core bundle must be completed0/root55/NA,
port closed, with intact output/RX artifact hashes, actual END0 followed by PS1.
Its actual target output must contain exactly one line:

    CANDIDATE_BOOT_BIND|<trial_nonce>|C|<dev:inode:mtime:size:mode:uid:gid:nlink>|94055|64db9d0df2277e1d95a037929aef30c4|776631029|ro|1|candidate_verified

The root device is64785. The source is the fixed systemApp.js path, mode755,
UID1018/GID3015/nlink1. The applied inode and candidate mtime come from that
actual line. The readiness1 is emitted only after the persistent recovery tool
was verified BEFORE publication. The apply producer emits this line only after
final C verification, postflush, paired RO request and observed physical RO.

Unknown/nonzero/missing-prompt, O, isolated-copy device45826, missing readiness,
wrong nonce/control/hash/metadata, duplicate binding or modified artifacts refuse.
No actual apply evidence exists yet; review.json deliberately has no bound CID.

## Offline preparation

    .venv/bin/python -B experiments/disclaimer-startup-trial/boot/observe.py

After a separately authorized actual apply, bind its actual evidence without
opening any device:

    .venv/bin/python -B experiments/disclaimer-startup-trial/boot/observe.py \
      --apply-evidence runs/ACTUAL/apply-evidence.json \
      --write-profile runs/ACTUAL/candidate-observer.review.json

The emitted profile stays live_authority:false, reboot_hex:null and unresolved
normal-route authority. Root's combined trial disposition must provide the final
enabled profile. This adapter does not enable its own profile.

A future approved live invocation has the same private credentials, camera index,
owner, private bundle and prompt solicitation arguments as the stock observer:

    .venv/bin/python -B experiments/disclaimer-startup-trial/boot/observe.py \
      --live --profile runs/ACTUAL/ROOT_APPROVED_PROFILE.json \
      --bundle runs/NEW_CANDIDATE_BOOT --credentials PRIVATE_CREDENTIAL_JSON \
      --camera-index 0 --owner t14 --solicit-prompt

There is no live invocation in this handoff. A review profile refuses before
credential reads, camera, locks or adapter open. Required enabled-profile facts:
live_authority:true, normal_reboot_route_verified:true, exact stock no-flags
reboot_hex, one request/one established login,180s, source_kind:C, current code
pins, recovery_identity_policy:exact_full_applied_cstage_or_OTHER_no_adoption,
and the unchanged revalidated actual apply binding.

Preflight requires the exact applied CID including mtime/inode. Postboot requires
C94055B/MD5/CRC/mode/UID/GID/mtime/nlink/root device, physical rootRO, fresh root55,
changed boot_id and lower uptime. This trial requires the EXACT full applied C
identity after boot, including inode and candidate mtime. Any changed field with
hash-identical C bytes is recovery-identity conflict/OTHER: after-conflict.json
records actual identity, the adapter preserves/stops, and performs no adoption or
control rewrite. It does not report C success or usable undo. The independent
persistent tool's VERIFY remains required even after an exact identity match.
Success is candidate_restart_access_C_RO_verified. Failed/unknown runs do not
claim a postboot C result. There is no O success label or automatic recovery.

One request, receive-only bootloader observation, one prompt-gated established
login, bounded video and actual frame/PTS validation are inherited behavior.
The observer never restores the GUI. Persistent apply/undo and combined trial
policy belong to t12/t6. Approx5FPS/cropping do not prove no-flash or cold start.

## Offline field-marker correction

The executed trial's original outcome and `review.json` remain historical. Its
postboot META record was attached to an unfinished logger line (`0x47eaSWST|META`),
so the previous line-start parser missed it. Current code accepts one complete
`SWST|KEY|value` record after a prefix on a newline-terminated line. Every expected
field must occur once with a complete typed value. Duplicated/interleaved markers,
unknown fields, quoted lookalikes, malformed/suffixed values and unterminated
records refuse; fragments are never repaired. Raw evidence is not rewritten.

The producer (`stock.CHECK`), wire/core, exact CID policy, RO and new-boot checks
are unchanged. A sanitized prefix fixture uses only synthetic identities/times.
The check runner now writes **field-marker-review.json**, always review-only with
no binding or reboot authority. It verifies the old executed source copy, original
unknown manifest, historical `review.json`, final-freeze and first-feature freeze
are unchanged. `field-marker-history.json` records those preservation pins.
This correction has no live verification or new device authority.

## Checks

    .venv/bin/python -B experiments/disclaimer-startup-trial/boot/check.py

Only synthetic saved-core evidence, the existing logger fixture and fake
Session/camera/port flows are tested. No UART, camera, credential or reboot action
is performed. Snapshots and the passing manifest live under boot/checks/.
