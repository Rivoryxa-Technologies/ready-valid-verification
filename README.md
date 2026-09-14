# Ready/valid buffer verification, from first principles

Backpressure bugs often survive simple “data went in, data came out” tests. The
interesting moment is when an output is valid but the consumer is not ready: the
producer-facing handshake must stop, and the visible output item must remain
stable until it is accepted.

This repository is a small, original teaching example. It contains a
parameterized, synthesizable one-entry elastic buffer and a self-checking
SystemVerilog testbench. The testbench uses a queue scoreboard, directed
backpressure, simultaneous input/output transfers, randomized stalls, reset
checks, several widths, and fixed seeds.

## Contract

A transfer occurs on a rising clock edge only when `valid && ready` is true.
The producer holds `valid` and `data` while blocked. The consumer may vary
`ready` independently. `rst` is synchronous and active high; after an edge with
`rst == 1`, `out_valid` is low. Reset discards any buffered item.

The correct buffer can accept and emit an item on the same edge, sustaining one
item per cycle after its initial latency. This is one ready/valid data channel.
It is not a complete AXI implementation and makes no AXI compliance claim.

## Run from any directory

Requirements: Python 3.9+ and Icarus Verilog with both `iverilog` and `vvp` on
`PATH`. The runner uses only the Python standard library.

```sh
python3 /absolute/path/to/ready-valid-verification/run.py
```

Each compile and simulation has a timeout. Missing tools return exit code 2.
Unexpected compile, timeout, pass, failure, or failure marker returns exit code
1. A successful run returns 0 only when every correct configuration prints
`PASS` and every mutant configuration fails specifically with
`FAIL_STABILITY_OR_ORDER`.

The ignored `evidence/` directory retains compile logs, simulation logs,
parameter widths, random seeds, exit codes, tool versions, platform, wall times,
source SHA-256 hashes, and the outcome matrix in `summary.json`. Choose another destination with
`--evidence-dir DIR`.

The default matrix runs six simulations: widths 8 and 17 over seeds 1, 2025,
and 99. Each of the three parameter/seed pairs runs once against the correct RTL
and once against the mutant. Harness regressions run with:

```sh
python3 -m unittest discover -s /absolute/path/to/ready-valid-verification/tests -v
```

## Why the mutant matters

`ready_valid_buffer_mutant.sv` deliberately claims it is always ready. When its
single slot is full and the output is stalled, it accepts and overwrites later
items. The protocol-aware source is behaving legally; the mutant causes output
instability or reordered data. A useful verification example proves both sides:
the intended RTL passes, while a plausible broken RTL fails for the intended
reason rather than merely returning some nonzero status.

## Limits

This demo checks a one-entry, single-clock buffer in simulation. It is not a
formal proof, CDC solution, asynchronous-reset example, performance benchmark,
or verification IP package. The queue-based testbench is simulation-only; the
two RTL modules are synthesizable. Production integration still needs project
lint, synthesis, timing, reset, and system-level verification.

MIT licensed; see `LICENSE`.
