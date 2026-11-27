"""Shared cached host-binary builder for offline tests.

Compiles unmodified target C sources once per cache directory (using atomic
rename so parallel workers and threads share binaries safely) instead of
invoking clang inside every test method's setUp().
"""

import atexit
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
_LOCAL_CACHE: Path | None = None
_LOCAL_CACHE_PID: int | None = None


def _cleanup_local_cache(path: Path, creator_pid: int) -> None:
    if os.getpid() == creator_pid:
        shutil.rmtree(path, ignore_errors=True)


def _cache_dir() -> Path:
    global _LOCAL_CACHE, _LOCAL_CACHE_PID
    env_dir = os.environ.get("OC_HOST_BIN_CACHE")
    if env_dir:
        path = Path(env_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    pid = os.getpid()
    if _LOCAL_CACHE is None or _LOCAL_CACHE_PID != pid or not _LOCAL_CACHE.is_dir():
        _LOCAL_CACHE = Path(tempfile.mkdtemp(prefix="oc-host-bins-")).resolve()
        _LOCAL_CACHE_PID = pid
        atexit.register(_cleanup_local_cache, _LOCAL_CACHE, pid)
    return _LOCAL_CACHE


def _build_cached(
    name: str,
    sources: list[Path],
    flags: list[str],
    *,
    extra_deps: list[Path] | tuple[Path, ...] = (),
) -> Path:
    digest = hashlib.sha256()
    digest.update("\0".join(flags).encode())
    for src in (*sources, *extra_deps):
        digest.update(b"\0")
        digest.update(str(src).encode())
        digest.update(b"\0")
        digest.update(src.read_bytes())
    key = digest.hexdigest()[:16]
    cache = _cache_dir()
    target = cache / f"{name}-{key}"
    if target.is_file():
        return target
    fd, tmp_name = tempfile.mkstemp(prefix=f".{name}-{key}-", dir=cache)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        result = subprocess.run(
            ["clang", *flags, *(str(s) for s in sources), "-o", str(tmp)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"clang failed building {name} (exit {result.returncode}):\n"
                f"{result.stdout}{result.stderr}"
            )
        tmp.chmod(0o700)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return target


def host_flush() -> Path:
    """Return cached host-compiled flush binary."""
    return _build_cached(
        "flush",
        [ROOT / "cmu/startup/flush.c"],
        ["-DOC_HOST"],
        extra_deps=[ASSETS / "boot-hash.h"],
    )


def copy_host_flush(dest: Path) -> Path:
    """Copy cached host flush binary to dest with mode 0700."""
    shutil.copyfile(host_flush(), dest)
    dest.chmod(0o700)
    return dest


def host_boot_select(*, extra_flags: tuple[str, ...] = ()) -> Path:
    """Return cached ASan+UBSan host-compiled boot-select binary."""
    core_dir = ASSETS / "core"
    core_srcs = sorted(p for p in core_dir.glob("*.c") if p.name != "oc-api.c")
    headers = sorted(core_dir.glob("*.h"))
    flags = [
        "-DOC_HOST",
        "-D_GNU_SOURCE",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-O2",
        "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer",
        *extra_flags,
    ]
    return _build_cached(
        "boot-select", [ASSETS / "boot-select.c", *core_srcs], flags, extra_deps=headers
    )


def copy_host_boot_select(dest: Path) -> Path:
    """Copy cached host boot-select binary to dest with mode 0700."""
    shutil.copyfile(host_boot_select(), dest)
    dest.chmod(0o700)
    return dest


def host_api() -> Path:
    """Return cached ASan+UBSan host-compiled api binary."""
    core_dir = ASSETS / "core"
    api_core = [
        core_dir / name
        for name in (
            "oc-hash.c",
            "oc-io.c",
            "oc-manifest.c",
            "oc-record.c",
            "oc-config.c",
            "oc-guard.c",
            "oc-api.c",
        )
    ]
    headers = sorted(core_dir.glob("*.h"))
    flags = [
        "-DOC_HOST",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer",
    ]
    return _build_cached("api", [ASSETS / "api.c", *api_core], flags, extra_deps=headers)


def copy_host_api(dest: Path) -> Path:
    """Copy cached host api binary to dest with mode 0700."""
    shutil.copyfile(host_api(), dest)
    dest.chmod(0o700)
    return dest


def host_ignition() -> Path:
    """Return cached ASan+UBSan host-compiled ignition binary."""
    core_dir = ASSETS / "core"
    ig_core = [core_dir / name for name in ("oc-hash.c", "oc-io.c", "oc-manifest.c", "oc-record.c")]
    headers = sorted(core_dir.glob("*.h"))
    flags = [
        "-DOC_HOST",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer",
    ]
    return _build_cached("ignition", [ASSETS / "ignition.c", *ig_core], flags, extra_deps=headers)


def copy_host_ignition(dest: Path) -> Path:
    """Copy cached host ignition binary to dest with mode 0700."""
    shutil.copyfile(host_ignition(), dest)
    dest.chmod(0o700)
    return dest
