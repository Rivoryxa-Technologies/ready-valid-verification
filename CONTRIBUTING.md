# Contributing

Keep examples small, synthesizable, and explicit about their protocol contract.
Install Python 3, Icarus Verilog (`iverilog` and `vvp`), then run:

```sh
python3 /path/to/ready-valid-verification/run.py
```

Changes must preserve the expected outcome matrix: every correct case passes and
every mutant case fails with `FAIL_STABILITY_OR_ORDER`. Add a deterministic seed
and width configuration when fixing a newly discovered corner case. Do not make
claims that this one-channel example implements AXI or another complete bus.

By contributing, you agree that your contribution is licensed under the MIT
License in this repository.
