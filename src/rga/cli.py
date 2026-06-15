"""CLI integration stub.

Inputs:
- analyze command should accept a recording path under data/recordings/
- config path should default to configs/slay-the-spire.json

Output:
- final implementation should write timeline JSON, density PNG, and report.md

Implementation is intentionally deferred until module workers are complete.
"""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """Run the eventual analyze CLI and return a process exit code."""

    raise NotImplementedError("cli.main is a contract stub for the integration worker")
