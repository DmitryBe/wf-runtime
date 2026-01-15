#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/wfcli.sh <invoke|validate> <workflow_spec_path.{yaml|yml|json}> [input_data_json_or_@file] [base_url]

Examples:
  scripts/wfcli.sh invoke examples/workflows/add_numbers.yaml '{"x":10,"y":20}'
  scripts/wfcli.sh invoke examples/workflows/add_numbers.yaml @input.json
  scripts/wfcli.sh validate examples/workflows/add_numbers.yaml
  scripts/wfcli.sh validate examples/workflows/add_numbers.yaml '{"x":10,"y":20}'
  scripts/wfcli.sh invoke examples/workflows/add_numbers.yaml '{"x":10,"y":20}' http://localhost:8000

Notes:
  - Sends POST to:
      - <base_url>/api/workflow/invoke
      - <base_url>/api/workflow/validate
  - base_url defaults to WF_RUNTIME_URL env var or http://localhost:8000
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

CMD="${1:-}"
WF_SPEC_PATH="${2:-}"
INPUT_ARG="${3:-}"
BASE_URL="${4:-${WF_RUNTIME_URL:-http://localhost:8000}}"

if [[ -z "$CMD" || -z "$WF_SPEC_PATH" ]]; then
  usage
  exit 2
fi

if [[ "$CMD" != "invoke" && "$CMD" != "validate" ]]; then
  echo "error: command must be 'invoke' or 'validate' (got: $CMD)" >&2
  exit 2
fi

if [[ "$CMD" == "invoke" && -z "${INPUT_ARG:-}" ]]; then
  echo "error: input_data is required for 'invoke'" >&2
  usage
  exit 2
fi

if [[ ! -f "$WF_SPEC_PATH" ]]; then
  echo "error: workflow spec file not found: $WF_SPEC_PATH" >&2
  exit 2
fi

INPUT_JSON=""
if [[ -n "${INPUT_ARG:-}" ]]; then
  INPUT_JSON="$INPUT_ARG"
  if [[ "$INPUT_ARG" == @* ]]; then
    INPUT_FILE="${INPUT_ARG#@}"
    if [[ ! -f "$INPUT_FILE" ]]; then
      echo "error: input_data file not found: $INPUT_FILE" >&2
      exit 2
    fi
    INPUT_JSON="$(cat "$INPUT_FILE")"
  fi
fi

REQ_JSON="$(
  python3 - "$WF_SPEC_PATH" "$INPUT_JSON" <<'PY'
import json
import os
import sys

wf_path = sys.argv[1]
input_json = sys.argv[2]

suffix = os.path.splitext(wf_path)[1].lower()
text = open(wf_path, "r", encoding="utf-8").read()

if suffix in (".yaml", ".yml"):
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise SystemExit(
            "PyYAML is required to load YAML workflow specs. "
            "Install it (e.g. `pip install pyyaml`) or provide a .json workflow spec."
        ) from e
    wf_spec = yaml.safe_load(text)
elif suffix == ".json":
    wf_spec = json.loads(text)
else:
    raise SystemExit("workflow_spec_path must end with .yaml/.yml or .json")

input_data = None
if input_json:
    try:
        input_data = json.loads(input_json)
    except Exception as e:
        raise SystemExit(f"input_data must be valid JSON. Got: {input_json!r}") from e

payload = {"wf_spec": wf_spec}
if input_data is not None:
    payload["input_data"] = input_data
print(json.dumps(payload))
PY
)"

URL="${BASE_URL%/}/api/workflow/${CMD}"

if command -v jq >/dev/null 2>&1; then
  echo "$REQ_JSON" \
    | curl -sS -X POST "$URL" -H 'Content-Type: application/json' -d @- \
    | jq .
else
  echo "$REQ_JSON" \
    | curl -sS -X POST "$URL" -H 'Content-Type: application/json' -d @-
fi

