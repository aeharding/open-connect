#!/usr/bin/env python3
"""Run compiled ARMv7 freestanding ELFs under qemu-arm-static + BusyBox + real Linux tmpfs.

Layer 1 public CI harness (zero OEM files, zero bench hardware):
  Part A: 100% unmodified `make release` ARMv7 binaries (`flush`, `api`, `install`,
          `boot-select`, `ignition`) + exact Linux `tmpfs` 4 KiB page measurements.
  Part B: Full end-to-end synthetic CMU lifecycle inside a chroot with real mounted
          Linux `tmpfs` at `/tmp` executing ARMv7 `-nostdlib` `svc 0` ELFs compiled
          with test-only `-DOC_TEST_PINFILE` (install -> boot-select -> live Settings
          HTTP `/control` over BusyBox `tcpsvd` -> `install --boot-recover` -> uninstall).

Must be run as root on Linux with clang, ld.lld, llvm-objcopy, qemu-arm-static, and
static busybox (with tcpsvd/awk/sh) available.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
BOOT1 = "12345678-1234-1234-1234-123456789abc"
BOOT2 = "22345678-1234-1234-1234-123456789abc"
BOOT3 = "32345678-1234-1234-1234-123456789abc"
TOKEN_USB = "a" * 32
TOKEN_SET = "b" * 32

BUSYBOX_APPLETS = (
    "sh",
    "ash",
    "awk",
    "tcpsvd",
    "timeout",
    "mount",
    "umount",
    "sync",
    "cat",
    "cp",
    "mv",
    "rm",
    "ln",
    "mkdir",
    "rmdir",
    "chmod",
    "chown",
    "sleep",
    "grep",
    "sed",
    "tr",
    "cut",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    "sha256sum",
    "du",
    "ls",
    "stat",
    "test",
    "[",
    "printf",
    "echo",
    "true",
    "false",
    "ps",
    "kill",
    "id",
    "env",
    "dirname",
    "basename",
    "readlink",
    "mktemp",
    "dd",
    "od",
    "find",
    "xargs",
    "touch",
    "date",
    "uname",
    "nohup",
    "setsid",
)

ARM_BINFMT_SPEC = (
    r":{name}:M::\x7fELF\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x28\x00:"
    r"\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:"
    r"{interp}:CF"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cmd: list[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True, **kwargs)


def find_qemu_arm() -> Path:
    for name in ("qemu-arm-static", "qemu-arm"):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    raise RuntimeError("missing qemu-arm-static / qemu-arm")


def find_busybox() -> Path:
    override = os.environ.get("OC_TEST_BUSYBOX")
    if override and Path(override).is_file():
        return Path(override).resolve()
    found = shutil.which("busybox")
    if not found:
        raise RuntimeError("missing busybox")
    return Path(found).resolve()


@contextlib.contextmanager
def binfmt_arm(qemu: Path):
    bm = Path("/proc/sys/fs/binfmt_misc")
    mounted = False
    reg_entry: Path | None = None
    try:
        if not (bm / "register").exists():
            bm.mkdir(parents=True, exist_ok=True)
            res = subprocess.run(["mount", "-t", "binfmt_misc", "binfmt_misc", str(bm)])
            if res.returncode != 0 and not (bm / "register").exists():
                raise RuntimeError("failed to mount binfmt_misc")
            mounted = True
        if (bm / "status").read_text().strip() != "enabled":
            raise RuntimeError("binfmt_misc is globally disabled")
        exact = bm / "qemu-arm"
        usable = False
        if exact.is_file():
            lines = exact.read_text().splitlines()
            has_f = any(ln.startswith("flags:") and "F" in ln.split(":", 1)[1] for ln in lines)
            usable = bool(lines and lines[0].strip() == "enabled" and has_f)
        if not usable:
            name = f"oc-qemu-arm-{os.getpid()}"
            (bm / "register").write_text(ARM_BINFMT_SPEC.format(name=name, interp=str(qemu)))
            reg_entry = bm / name
        yield
    finally:
        if reg_entry is not None and reg_entry.exists():
            try:
                reg_entry.write_text("-1")
            except OSError:
                pass
        if mounted:
            subprocess.run(["umount", str(bm)], capture_output=True)


def stop_proc(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_control(
    port: int,
    token: str | None,
    fields: str | None,
    *,
    method: str = "POST",
    path: str = "/control",
) -> tuple[int, dict[str, str], str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    headers: dict[str, str] = {}
    body: bytes | None = None
    if method == "POST":
        headers["Content-Type"] = "text/plain"
        payload = (
            f"{token}|{fields}" if token is not None and fields is not None else (fields or "")
        )
        body = payload.encode()
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        return resp.status, hdrs, raw
    finally:
        conn.close()


def wait_port(port: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"listener on 127.0.0.1:{port} did not become ready")


def stock_sm(wcp: bool) -> bytes:
    sys.path.insert(0, str(ROOT))
    from tests.test_installer_preferences import InstallerPreferences

    txt = InstallerPreferences().profile(wcp)
    inject = (
        '  <service type="process" name="jciGUI" '
        'path="/jci/opera/opera_dir/userjs/opera" args="-u /jci/gui/index.html" autorun="yes"/>\n'
        '  <service type="process" name="jciMMUI" path="/jci/mmui/svcjcimmui.so" autorun="yes"/>\n'
    )
    return txt.replace("<services>\n", "<services>\n" + inject, 1).encode()


def populate_busybox(chroot: Path, busybox: Path) -> None:
    (chroot / "bin").mkdir(parents=True, exist_ok=True)
    (chroot / "usr/bin").mkdir(parents=True, exist_ok=True)
    (chroot / "usr/sbin").mkdir(parents=True, exist_ok=True)
    bb_dst = chroot / "bin/busybox"
    shutil.copyfile(busybox, bb_dst)
    bb_dst.chmod(0o755)
    for app in BUSYBOX_APPLETS:
        for d in (chroot / "bin", chroot / "usr/bin"):
            link = d / app
            if not link.exists() and not link.is_symlink():
                link.symlink_to("/bin/busybox")


def chroot_run(
    chroot: Path,
    argv: list[str],
    *,
    check: bool = False,
    timeout: int = 30,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["chroot", str(chroot), *argv],
        check=check,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def mount_tmpfs(target: Path, size: str = "32M") -> None:
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["mount", "-t", "tmpfs", "-o", f"size={size}", "tmpfs", str(target)], check=True)


def umount_quiet(target: Path) -> None:
    if not target.exists():
        return
    res = subprocess.run(["umount", str(target)], capture_output=True, text=True)
    if res.returncode != 0:
        print(
            f"  [warn] sync umount {target} busy ({res.stderr.strip()}); retrying lazy",
            file=sys.stderr,
        )
        subprocess.run(["umount", "-l", str(target)], check=True)


def build_arm_test_bins(out_dir: Path) -> dict[str, Path]:
    """Compile ARMv7 Thumb-2 -nostdlib binaries with test-only -DOC_TEST_PINFILE."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clang = shutil.which("clang")
    lld = os.environ.get("OC_LLD") or shutil.which("ld.lld")
    objcopy = shutil.which("llvm-objcopy")
    if not clang or not lld or not objcopy:
        raise RuntimeError(f"missing toolchain: clang={clang} lld={lld} objcopy={objcopy}")

    thumb_flags = [
        "--target=armv7-linux-gnueabi",
        "-march=armv7-a",
        "-mthumb",
        "-fomit-frame-pointer",
        "-mfloat-abi=soft",
        "-Oz",
        "-mllvm",
        "-enable-machine-outliner",
        "-fno-builtin",
        "-fno-pic",
        "-fvisibility=hidden",
        "-ffunction-sections",
        "-fdata-sections",
        "-ffreestanding",
        "-fno-stack-protector",
        "-fno-unwind-tables",
        "-fno-asynchronous-unwind-tables",
        "-nostdlib",
        "-static",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-DOC_TEST_PINFILE",
    ]
    link_flags = [
        f"--ld-path={lld}",
        "-Wl,-e,_start,--build-id=none,--gc-sections,--icf=all,-z,max-page-size=4096,--strip-all",
    ]
    core = ASSETS / "core"
    shared = [
        core / name
        for name in (
            "oc-hash.c",
            "oc-io.c",
            "oc-manifest.c",
            "oc-record.c",
            "oc-config.c",
            "oc-guard.c",
        )
    ]
    targets = {
        "api": [
            ASSETS / "api.c",
            *shared,
            core / "oc-root.c",
            core / "oc-access.c",
            core / "oc-txn.c",
            core / "oc-render.c",
            core / "oc-api.c",
        ],
        "install": [
            ASSETS / "install.c",
            *shared,
            core / "oc-root.c",
            core / "oc-access.c",
            core / "oc-txn.c",
            core / "oc-render.c",
            core / "oc-compose.c",
        ],
        "boot-select": [
            ASSETS / "boot-select.c",
            *shared,
            core / "oc-plan.c",
            core / "oc-store.c",
            core / "oc-boot.c",
        ],
    }
    built: dict[str, Path] = {}
    for name, srcs in targets.items():
        dst = out_dir / name
        cmd = [clang, *thumb_flags, *link_flags, *(str(s) for s in srcs), "-o", str(dst)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            raise RuntimeError(f"failed compiling ARM test {name}:\n{res.stdout}{res.stderr}")
        subprocess.run(
            [objcopy, "--remove-section=.comment", "--remove-section=.ARM.attributes", str(dst)],
            check=True,
        )
        dst.chmod(0o700)
        built[name] = dst
    return built


def part_a_unmodified_release(work: Path, release_dir: Path, busybox: Path) -> None:
    """Part A: Exercise 100% unmodified `make release` ARMv7 ELFs + exact tmpfs page counts."""
    print("=== Part A: Unmodified make release ARMv7 ELFs & Linux tmpfs budgets ===")
    version = (ASSETS / "VERSION").read_text().strip()
    usb_dir = release_dir / f"usb/open-connect-{version}-usb/open-connect"
    flush_bin = release_dir / "flush"
    ig_bin = release_dir / "ignition"

    # 1. Exact real Linux tmpfs 4 KiB page measurements.
    tmpfs_mnt = work / "tmpfs-budget"
    mount_tmpfs(tmpfs_mnt, size="16M")
    try:
        # 1a. Full USB staged bundle on real tmpfs.
        staged_usb = tmpfs_mnt / "usb-bundle"
        shutil.copytree(usb_dir, staged_usb)
        usb_kb = int(run(["du", "-sk", str(staged_usb)]).stdout.split()[0])
        usb_pages = (usb_kb + 3) // 4
        print(f"  [tmpfs] USB staged bundle: {usb_kb} KiB ({usb_pages} 4KiB pages)")
        assert usb_kb <= 512, f"USB staged bundle exceeded 512 KiB budget: {usb_kb} KiB"

        # 1b. Exact 8-file (+ files.sha256) Settings boot session (service.sh:241) on real tmpfs.
        settings_files = (
            "files.sha256",
            "service.sh",
            "console.sh",
            "VERSION",
            "api",
            "flush",
            "runtime.js",
            "dialog.js",
            "settings.js",
        )
        staged_set = tmpfs_mnt / "settings-session"
        staged_set.mkdir(mode=0o700)
        for nm in settings_files:
            shutil.copyfile(usb_dir / nm, staged_set / nm)
            (staged_set / nm).chmod(0o700 if nm in ("api", "flush") else 0o600)
        set_kb = int(run(["du", "-sk", str(staged_set)]).stdout.split()[0])
        set_pages = (set_kb + 3) // 4
        print(f"  [tmpfs] 8-file Settings session: {set_kb} KiB ({set_pages} 4KiB pages)")
        assert set_kb <= 160, f"8-file Settings session exceeded 160 KiB budget: {set_kb} KiB"

        # 1c. 1-page ignition observer staged on real tmpfs.
        staged_ig = tmpfs_mnt / "ignition-stage"
        staged_ig.mkdir(mode=0o700)
        shutil.copyfile(ig_bin, staged_ig / "ignition")
        (staged_ig / "ignition").chmod(0o700)
        ig_kb = int(run(["du", "-sk", str(staged_ig)]).stdout.split()[0])
        ig_pages = (ig_kb + 3) // 4
        print(f"  [tmpfs] ignition observer: {ig_kb} KiB ({ig_pages} 4KiB pages)")
        assert ig_bin.stat().st_size <= 4096 and ig_kb <= 4, (
            f"ignition exceeded 1-page (4 KiB) budget: {ig_kb} KiB"
        )
    finally:
        umount_quiet(tmpfs_mnt)

    # 2. Unmodified ARMv7 `flush` SHA-256 parity and error codes.
    fdir = work / "flush-test"
    fdir.mkdir(mode=0o700)
    for label, payload in (
        ("empty", b""),
        ("one", b"x"),
        ("block64", b"A" * 64),
        ("big100k", os.urandom(102400)),
    ):
        p = fdir / label
        p.write_bytes(payload)
        for mode in ("h", "H"):
            r = run([str(flush_bin), mode, str(p)])
            want = sha(payload) if mode == "h" else f"{sha(payload)} *{p}"
            assert r.stdout.strip() == want, f"flush {mode} mismatch on {label}: {r.stdout!r}"
        run([str(flush_bin), "f", str(p)])
        run([str(flush_bin), "F", str(p)])
    run([str(flush_bin), "d", str(fdir)])
    r_enoent = run([str(flush_bin), "h", str(fdir / "missing")], check=False)
    assert r_enoent.returncode == 2, f"expected ENOENT=2, got {r_enoent.returncode}"
    r_einval_dir = run([str(flush_bin), "h", str(fdir)], check=False)
    assert r_einval_dir.returncode == 22, (
        f"expected EINVAL=22 on dir, got {r_einval_dir.returncode}"
    )
    r_einval_dev = run([str(flush_bin), "h", "/dev/null"], check=False)
    assert r_einval_dev.returncode == 22, (
        f"expected EINVAL=22 on /dev/null, got {r_einval_dev.returncode}"
    )
    print("  [ARMv7 flush] SHA-256 parity, fsync modes, ENOENT/EINVAL verified")

    # 3. Unmodified ARMv7 `api`, `install`, `boot-select gc`, and `ignition` inside a chroot.
    chroot = work / "chroot-a"
    chroot_tmp = chroot / "tmp"
    chroot.mkdir(mode=0o755)
    populate_busybox(chroot, busybox)
    mount_tmpfs(chroot_tmp, size="16M")
    try:
        for d in (
            chroot / "proc/self",
            chroot / "proc/sys/kernel/random",
            chroot / "sys/class/gpio/ACC_Sense",
            chroot / "dev",
            chroot / "jci",
            chroot / "tmp/open-connect/sessions/session-usb1",
            chroot / "tmp/mnt/data_persist/open-connect/snapshots",
            chroot / "tmp/mnt/data_persist/open-connect/packages",
            chroot / "tmp/mnt/data_persist/open-connect/composed",
        ):
            d.mkdir(parents=True, exist_ok=True)
        (chroot / "dev/urandom").write_bytes(os.urandom(4096))
        (chroot / "proc/uptime").write_text("42.00 10.00\n")
        (chroot / "proc/sys/kernel/random/boot_id").write_text(BOOT1 + "\n")
        (chroot / "proc/self/mounts").write_text(
            "rootfs / rootfs rw 0 0\n"
            "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
        )
        (chroot / "proc/mounts").symlink_to("self/mounts")
        (chroot / "jci/version.ini").write_text('JCI_SW_VER="WRONG_VER"\n')
        ram = chroot / "tmp/open-connect"
        sess = ram / "sessions/session-usb1"
        data = chroot / "tmp/mnt/data_persist/open-connect"
        for d in (
            ram,
            ram / "sessions",
            sess,
            data,
            data / "snapshots",
            data / "packages",
            data / "composed",
        ):
            d.chmod(0o700)
        for nm in ("api", "install", "boot-select", "ignition", "flush"):
            shutil.copyfile(release_dir / nm, sess / nm)
            (sess / nm).chmod(0o700)
        shutil.copyfile(usb_dir / "VERSION", sess / "VERSION")
        (sess / "VERSION").chmod(0o600)
        (sess / "token").write_text(TOKEN_USB + "\n")
        (sess / "token").chmod(0o600)
        (ram / "lock").write_bytes(b"")
        (ram / "lock").chmod(0o600)
        (ram / "usb-runtime").symlink_to("/tmp/open-connect/sessions/session-usb1")

        # 3a. Unmodified ARMv7 `api` HTTP framing + CORS + auth over real BusyBox `tcpsvd`.
        port = pick_port()
        srv = subprocess.Popen(
            [
                "chroot",
                str(chroot),
                "/bin/busybox",
                "tcpsvd",
                "127.0.0.1",
                str(port),
                "/tmp/open-connect/sessions/session-usb1/api",
                "/tmp/open-connect/sessions/session-usb1/token",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_port(port)
            st, hdrs, _ = http_control(port, None, None, method="GET")
            assert st == 400, f"GET expected 400, got {st}"
            assert hdrs.get("access-control-allow-origin") == "*", hdrs

            st_bad, _, _ = http_control(port, "0" * 32, "-|status|session|-|-")
            assert st_bad == 403, f"wrong token expected 403, got {st_bad}"

            st_ok, _, raw = http_control(port, TOKEN_USB, "-|status|session|-|-")
            assert st_ok == 200, f"status|session expected 200, got {st_ok}: {raw}"
            obj = json.loads(raw)
            assert obj.get("ok") is True and obj.get("closed") is False, obj

            # Fail-closed firmware guard on unmodified ARMv7 `api` (`WRONG_VER` -> unsupported_firmware).
            st_fw, _, raw_fw = http_control(port, TOKEN_USB, "-|install|-|-|-")
            assert st_fw == 200, (st_fw, raw_fw)
            obj_fw = json.loads(raw_fw)
            assert obj_fw.get("ok") is False and obj_fw.get("error") == "unsupported_firmware", (
                obj_fw
            )
            # Unmodified `install` refuses unsigned session with exact token.
            r_inst = chroot_run(
                chroot,
                [
                    "/tmp/open-connect/sessions/session-usb1/install",
                    "/tmp/open-connect/sessions/session-usb1",
                ],
            )
            assert (
                r_inst.returncode == 1 and r_inst.stdout.strip() == "incomplete_maintenance_bundle"
            ), (r_inst.returncode, r_inst.stdout, r_inst.stderr)
            # Manifest-valid session without OEM files -> unmodified `install` fails with exact
            # `unsupported_original` from real ARMv7 SHA-256 stock dependency verification.
            sess_fw = ram / "sessions/session-usbfw"
            shutil.copytree(usb_dir, sess_fw)
            sess_fw.chmod(0o700)
            for exe in ("api", "install", "boot-select", "ignition", "flush"):
                (sess_fw / exe).chmod(0o700)
            data_bak = chroot / "tmp/mnt/data_persist/.oc-bak"
            data.rename(data_bak)
            try:
                r_inst2 = chroot_run(
                    chroot,
                    [
                        "/tmp/open-connect/sessions/session-usbfw/install",
                        "/tmp/open-connect/sessions/session-usbfw",
                    ],
                )
            finally:
                data_bak.rename(data)
            inst2_lines = r_inst2.stdout.splitlines()
            assert (
                r_inst2.returncode == 1
                and len(inst2_lines) >= 2
                and inst2_lines[0] == "unsupported_original"
                and inst2_lines[1].startswith("DIAG|stock_dependencies|/jci/sm/sm.conf|missing|")
            ), (r_inst2.returncode, r_inst2.stdout, r_inst2.stderr)
            print(
                "  [ARMv7 api+tcpsvd] 400 GET+CORS, 403 bad token, 200 status|session, exact fail-closed guards verified"
            )
        finally:
            stop_proc(srv)

        # 3b. Unmodified ARMv7 `boot-select gc` prunes unpinned snapshots & `.prune-<id>` tombstones.
        def make_snap_dir(label: str, *, tombstone: bool = False) -> tuple[str, Path]:
            files = {
                "autostart": f"#!/bin/sh\n# {label}\n".encode(),
                "config": f"OC2\npackage={'3' * 64}\ntouch=1\nwarning=1\nbase=0\nnvram=disable\nmetadata=755:0:0\n".encode(),
                "dependencies": b"",
            }
            mf = "".join(f"{sha(v)}  {k}\n" for k, v in sorted(files.items()))
            sid = sha(mf.encode())
            d = data / "snapshots" / (f".prune-{sid}" if tombstone else sid)
            d.mkdir(mode=0o700)
            for k, v in files.items():
                (d / k).write_bytes(v)
                (d / k).chmod(0o600)
            (d / "files.sha256").write_text(mf)
            (d / "files.sha256").chmod(0o600)
            return sid, d

        keep_snap, keep_dir = make_snap_dir("keep")
        _, tomb_dir = make_snap_dir("tomb", tombstone=True)
        _, orphan0 = make_snap_dir("orphan-0")
        _, orphan1 = make_snap_dir("orphan-1")
        (data / "record").write_text(
            f"OC1|active|{'a' * 32}|{'3' * 64}|{keep_snap}|{keep_snap}|-|-|-|3|-|-|installed\n"
        )
        (data / "record").chmod(0o600)
        r_gc = chroot_run(
            chroot, ["/tmp/open-connect/sessions/session-usb1/boot-select", "gc", "/"]
        )
        assert r_gc.returncode == 0, r_gc.stdout + r_gc.stderr
        assert keep_dir.is_dir()
        assert not orphan0.exists()
        assert not orphan1.exists()
        assert not tomb_dir.exists()
        print("  [ARMv7 boot-select gc] real ARMv7 tombstone & unpinned snapshot pruning verified")

        # 3c. Unmodified 1-page Thumb-2 `ignition` detects sustained ACC_Sense 1->0 (3 samples),
        #     writes rec[10]=BOOT1, clears rec[10] back to "-" on QuickStart ACC=1, and exits 0
        #     cleanly when boot-id is unlinked!
        (data / "record").write_text(
            f"OC1|active|{'a' * 32}|{'3' * 64}|{keep_snap}|{keep_snap}|-|-|-|3|-|{BOOT1}|installed\n"
        )
        (data / "record").chmod(0o600)
        (chroot / "sys/class/gpio/ACC_Sense/value").write_text("1\n")
        (ram / "boot-id").symlink_to(BOOT1)
        ig_proc = subprocess.Popen(
            [
                "chroot",
                str(chroot),
                "/tmp/open-connect/sessions/session-usb1/ignition",
                BOOT1,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            lock_deadline = time.monotonic() + 5.0
            while time.monotonic() < lock_deadline and not (ram / "ignition.lock").exists():
                time.sleep(0.05)
            assert (ram / "ignition.lock").exists(), "ignition did not create ignition.lock"
            time.sleep(1.2)
            assert ig_proc.poll() is None, "ignition exited prematurely while ACC=1"
            rec_mid = (data / "record").read_text().strip().split("|")
            assert rec_mid[10] == "-", f"rec[10] changed while ACC=1: {rec_mid}"
            (chroot / "sys/class/gpio/ACC_Sense/value").write_text("0\n")
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                if (data / "record").read_text().strip().split("|")[10] == BOOT1:
                    break
                time.sleep(0.2)
            rec_after = (data / "record").read_text().strip().split("|")
            assert rec_after[10] == BOOT1, f"expected rec[10]={BOOT1}, got {rec_after}"
            # QuickStart resume: ACC=1 clears rec[10] back to "-".
            (chroot / "sys/class/gpio/ACC_Sense/value").write_text("1\n")
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if (data / "record").read_text().strip().split("|")[10] == "-":
                    break
                time.sleep(0.2)
            assert (data / "record").read_text().strip().split("|")[10] == "-"
            (ram / "boot-id").unlink()
            ig_proc.wait(timeout=5)
            assert ig_proc.returncode == 0, f"ignition exited {ig_proc.returncode}"
            print("  [ARMv7 ignition] 1-page Thumb-2 ACC_Sense 1->0->1 & clean exit verified")
        finally:
            if ig_proc.poll() is None:
                ig_proc.kill()
                ig_proc.wait(timeout=5)
    finally:
        umount_quiet(chroot_tmp)


def part_b_full_lifecycle(
    work: Path, release_dir: Path, test_bins: dict[str, Path], busybox: Path
) -> None:
    """Part B: Full end-to-end synthetic CMU lifecycle on REAL ARMv7 -nostdlib svc 0 ELFs."""
    print("=== Part B: Full End-to-End ARMv7 Synthetic CMU Lifecycle ===")
    chroot = work / "chroot-b"
    chroot_tmp = chroot / "tmp"
    chroot.mkdir(mode=0o755)
    populate_busybox(chroot, busybox)
    mount_tmpfs(chroot_tmp, size="32M")

    try:
        ram = chroot / "tmp/open-connect"
        usb_sess = ram / "sessions/session-usb100"
        data_parent = chroot / "tmp/mnt/data_persist"
        data = data_parent / "open-connect"
        for d in (
            ram,
            usb_sess,
            data_parent,
            chroot / "proc/self",
            chroot / "proc/sys/kernel/random",
            chroot / "sys/class/gpio/ACC_Sense",
            chroot / "sys/class/nvram/nv-config/keys",
            chroot / "dev",
            chroot / "etc/ssh",
            chroot / "jci/sm",
            chroot / "jci/scripts",
            chroot / "jci/mmui/uia",
            chroot / "jci/gui/apps/system/js",
            chroot / "jci/gui/apps/syssettings/js",
            chroot / "jci/gui/framework/js",
            chroot / "jci/gui/common/js",
            chroot / "jci/lib",
            chroot / "jci/vbs/modules",
            chroot / "jci/devicemanager",
            chroot / "jci/lvds",
            chroot / "jci/vui/plugins",
            chroot / "jci/devices",
            chroot / "config/common/log",
        ):
            d.mkdir(parents=True, exist_ok=True)
        for d in (ram, ram / "sessions", usb_sess):
            d.chmod(0o700)

        (chroot / "dev/urandom").write_bytes(os.urandom(8192))
        (chroot / "proc/uptime").write_text("120.50 10.00\n")
        (chroot / "proc/sys/kernel/random/boot_id").write_text(BOOT1 + "\n")
        (chroot / "proc/self/mounts").write_text(
            "rootfs / rootfs rw 0 0\n"
            "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
        )
        (chroot / "proc/mounts").symlink_to("self/mounts")
        (chroot / "sys/class/gpio/ACC_Sense/value").write_text("1\n")
        for ctl in ("add", "remove", "commit"):
            (chroot / "sys/class/nvram/nv-config" / ctl).write_text("")
        (chroot / "jci/version.ini").write_text(
            'JCI_SW_VER="MAZ_CMU-150_74.00.324"\nJCI_SW_VER_PATCH="A"\nJCI_SW_FLAVOR="cmu150_NA"\n'
        )
        (ram / "lock").write_bytes(b"")
        (ram / "lock").chmod(0o600)
        (ram / "usb-runtime").symlink_to("/tmp/open-connect/sessions/session-usb100")

        autostart_bytes = (
            b"#!/bin/sh\n"
            b"if true; then\n"
            b"        echo $MESSAGE_NORMALMODE\n"
            b"                sleep 1\n"
            b"                $(/jci/scripts/get_board_type.sh)\n"
            b"fi\n"
        )
        sm_normal = stock_sm(False)
        sm_wcp = stock_sm(True)
        index_html = (
            b"<!DOCTYPE html>\n<html>\n<head>\n"
            b'  <script type="text/javascript" src="common/js/logDefaults.js"></script>\n'
            b"</head>\n<body>\n"
            b"  <!-- stock comment -->\n"
            b"  <script>\n"
            b"  var baseApp = new BaseApp(); // trailing\n"
            b"  framework.init();\n"
            b"  </script>\n"
            b"</body>\n</html>\n"
        )
        mmui_xml = (ROOT / "tests/fixtures/ui-profile.xml").read_bytes()
        vui_xml = b'<vui><PluginsFolder value="/jci/vui/plugins"/></vui>\n'
        uia_so = bytes(674047)
        mmui_so = bytes(20000)
        vui_so = bytearray(95537)
        vui_so[68196 : 68196 + 24] = b"/jci/vui/vui_config.xml\x00"
        vui_so_bytes = bytes(vui_so)
        vui_path_blob = (release_dir / "vui-path.bin").read_bytes()
        vui_expected = bytearray(vui_so_bytes)
        vui_expected[68196 : 68196 + 24] = vui_path_blob

        stock_files = {
            "originals/autostart": ("usr/bin/autostart", autostart_bytes, 0o755),
            "root/sm.conf": ("jci/sm/sm.conf", sm_normal, 0o644),
            "root/sm_WCP.conf": ("jci/sm/sm_WCP.conf", sm_wcp, 0o644),
            "root/board.sh": ("jci/scripts/get_board_type.sh", b"#!/bin/sh\nexit 1\n", 0o755),
            "root/mmui.so": ("jci/mmui/svcjcimmui.so", mmui_so, 0o755),
            "root/mmui.xml": ("jci/mmui/mmui_config.xml", mmui_xml, 0o644),
            "root/uia.so": ("jci/mmui/uia/libjciuiasystem.so", uia_so, 0o755),
            "root/index.html": ("jci/gui/index.html", index_html, 0o644),
            "root/system-app.js": ("jci/gui/apps/system/js/systemApp.js", b"// sys\n", 0o644),
            "root/settings-app.js": (
                "jci/gui/apps/syssettings/js/syssettingsApp.js",
                b"// set\n",
                0o644,
            ),
            "root/base-app.js": ("jci/gui/framework/js/BaseApp.js", b"// base\n", 0o644),
            "root/manager.so": ("jci/lib/libjciuiamgr.so", b"stock manager\n", 0o755),
            "root/device-master.xml": ("etc/devmgr_config_master.xml", b"<dm/>\n", 0o644),
            "root/eem.so": ("jci/vbs/modules/libjcimod_eem.so", b"eem\n", 0o755),
            "root/device-manager.so": ("jci/devicemanager/libdevicemanager.so", b"devmgr\n", 0o755),
            "root/rungetty": ("usr/bin/rungetty", b"rungetty\n", 0o755),
            "root/sshd": ("usr/sbin/sshd", b"#!/bin/sh\nexit 0\n", 0o755),
            "root/ssh-keygen": ("usr/bin/ssh-keygen", b"ssh-keygen\n", 0o755),
            "root/framework.js": ("jci/gui/framework/js/GuiFramework.js", b"// fw\n", 0o644),
            "root/lvds-service": ("jci/lvds/lvds_service", b"lvds\n", 0o755),
            "root/runlogin": ("usr/bin/runlogin", b"stock runlogin\n", 0o755),
            "base/settings.txt": (
                "config/common/log/settings.txt",
                b"COMMON_LOG_LEVEL=Info\n",
                0o644,
            ),
            "base/libjcicommon.so": ("jci/lib/libjcicommon.so", b"libjcicommon\n", 0o755),
            "base/log-defaults.js": ("jci/gui/common/js/logDefaults.js", b"// log\n", 0o644),
            "base/vui/vui.so": ("jci/vui/svcjcivui.so", vui_so_bytes, 0o755),
            "base/vui/vui.xml": ("jci/vui/vui_config.xml", vui_xml, 0o644),
            "touch/devices/svc": (
                "jci/devices/svc-com-jci-cpp-devices.so",
                b"devices svc\n",
                0o755,
            ),
            "touch/devices/lib": ("jci/lib/libjcidevices.so", b"devices lib\n", 0o755),
        }
        pin_lines = []
        for pin_key, (rel, content, mode) in stock_files.items():
            p = chroot / rel
            p.write_bytes(content)
            p.chmod(mode)
            pin_lines.append(f"{pin_key}={sha(content)}\n")
        (chroot / "etc/passwd").write_text("cmu:x:0:0:CMU:/home/cmu:/bin/sh\n")
        (chroot / "etc/passwd").chmod(0o644)
        (chroot / "etc/ssh/sshd_config").write_text(
            "Port 36000\n"
            "AuthorizedKeysFile /config-mfg/authorized_keys /owner/keys.%u\n"
            "PasswordAuthentication no\n"
        )
        (chroot / "etc/ssh/sshd_config").chmod(0o644)
        mgr_sha = sha(b"stock manager\n")
        pin_lines.append(f"originals/mmui.xml={sha(mmui_xml)}\n")
        pin_lines.append(f"manager.so={mgr_sha}\n")
        pin_lines.append(f"composed/vui.so={sha(bytes(vui_expected))}\n")
        (chroot / "etc/oc-test-pins").write_text("".join(pin_lines))
        (chroot / "etc/oc-test-pins").chmod(0o644)
        orig_runlogin_ino = (chroot / "usr/bin/runlogin").stat().st_ino

        # Populate USB session from real release bundle, swapping in ARMv7 OC_TEST_PINFILE binaries.
        version = (ASSETS / "VERSION").read_text().strip()
        usb_src = release_dir / f"usb/open-connect-{version}-usb/open-connect"
        for p in usb_src.iterdir():
            if p.name == "files.sha256":
                continue
            dst = usb_sess / p.name
            if p.name in test_bins:
                shutil.copyfile(test_bins[p.name], dst)
                dst.chmod(0o700)
            else:
                shutil.copyfile(p, dst)
                dst.chmod(0o700 if p.name in ("flush", "ignition") else 0o600)
        mf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb_sess.iterdir()))
        (usb_sess / "files.sha256").write_text(mf)
        (usb_sess / "files.sha256").chmod(0o600)
        (usb_sess / "token").write_text(TOKEN_USB + "\n")
        (usb_sess / "token").chmod(0o600)

        # B1. Cold USB install over real HTTP `tcpsvd` -> ARMv7 `api` -> ARMv7 `install`.
        usb_port = pick_port()
        usb_srv = subprocess.Popen(
            [
                "chroot",
                str(chroot),
                "/bin/busybox",
                "tcpsvd",
                "127.0.0.1",
                str(usb_port),
                "/tmp/open-connect/sessions/session-usb100/api",
                "/tmp/open-connect/sessions/session-usb100/token",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_port(usb_port)
            st, _, raw = http_control(usb_port, TOKEN_USB, "-|install|-|-|-")
            assert st == 200, (st, raw)
            res = json.loads(raw)
            assert res.get("ok") is True and res.get("installed") is True, res
            assert res["touch"] == 1 and res["warning"] == 1 and res["base"] == 0, res
            assert res["carplayAutoshow"] == 0, res
            rec = (data / "record").read_text().strip().split("|")
            assert rec[1] == "active" and rec[9] == "3" and rec[12] == "installed", rec
            assert "open-connect-boot-select" in (chroot / "usr/bin/autostart").read_text()
            assert (chroot / "usr/bin/open-connect-boot-select").is_file()
            assert (
                chroot / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
            ).read_text().strip() == "disable"
            assert (
                "/dev/ffx01p1 / relfs ro,noatime 0 0" in (chroot / "proc/self/mounts").read_text()
            )
            pkg1, snap1 = rec[3], rec[5]
            print(f"  [B1] Cold ARMv7 USB install OK (pkg={pkg1[:8]}, snap={snap1[:8]})")
        finally:
            stop_proc(usb_srv)

        # B2. Simulated Boot #1: fresh tmpfs -> ARMv7 `/usr/bin/open-connect-boot-select select /`.
        for child in list(ram.iterdir()):
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        (chroot / "proc/sys/kernel/random/boot_id").write_text(BOOT2 + "\n")
        (chroot / "dev/urandom").write_bytes(os.urandom(8192))
        r_bs = chroot_run(chroot, ["/usr/bin/open-connect-boot-select", "select"])
        assert r_bs.returncode == 0, (
            f"boot-select failed ({r_bs.returncode}): {r_bs.stdout}{r_bs.stderr}"
        )
        assert (ram / "selected").read_text().strip() == snap1
        assert (ram / "feature/index.html").is_file()
        assert (ram / "feature/sm.conf").is_file()
        assert (ram / "ignition/ignition").is_file()
        rec_b1 = (data / "record").read_text().strip().split("|")
        assert rec_b1[9] == "2", f"expected budget 3->2, got {rec_b1[9]}"
        print(
            "  [B2] Boot #1 ARMv7 open-connect-boot-select select OK (budget 3->2, feature+ignition staged)"
        )

        # B3. Live Settings HTTP `/control` on 127.0.0.1 -> ARMv7 `api` (8-file Settings session!).
        set_sess = ram / "sessions/session-set100"
        set_sess.mkdir(parents=True, mode=0o700)
        (ram / "sessions").chmod(0o700)
        for nm in (
            "files.sha256",
            "service.sh",
            "console.sh",
            "VERSION",
            "api",
            "flush",
            "runtime.js",
            "dialog.js",
            "settings.js",
        ):
            shutil.copyfile(data / "packages" / pkg1 / nm, set_sess / nm)
            (set_sess / nm).chmod(0o700 if nm in ("api", "flush") else 0o600)
        (set_sess / "token").write_text(TOKEN_SET + "\n")
        (set_sess / "token").chmod(0o600)
        (ram / "runtime").symlink_to("/tmp/open-connect/sessions/session-set100")

        set_port = pick_port()
        set_srv = subprocess.Popen(
            [
                "chroot",
                str(chroot),
                "/bin/busybox",
                "tcpsvd",
                "127.0.0.1",
                str(set_port),
                "/tmp/open-connect/sessions/session-set100/api",
                "/tmp/open-connect/sessions/session-set100/token",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_port(set_port)
            st, _, raw = http_control(set_port, TOKEN_SET, "-|status|settings|-|-")
            assert st == 200 and json.loads(raw)["ok"] is True, (st, raw)
            rev = json.loads(raw)["revision"]
            assert rev == snap1

            # Fast path: touch 1 -> 0 -> 1
            (chroot / "dev/urandom").write_bytes(os.urandom(8192))
            st, _, raw = http_control(set_port, TOKEN_SET, f"{rev}|set|touch|1|0")
            r_t0 = json.loads(raw)
            assert st == 200 and r_t0["ok"] is True and r_t0["touch"] == 0, r_t0
            assert not (chroot / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
            rev = r_t0["revision"]

            (chroot / "dev/urandom").write_bytes(os.urandom(8192))
            st, _, raw = http_control(set_port, TOKEN_SET, f"{rev}|set|touch|0|1")
            r_t1 = json.loads(raw)
            assert st == 200 and r_t1["ok"] is True and r_t1["touch"] == 1, r_t1
            assert (
                chroot / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
            ).read_text().strip() == "disable"
            rev = r_t1["revision"]

            # Fast path: carplay-autoshow 0 -> 1
            (chroot / "dev/urandom").write_bytes(os.urandom(8192))
            st, _, raw = http_control(set_port, TOKEN_SET, f"{rev}|set|carplay-autoshow|0|1")
            r_cp = json.loads(raw)
            assert st == 200 and r_cp["ok"] is True and r_cp["carplayAutoshow"] == 1, r_cp
            rev = r_cp["revision"]

            # Root-publish path: uart 0 -> 1 -> 0 (verifying hardlink hold & stock inode preserved!)
            (chroot / "dev/urandom").write_bytes(os.urandom(8192))
            st, _, raw = http_control(set_port, TOKEN_SET, f"{rev}|set|uart|0|1")
            r_u1 = json.loads(raw)
            assert st == 200 and r_u1["ok"] is True and r_u1["uart"] == 1, r_u1
            assert (chroot / "usr/bin/runlogin").stat().st_ino != orig_runlogin_ino
            assert (chroot / f"usr/bin/.open-connect-runlogin-{orig_runlogin_ino}").exists()
            rev = r_u1["revision"]

            (chroot / "dev/urandom").write_bytes(os.urandom(8192))
            st, _, raw = http_control(set_port, TOKEN_SET, f"{rev}|set|uart|1|0")
            r_u0 = json.loads(raw)
            assert st == 200 and r_u0["ok"] is True and r_u0["uart"] == 0, r_u0
            assert (chroot / "usr/bin/runlogin").stat().st_ino == orig_runlogin_ino
            rev = r_u0["revision"]
            assert (
                "/dev/ffx01p1 / relfs ro,noatime 0 0" in (chroot / "proc/self/mounts").read_text()
            )
            print(
                "  [B3] Live Settings HTTP /control OK (status, touch 1->0->1, autoshow, uart 0->1->0, inode preserved)"
            )
        finally:
            stop_proc(set_srv)

        # B4. Slow-path ARMv7 `install --boot-recover` (budget=0 NVRAM revert + D/reseal).
        def clean_ram_for_boot(boot_uuid: str) -> None:
            for child in list(ram.iterdir()):
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            (chroot / "proc/sys/kernel/random/boot_id").write_text(boot_uuid + "\n")
            (chroot / "dev/urandom").write_bytes(os.urandom(8192))

        clean_ram_for_boot(BOOT3)
        rec_b4 = (data / "record").read_text().strip().split("|")
        rec_b4[9] = "0"
        (data / "record").write_text("|".join(rec_b4) + "\n")
        rec_exec = ram / ".recover-b4"
        rec_exec.mkdir(mode=0o700)
        shutil.copyfile(data / "packages" / pkg1 / "install", rec_exec / "install")
        (rec_exec / "install").chmod(0o700)
        r_br = chroot_run(
            chroot,
            [
                "/tmp/open-connect/.recover-b4/install",
                "--boot-recover",
                f"/tmp/mnt/data_persist/open-connect/packages/{pkg1}",
                "/tmp/open-connect/.recover-b4",
            ],
        )
        assert r_br.returncode == 0, f"boot-recover budget=0 failed: {r_br.stdout}{r_br.stderr}"
        assert not (chroot / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
        # With budget=0, boot-select must return OC_STOCK (2) so the CMU boots stock safely.
        r_bs2 = chroot_run(chroot, ["/usr/bin/open-connect-boot-select", "select"])
        assert r_bs2.returncode == 2, f"expected OC_STOCK (2) at budget=0, got {r_bs2.returncode}"

        # ACC-off recorded on previous boot + ACC=1 now -> boot-recover replenishes NVRAM & budget!
        rec_acc = (data / "record").read_text().strip().split("|")
        rec_acc[10] = BOOT3
        (data / "record").write_text("|".join(rec_acc) + "\n")
        clean_ram_for_boot("42345678-1234-1234-1234-123456789abc")
        rec_exec = ram / ".recover-acc"
        rec_exec.mkdir(mode=0o700)
        shutil.copyfile(data / "packages" / pkg1 / "install", rec_exec / "install")
        (rec_exec / "install").chmod(0o700)
        r_acc = chroot_run(
            chroot,
            [
                "/tmp/open-connect/.recover-acc/install",
                "--boot-recover",
                f"/tmp/mnt/data_persist/open-connect/packages/{pkg1}",
                "/tmp/open-connect/.recover-acc",
            ],
        )
        assert r_acc.returncode == 0, (
            f"boot-recover ACC replenish failed: {r_acc.stdout}{r_acc.stderr}"
        )
        assert (
            chroot / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        ).read_text().strip() == "disable"
        r_bs_acc = chroot_run(chroot, ["/usr/bin/open-connect-boot-select", "select"])
        assert r_bs_acc.returncode == 0, (
            f"boot-select after ACC replenish failed: {r_bs_acc.returncode}"
        )

        # D/reseal hint -> recheck + reseal + unlink D/reseal -> boot-select succeeds.
        rec_rs = (data / "record").read_text().strip().split("|")
        clean_ram_for_boot("52345678-1234-1234-1234-123456789abc")
        rec_exec = ram / ".recover-rs"
        rec_exec.mkdir(mode=0o700)
        shutil.copyfile(data / "packages" / pkg1 / "install", rec_exec / "install")
        (rec_exec / "install").chmod(0o700)
        (data / "reseal").write_text(rec_rs[5] + "\n")
        (data / "reseal").chmod(0o600)
        r_br2 = chroot_run(
            chroot,
            [
                "/tmp/open-connect/.recover-rs/install",
                "--boot-recover",
                f"/tmp/mnt/data_persist/open-connect/packages/{pkg1}",
                "/tmp/open-connect/.recover-rs",
            ],
        )
        assert r_br2.returncode == 0, f"boot-recover reseal failed: {r_br2.stdout}{r_br2.stderr}"
        assert not (data / "reseal").exists()
        r_bs3 = chroot_run(chroot, ["/usr/bin/open-connect-boot-select", "select"])
        assert r_bs3.returncode == 0, f"boot-select after reseal failed: {r_bs3.returncode}"
        print("  [B4] Slow-path ARMv7 install --boot-recover OK (budget=0 NVRAM revert + D/reseal)")

        # B5. Full USB uninstall over HTTP -> restores stock autostart, removes boot-select & data!
        cur_rev = (data / "record").read_text().strip().split("|")[5]
        usb_sess2 = ram / "sessions/session-usb200"
        usb_sess2.mkdir(parents=True, mode=0o700)
        (ram / "sessions").chmod(0o700)
        for p in (data / "packages" / pkg1).iterdir():
            dst = usb_sess2 / p.name
            shutil.copyfile(p, dst)
            dst.chmod(
                0o700 if p.name in ("api", "install", "flush", "boot-select", "ignition") else 0o600
            )
        (usb_sess2 / "token").write_text(TOKEN_USB + "\n")
        (usb_sess2 / "token").chmod(0o600)
        (ram / "usb-runtime").symlink_to("/tmp/open-connect/sessions/session-usb200")

        un_port = pick_port()
        un_srv = subprocess.Popen(
            [
                "chroot",
                str(chroot),
                "/bin/busybox",
                "tcpsvd",
                "127.0.0.1",
                str(un_port),
                "/tmp/open-connect/sessions/session-usb200/api",
                "/tmp/open-connect/sessions/session-usb200/token",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_port(un_port)
            (chroot / "dev/urandom").write_bytes(os.urandom(8192))
            st, _, raw = http_control(un_port, TOKEN_USB, f"{cur_rev}|uninstall|-|-|-")
            assert st == 200, (st, raw)
            r_un = json.loads(raw)
            assert r_un.get("ok") is True and r_un.get("installed") is False, r_un
            assert not data.exists()
            assert not (chroot / "usr/bin/open-connect-boot-select").exists()
            assert (chroot / "usr/bin/autostart").read_bytes() == autostart_bytes
            assert not (chroot / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
            assert (
                "/dev/ffx01p1 / relfs ro,noatime 0 0" in (chroot / "proc/self/mounts").read_text()
            )
            print(
                "  [B5] Full ARMv7 USB uninstall OK (stock autostart restored, boot-select & data removed)"
            )
        finally:
            stop_proc(un_srv)
    finally:
        umount_quiet(chroot_tmp)


def main() -> int:
    if sys.platform != "linux":
        print("run_arm_qemu.py requires Linux", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        print("run_arm_qemu.py requires root (for tmpfs mount & chroot)", file=sys.stderr)
        return 2

    qemu = find_qemu_arm()
    busybox = find_busybox()

    with binfmt_arm(qemu), tempfile.TemporaryDirectory(prefix="oc-arm-qemu-") as td:
        work = Path(td).resolve()
        release_dir = work / "release"
        print("=== Building unmodified `make release` ARMv7 binaries ===")
        env = {**os.environ}
        if shutil.which("ld.lld") and "OC_LLD" not in env:
            env["OC_LLD"] = shutil.which("ld.lld")
        mk = subprocess.run(
            ["make", "release", f"OUT={release_dir}"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if mk.returncode != 0:
            print(mk.stdout + mk.stderr, file=sys.stderr)
            return 1

        part_a_unmodified_release(work, release_dir, busybox)
        test_bins = build_arm_test_bins(work / "arm-test-bins")
        part_b_full_lifecycle(work, release_dir, test_bins, busybox)

    print("ALL ARMv7 qemu-arm + BusyBox + tmpfs checks PASSED!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
