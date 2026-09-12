#!/usr/bin/env python3
"""Pull xiaojianbang custom-system unpack output and merge .dex/.bin with dexfixer.jar.

On the xiaojianbang custom system, creating `/data/local/tmp/<pkgName>/` only
ENABLES extract-mode unpacking. The actual artifacts are written under the app's
private dir:

  /data/data/<pkgName>/xiaojianbang/
    *.dex  - unpacked dex
    *.txt  - class names recorded for each dex
    *.bin  - method-body data for each dex

That dir is owned by the app uid and unreadable by the shell user, so batch mode
first copies it to /sdcard via `su` and then adb-pulls from there.

dexfixer.jar merges a .dex with its matching .bin into a complete dex:

  java -jar dexfixer.jar <dexpath> <binpath> <outpath>

This wrapper has two modes:

  batch (default): copy the device unpack dir to sdcard, pull it, pair every
                   <stem>.dex with its <stem>.bin, and run dexfixer.jar per pair.
  single:          merge one local dex+bin pair (use --dex/--bin/--out), no adb.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent


def find_project_root(start: pathlib.Path) -> pathlib.Path:
    for path in [start, *start.parents]:
        if (path / "third_party").exists() or (path / "AGENTS.md").exists():
            return path
    return pathlib.Path.cwd().resolve()


PROJECT_ROOT = find_project_root(SCRIPT_DIR)


def choose_dexfixer_jar() -> pathlib.Path:
    override = os.environ.get("XJB_DEXFIXER_JAR")
    if override:
        return pathlib.Path(override).expanduser()
    candidates = [
        PROJECT_ROOT / "third_party" / "dexfixer" / "dexfixer.jar",
        SCRIPT_DIR / "dexfixer" / "dexfixer.jar",
        SCRIPT_DIR / "tools" / "dexfixer" / "dexfixer.jar",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def choose_adb() -> str:
    override = os.environ.get("XJB_ADB") or os.environ.get("ADB")
    if override:
        return override
    candidates = [
        PROJECT_ROOT / "third_party" / "aosp" / "platform-tools" / "adb",
        PROJECT_ROOT / "third_party" / "aosp" / "platform-tools" / "adb.exe",
        PROJECT_ROOT / "third_party" / "platform-tools" / "adb",
        PROJECT_ROOT / "third_party" / "platform-tools" / "adb.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("adb") or "adb"


def choose_java() -> str:
    override = os.environ.get("XJB_JAVA") or os.environ.get("JAVA")
    if override:
        return override
    return shutil.which("java") or "java"


ADB = choose_adb()
JAVA = choose_java()
DEXFIXER_JAR = choose_dexfixer_jar()


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=False, text=True, **kwargs)


def adb(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run([ADB, *args], **kwargs)


def adb_su(command: str, **kwargs) -> subprocess.CompletedProcess:
    return adb("shell", f"su -c {shell_quote(command)}", **kwargs)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def merge_pair(dex: pathlib.Path, binf: pathlib.Path, out: pathlib.Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    result = run(
        [JAVA, "-jar", str(DEXFIXER_JAR), str(dex), str(binf), str(out)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        print(f"[-] dexfixer failed for {dex.name} (rc={result.returncode})", file=sys.stderr)
        return result.returncode
    if not out.exists():
        print(f"[-] dexfixer reported success but output missing: {out}", file=sys.stderr)
        return 1
    print(f"[fixed] {out} size={out.stat().st_size}", flush=True)
    return 0


def pull_unpack_dir(package: str, device_dir: str, local_dir: pathlib.Path) -> int:
    local_dir.mkdir(parents=True, exist_ok=True)
    # The unpack dir lives under /data/data/<pkg>/ (owned by the app uid), which
    # the shell user cannot read directly. Copy it to sdcard first, then adb pull.
    staging = f"/sdcard/xjb_dexfix_pull/{package}"
    adb_su(f"rm -rf {shell_quote(staging)}; mkdir -p {shell_quote(staging)}")
    copy = adb_su(
        f"cp -a {shell_quote(device_dir + '/.')} {shell_quote(staging)}/ 2>/dev/null",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(copy.stdout, end="")
    print(copy.stderr, end="", file=sys.stderr)
    pulled = adb("pull", staging + "/.", str(local_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(pulled.stdout, end="")
    print(pulled.stderr, end="", file=sys.stderr)
    adb_su(f"rm -rf {shell_quote(staging)}", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return pulled.returncode


def batch_merge(src_dir: pathlib.Path, out_dir: pathlib.Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    dex_files = sorted(src_dir.rglob("*.dex"))
    if not dex_files:
        print(f"[-] no .dex files found under {src_dir}", file=sys.stderr)
        return 1

    total = 0
    merged = 0
    skipped_no_bin = []
    failed = []
    for dex in dex_files:
        total += 1
        binf = dex.with_suffix(".bin")
        if not binf.exists():
            skipped_no_bin.append(dex)
            print(f"[skip] no matching .bin for {dex.name}; not an extract-mode dex?", flush=True)
            continue
        out = out_dir / (dex.stem + ".fixed.dex")
        rc = merge_pair(dex, binf, out)
        if rc == 0:
            merged += 1
        else:
            failed.append(dex)

    print("---- dexfix summary ----", flush=True)
    print(f"dex_total={total} merged={merged} no_bin={len(skipped_no_bin)} failed={len(failed)}", flush=True)
    print(f"output_dir={out_dir}", flush=True)
    if skipped_no_bin:
        print("no_bin:", ", ".join(p.name for p in skipped_no_bin), flush=True)
    if failed:
        print("failed:", ", ".join(p.name for p in failed), flush=True)
        return 1
    return 0 if merged else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--package", help="Target package; device unpack dir defaults to /data/data/<package>/xiaojianbang.")
    parser.add_argument("--device-dir", default=None, help="Override device unpack dir. Defaults to /data/data/<package>/xiaojianbang.")
    parser.add_argument("--out-dir", type=pathlib.Path, default=None, help="Local output dir for merged dex.")
    parser.add_argument("--src-dir", type=pathlib.Path, default=None, help="Local dir already containing .dex/.bin; skips adb pull.")
    parser.add_argument("--no-pull", action="store_true", help="Do not pull from device; use --src-dir as-is.")
    # single-pair mode
    parser.add_argument("--dex", type=pathlib.Path, default=None, help="Single mode: one local .dex.")
    parser.add_argument("--bin", dest="binf", type=pathlib.Path, default=None, help="Single mode: matching .bin.")
    parser.add_argument("--out", type=pathlib.Path, default=None, help="Single mode: merged output dex path.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if not DEXFIXER_JAR.exists():
        print(f"[-] dexfixer.jar not found: {DEXFIXER_JAR}", file=sys.stderr)
        print("    Set XJB_DEXFIXER_JAR=/path/to/dexfixer.jar if needed.", file=sys.stderr)
        return 2
    java_path = pathlib.Path(JAVA)
    java_ok = shutil.which(JAVA) is not None or (java_path.is_file() and os.access(java_path, os.X_OK))
    if not java_ok:
        print(f"[-] java not found or not executable: {JAVA}; install a JRE/JDK or set XJB_JAVA.", file=sys.stderr)
        return 2

    print(f"DEXFIXER_JAR={DEXFIXER_JAR}", flush=True)
    print(f"JAVA={JAVA}", flush=True)

    # Single-pair mode
    if args.dex or args.binf or args.out:
        if not (args.dex and args.binf and args.out):
            print("[-] single mode requires --dex, --bin and --out together", file=sys.stderr)
            return 2
        if not args.dex.exists():
            print(f"[-] dex not found: {args.dex}", file=sys.stderr)
            return 2
        if not args.binf.exists():
            print(f"[-] bin not found: {args.binf}", file=sys.stderr)
            return 2
        return merge_pair(args.dex.expanduser().resolve(), args.binf.expanduser().resolve(), args.out.expanduser().resolve())

    # Batch mode
    out_dir = (args.out_dir or (pathlib.Path.cwd() / "artifacts" / "dexfix")).expanduser().resolve()

    if args.no_pull or args.src_dir:
        src_dir = (args.src_dir or out_dir).expanduser().resolve()
        if not src_dir.is_dir():
            print(f"[-] src dir not found: {src_dir}", file=sys.stderr)
            return 2
        print(f"SRC_DIR={src_dir}", flush=True)
        return batch_merge(src_dir, out_dir)

    if not args.package:
        print("[-] batch mode requires --package (or use --src-dir/--no-pull, or single mode)", file=sys.stderr)
        return 2

    device_dir = args.device_dir or f"/data/data/{args.package}/xiaojianbang"
    pull_dir = out_dir / "pulled"
    print(f"ADB={ADB}", flush=True)
    print(f"DEVICE_DIR={device_dir}", flush=True)
    print(f"PULL_DIR={pull_dir}", flush=True)

    rc = pull_unpack_dir(args.package, device_dir, pull_dir)
    if rc != 0:
        print(f"[-] adb pull failed (rc={rc}); check device dir and root/su", file=sys.stderr)
        return rc

    return batch_merge(pull_dir, out_dir)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
