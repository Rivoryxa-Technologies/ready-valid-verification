#!/usr/bin/env python3
"""Reproducible stdlib-only compile/run harness with retained evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import math
import re
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ((1, 7), (8, 1), (8, 2025), (17, 99))


def outcome_ok(mutant: bool, compile_exit: int, run_exit: int | None, output: str,
               timed_out: bool) -> bool:
    """Require the semantic result, never merely a zero/nonzero exit status."""
    if compile_exit != 0 or timed_out or run_exit is None:
        return False
    if mutant:
        markers = set(re.findall(r"FAIL_[A-Z_]+", output))
        return run_exit != 0 and markers == {"FAIL_STABILITY_OR_ORDER"} and "PASS " not in output
    return run_exit == 0 and "PASS " in output and "FAIL_" not in output


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(cmd: list[str], timeout: float, log: Path) -> tuple[int, str, float, bool]:
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            output, _ = proc.communicate(timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            remainder, _ = proc.communicate()
            # communicate() returns the complete captured stream after kill.
            output = (remainder or "") + "\nTIMEOUT\n"
            code = 124
    except OSError as exc:
        code, output = 127, f"EXEC_ERROR: {exc}\n"
    if timed_out:
        code, timed_out = 124, True
    elapsed = time.monotonic() - started
    log.write_text(output, encoding="utf-8")
    return code, output, elapsed, timed_out


def version(tool: str, timeout: float) -> str:
    try:
        proc = subprocess.run([tool, "-V"], text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, check=False, timeout=timeout)
        return proc.stdout.splitlines()[0] if proc.stdout else "unknown"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {type(exc).__name__}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per compile or simulation")
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "evidence")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a positive finite number")
    tools = {name: shutil.which(name) for name in ("iverilog", "vvp")}
    if not all(tools.values()):
        print("ERROR: missing required tool(s): " + ", ".join(k for k, v in tools.items() if not v), file=sys.stderr)
        return 2

    evidence_root = args.evidence_dir.resolve()
    run_id = time.strftime("run-%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{os.getpid()}"
    evidence = evidence_root / run_id
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
            run_cmd = [tools["vvp"], str(binary), f"+SEED={seed}"]
            rc, output, run_s, run_timeout = (None, "", 0.0, False)
            if cc == 0:
                rc, output, run_s, run_timeout = command(
                    run_cmd, args.timeout, run_log)
            else:
                run_log.write_text("simulation skipped: compile failed\n", encoding="utf-8")
            marker = "FAIL_STABILITY_OR_ORDER"
            passed = outcome_ok(mutant, cc, rc, output, compile_timeout or run_timeout)
            all_ok &= passed
            records.append({"name": name, "implementation": kind, "width": width, "seed": seed,
                            "compile_command": compile_cmd, "run_command": run_cmd,
                            "compile_exit": cc, "run_exit": rc, "compile_seconds": round(compile_s, 6),
                            "run_seconds": round(run_s, 6), "timed_out": compile_timeout or run_timeout,
                            "expected": "PASS" if not mutant else marker, "outcome_ok": passed,
                            "compile_log": compile_log.name, "run_log": run_log.name})
            print(f"{name}: {'EXPECTED' if passed else 'UNEXPECTED'} (compile={cc}, run={rc})")

    source_paths = [ROOT / "run.py", ROOT / "tb/tb_ready_valid.sv",
                    ROOT / "rtl/ready_valid_buffer.sv", ROOT / "rtl/ready_valid_buffer_mutant.sv"]
    summary = {"schema_version": 1, "ok": all_ok, "runner": "run.py",
               "python": platform.python_version(), "platform": platform.platform(),
               "tools": {k: {"path": v, "version": version(v, args.timeout)} for k, v in tools.items()},
               "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in source_paths},
               "cases": records}
    (evidence / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"evidence: {evidence / 'summary.json'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
