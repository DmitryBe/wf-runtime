"""
Generate the Workflow JSON Schema and save it as YAML in docs/.

This uses Pydantic's `model_json_schema()` output (JSON Schema) and writes it in
YAML format for readability.

Usage (repo checkout):
  - uv run python src/wf_runtime/dsl/generate_schema.py
  - python src/wf_runtime/dsl/generate_schema.py

Usage (installed package):
  - python -m wf_runtime.dsl.generate_schema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml


def _find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists() and (p / "src").exists():
            return p
    return start


def _ensure_src_on_path() -> Path:
    """
    Ensure repo's `src/` is on sys.path so this file can be executed directly.
    Returns the detected repository root.
    """
    repo_root = _find_repo_root(Path(__file__).resolve())
    src_dir = repo_root / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    return repo_root


def generate_schema() -> Dict[str, Any]:
    # Local import so sys.path bootstrapping can happen first.
    from wf_runtime.dsl.models import Workflow

    # Use aliases so the schema matches the on-wire DSL keys (`from`, `schema`, ...).
    schema = Workflow.model_json_schema(by_alias=True)

    # Make YAML output deterministic-ish across Python/Pydantic versions by
    # normalizing through JSON (removes non-JSON scalars).
    return json.loads(json.dumps(schema, sort_keys=True))


def main() -> int:
    repo_root = _ensure_src_on_path()

    parser = argparse.ArgumentParser(description="Generate Workflow schema (YAML).")
    parser.add_argument(
        "--out",
        default=str(repo_root / "docs" / "dsl_schema.yaml"),
        help="Output path (default: docs/dsl_schema.yaml)",
    )
    args = parser.parse_args()

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = generate_schema()

    header = (
        "# GENERATED FILE - DO NOT EDIT BY HAND\n"
        "# Source: Workflow.model_json_schema(by_alias=True)\n"
    )
    yaml_text = yaml.safe_dump(
        schema,
        sort_keys=False,  # already normalized above
        default_flow_style=False,
        allow_unicode=True,
    )
    out_path.write_text(header + yaml_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
