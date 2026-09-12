#!/usr/bin/env python3
"""Export rizin analysis inputs from an ELF/Android .so into an AI-ready directory.

This is the rizin-based counterpart of the IDA ``INP.py`` exporter for the
xiaojianbang-auto-reverse workflow. It writes machine-readable analysis input
(disassembly, strings, imports/exports, symbols, sections, xrefs, function
list) plus, when a Ghidra headless decompiler is available, pseudo-C so the
workflow can analyze native code without IDA. Output lands in a caller-chosen
``<out_dir>`` directory mirroring the ``artifacts/inp/<module>_export_for_ai``
convention.

rizin at this install has no decompiler plugin (``pdc``/``pdg`` are absent), so
pseudo-C is produced by an optional Ghidra ``analyzeHeadless`` invocation; when
Ghidra is not found the script writes a note and emits disassembly only. The
workflow treats disassembly as authoritative and pseudo-C as an aid to be
cross-checked against the disassembly.

Only rizin/rz-bin on PATH (or given by ``--rizin``/``--rz-bin``) is required.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_DECOMP_SUBDIR = "ghidra_pseudocode"


def run(cmd: list[str], *, timeout: int | None = 300) -> subprocess.CompletedProcess[str]:
    """Run a command capturing UTF-8 text output. Never uses a shell."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def json_from(cmd: list[str]) -> object | None:
    """Run a command expecting JSON on stdout; return parsed value or None."""
    proc = run(cmd)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def resolve_tool(name: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which(name)
    if found:
        return found
    sys.exit(f"[rizin_export] {name} not found on PATH; pass --{name.replace('rz-', 'rz_')} or add it to PATH")


def export_rzbin(rz_bin: str, target: Path, out: Path) -> None:
    """Collect binary-level metadata with rz-bin as separate JSON files."""
    infos = {
        "info": ["-Ij"],
        "sections": ["-Sj"],
        "segments": ["-SSj"],
        "symbols": ["-sj"],
        "imports": ["-ij"],
        "strings": ["-zj"],
        "entry": ["-ej"],
    }
    for name, flags in infos.items():
        value = json_from([rz_bin, *flags, str(target)])
        if name == "strings":
            # rz-bin -zj returns a list of {string, ...}; keep only needed fields.
            if isinstance(value, list):
                value = [
                    {
                        "string": str(item.get("string", "")),
                        "offset": int(item.get("vaddr", item.get("offset", 0))),
                        "size": int(item.get("size", 0)),
                        "section": item.get("section"),
                    }
                    for item in value
                    if isinstance(item, dict)
                ]
        write_json(out / f"{name}.json", value)
    # Human-readable summary (single call, all info), best-effort.
    proc = run([rz_bin, "-gI", str(target)])
    write_text(out / "rzbin_info.txt", proc.stdout)


def export_rizin(rizin: str, target: Path, out: Path) -> None:
    """Analyze with rizin (-A) and emit function list and per-function disassembly/xrefs."""
    # Function list as JSON, best-effort.
    funcs = json_from([rizin, "-A", "-q", "-c", "aflj", str(target)])
    write_json(out / "functions.json", funcs)

    # Per-function disassembly and xrefs in a single text pass. This can be
    # large; it is the authoritative view and intentionally kept whole.
    if isinstance(funcs, list) and funcs:
        lines: list[str] = []
        for fn in funcs:
            if not isinstance(fn, dict):
                continue
            name = fn.get("name", "?")
            addr = fn.get("offset", fn.get("vaddr"))
            if addr is None:
                continue
            if not isinstance(addr, int):
                continue
            lines.append(f"\n==== function {name} @ {hex(addr)} ({fn.get('size', 0)} bytes) ====")
            dis = run([rizin, "-q", "-c", f"s {hex(addr)}; af; pdf", str(target)])
            lines.append(dis.stdout)
            xrefs = run([rizin, "-q", "-c", f"s {hex(addr)}; axt", str(target)])
            if xrefs.stdout.strip():
                lines.append("-- xrefs --")
                lines.append(xrefs.stdout)
        write_text(out / "disassembly.txt", "\n".join(lines))
    # A compact address-to-name map for downstream offset resolution.
    if isinstance(funcs, list):
        table = []
        for fn in funcs:
            if isinstance(fn, dict):
                table.append({
                    "name": fn.get("name"),
                    "offset": fn.get("offset", fn.get("vaddr")),
                    "size": fn.get("size"),
                })
        write_json(out / "functions_map.json", table)


def export_ghidra(ghidra_support: str, target: Path, out: Path, project_dir: Path) -> Path | None:
    """Run Ghidra headless to emit pseudo-C, if available; return decompiled dir or None."""
    import platform as _platform
    support = Path(ghidra_support)
    is_windows = _platform.system() == "Windows"
    # Windows must use the .bat launcher (cmd.exe); other platforms use the
    # extensionless shell script. Prefer .bat over a stray '.cmd' on Windows.
    names = (["analyzeHeadless.bat", "analyzeHeadless.cmd", "analyzeHeadless"] if is_windows
             else ["analyzeHeadless"])
    analyzer: Path | None = None
    for name in names:
        candidate = (support / name) if support.is_dir() else Path(name)
        if candidate.exists():
            analyzer = candidate
            break
    if analyzer is None:
        return None
    decomp_out = out / DEFAULT_DECOMP_SUBDIR
    decomp_out.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    if is_windows and str(analyzer).lower().endswith((".bat", ".cmd")):
        # Windows .bat requires cmd.exe /c. cmd treats a backslash as an escape,
        # so every path is converted to forward slashes (cmd does not escape '/').
        args = [str(analyzer), str(project_dir), "rizin_ghe",
                "-import", str(target), "-postScript", "DecompileHeadless.java",
                "-scriptPath", str(Path(__file__).resolve().parent / "rizin_export"), "-deleteProject"]
        args = [arg.replace("\\", "/") for arg in args]
        quoted = " ".join(f'"{arg}"' if (" " in arg or "(" in arg or ")" in arg) else arg for arg in args)
        cmd = ["cmd.exe", "/c", quoted]
    else:
        cmd = [
            str(analyzer),
            str(project_dir),
            "rizin_ghe",
            "-import", str(target),
            "-postScript", "DecompileHeadless.java",
            "-scriptPath", str(Path(__file__).resolve().parent / "rizin_export"),
            "-deleteProject",
        ]
    env = dict(os.environ)
    env["GHIDRA_DECOMP_OUT"] = str(decomp_out)
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", timeout=900, check=False, env=env,
    )
    note = decomp_out / "ghidra_run.txt"
    note.write_text(
        f"cmd: {json.dumps(cmd, ensure_ascii=False)}\n"
        f"returncode: {proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
        encoding="utf-8",
    )
    # index.txt presence is the success signal (DecompileHeadless writes it).
    return decomp_out if (decomp_out / "index.txt").exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="ELF / Android .so to analyze.")
    parser.add_argument("out_dir", help="Directory to write exported inputs into.")
    parser.add_argument("--rizin", help="rizin executable path (default: PATH 'rizin').")
    parser.add_argument("--rz-bin", dest="rz_bin", help="rz-bin executable path (default: PATH 'rz-bin').")
    parser.add_argument("--ghidra-support", help="Ghidra 'support' directory (contains analyzeHeadless).")
    parser.add_argument("--no-ghidra", action="store_true", help="Skip Ghidra pseudo-C even if available.")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.is_file():
        sys.exit(f"[rizin_export] target is not a file: {target}")
    out = Path(args.out_dir).resolve()

    rizin = resolve_tool("rizin", args.rizin)
    rz_bin = resolve_tool("rz-bin", args.rz_bin)

    # Basic metadata.
    meta = {
        "target": str(target),
        "rizin": shutil.which("rizin") or rizin,
        "rz_bin": shutil.which("rz-bin") or rz_bin,
        "tools_used": ["rizin", "rz-bin"] + (["ghidra_headless"] if args.ghidra_support and not args.no_ghidra else []),
    }
    write_json(out / "meta.json", meta)

    export_rzbin(rz_bin, target, out)
    export_rizin(rizin, target, out)

    if args.ghidra_support and not args.no_ghidra:
        project_dir = out / "_ghidra_project"
        decomp = export_ghidra(args.ghidra_support, target, out, project_dir)
        if decomp is not None:
            write_text(out / "pseudocode_note.txt", f"Ghidra pseudo-C written to {decomp}")
        else:
            write_text(out / "pseudocode_note.txt", "Ghidra headless not found/usable; rizin emitted disassembly only.")

    write_text(out / "EXPORT_README.md", (
        f"# rizin_export for {target.name}\n\n"
        "Files:\n"
        "- `meta.json` — tool versions and target.\n"
        "- `rzbin_info.txt` — compiled/header summary.\n"
        "- `info.json`, `sections.json`, `segments.json`, `symbols.json`, `imports.json`, `entry.json` — binary metadata.\n"
        "- `strings.json` — candidate strings.\n"
        "- `functions.json`, `functions_map.json` — rizin function list / address map.\n"
        "- `disassembly.txt` — authoritative per-function disassembly + xrefs.\n"
        "- `pseudocode_note.txt` (+ `ghidra_pseudocode/`) — pseudo-C when Ghidra headless ran.\n\n"
        "rizin has no decompiler plugin at this install, so disassembly is authoritative; "
        "treat pseudo-C as an aid and cross-check it against `disassembly.txt`.\n"
    ))

    print(f"[rizin_export] wrote inputs to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
