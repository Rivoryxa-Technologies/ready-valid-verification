#!/usr/bin/env python3
"""Reproducible stdlib-only compile/run harness with retained evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ((8, 1), (8, 2025), (17, 99))


def outcome_ok(mutant: bool, compile_exit: int, run_exit: int | None, output: str,
               timed_out: bool) -> bool:
    """Require the semantic result, never merely a zero/nonzero exit status."""
    if compile_exit != 0 or timed_out or run_exit is None:
        return False
    if mutant:
        return run_exit != 0 and "FAIL_STABILITY_OR_ORDER" in output and "PASS " not in output
    return run_exit == 0 and "PASS " in output and "FAIL_" not in output


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(cmd: list[str], timeout: float, log: Path) -> tuple[int, str, float, bool]:
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout, check=False)
        code, output = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as exc:
        code, timed_out = 124, True
        output = (exc.stdout or "") + "\nTIMEOUT\n"
    elapsed = time.monotonic() - started
    log.write_text(output, encoding="utf-8")
    return code, output, elapsed, timed_out


def version(tool: str) -> str:
    proc = subprocess.run([tool, "-V"], text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, check=False)
    return proc.stdout.splitlines()[0] if proc.stdout else "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per compile or simulation")
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "evidence")
    args = parser.parse_args()
    tools = {name: shutil.which(name) for name in ("iverilog", "vvp")}
    if not all(tools.values()):
        print("ERROR: missing required tool(s): " + ", ".join(k for k, v in tools.items() if not v), file=sys.stderr)
        return 2

    evidence = args.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    all_ok = True
    for width, seed in DEFAULT_CASES:
        for mutant in (False, True):
            kind = "mutant" if mutant else "correct"
            name = f"{kind}-w{width}-s{seed}"
            binary = evidence / (name + ".vvp")
            compile_log = evidence / (name + "-compile.log")
            run_log = evidence / (name + "-run.log")
            sources = [ROOT / "tb/tb_ready_valid.sv", ROOT / "rtl/ready_valid_buffer.sv"]
            defines: list[str] = []
            if mutant:
                sources.append(ROOT / "rtl/ready_valid_buffer_mutant.sv")
                defines = ["-DMUTANT"]
            compile_cmd = [tools["iverilog"], "-g2012", "-Wall", *defines,
                           f"-Ptb.WIDTH={width}", "-s", "tb", "-o", str(binary),
                           *map(str, sources)]
            cc, _, compile_s, compile_timeout = command(compile_cmd, args.timeout, compile_log)
            rc, output, run_s, run_timeout = (None, "", 0.0, False)
            if cc == 0:
                rc, output, run_s, run_timeout = command(
                    [tools["vvp"], str(binary), f"+SEED={seed}"], args.timeout, run_log)
            else:
                run_log.write_text("simulation skipped: compile failed\n", encoding="utf-8")
            marker = "FAIL_STABILITY_OR_ORDER"
            passed = outcome_ok(mutant, cc, rc, output, compile_timeout or run_timeout)
            all_ok &= passed
            records.append({"name": name, "implementation": kind, "width": width, "seed": seed,
                            "compile_exit": cc, "run_exit": rc, "compile_seconds": round(compile_s, 6),
                            "run_seconds": round(run_s, 6), "timed_out": compile_timeout or run_timeout,
                            "expected": "PASS" if not mutant else marker, "outcome_ok": passed,
                            "compile_log": compile_log.name, "run_log": run_log.name})
            print(f"{name}: {'EXPECTED' if passed else 'UNEXPECTED'} (compile={cc}, run={rc})")

    source_paths = [ROOT / "run.py", ROOT / "tb/tb_ready_valid.sv",
                    ROOT / "rtl/ready_valid_buffer.sv", ROOT / "rtl/ready_valid_buffer_mutant.sv"]
    summary = {"schema_version": 1, "ok": all_ok, "runner": "run.py",
               "python": platform.python_version(), "platform": platform.platform(),
               "tools": {k: {"path": v, "version": version(v)} for k, v in tools.items()},
               "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in source_paths},
               "cases": records}
    (evidence / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"evidence: {evidence / 'summary.json'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
