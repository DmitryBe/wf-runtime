## wf-runtime

A small **workflow runtime** that executes a YAML/JSON DSL by compiling it into a
LangGraph state machine.

It provides:

- **A DSL** (`Workflow`) defined with Pydantic (`src/wf_runtime/dsl/models.py`)
- **JSON Schema validation** for workflow input/output payloads
- **Node executors** for:
  - `noop` (pass-through)
  - `python_code` (RestrictedPython sandbox)
  - `jq_transform` (jq expressions)
  - `router` (safe, limited expression evaluator for branching)
  - `llm` (LangChain chat models + optional structured output)

## Install

This project targets **Python 3.12+**.

From a repo checkout:

```bash
uv sync
```

## Workflow DSL overview

Workflow files are plain YAML (or JSON) and are validated by `Workflow`:

- **`id`**: workflow identifier
- **`version`**: integer version
- **`input.schema`**: JSON Schema for the input payload
- **`nodes`**: list of node definitions (do **not** define `start`/`end` nodes)
- **`edges`**: how nodes connect (may reference implicit `start` and `end`)
- **`output`**:
  - **`output.input_mapping`**: mapping that computes final output from `$input` / `$nodes.*`
  - **`output.schema`**: JSON Schema for the final output payload

The canonical generated schema lives at `docs/dsl_schema.yaml` (also copied to
`resources/dsl_schema.yaml`).

### Mapping expressions

Most places that accept “mappings” are dictionaries whose values can be:

- **constants**: any value that does not start with `$`
- **references**:
  - **`$input`**: entire workflow input
  - **`$input.foo.bar`**: nested input values
  - **`$nodes.node_id`**: entire output of a node
  - **`$nodes.node_id.key`**: read a field from a node output (when it’s an object)
  - **`$state.some_key`**: internal state keys (advanced; mainly for engine internals)

### Supported node kinds

#### `noop`

Resolves `input_mapping` and writes it to node output. Useful for wiring and tests.

#### `python_code`

Runs Python code using `RestrictedPython` via `SandboxRunnerImpl`.

- Your code is wrapped as `def user_main(input): ...`
- Top-level `return ...` in YAML is supported
- `timeout_s` defaults to `1.0`

Note: this is **not** a hardened OS sandbox; it’s best-effort restriction inside
the Python process.

#### `jq_transform`

Runs a jq program via the Python `jq` package (`JQRunnerImpl`).

This node resolves inputs with **non-strict** behavior (missing inputs become
`null`/`None`), which is convenient for “pick first non-null” patterns after
branching.

#### `router`

Evaluates a set of labeled conditions and writes `{"label": "<picked>"}` as node output.
Edges out of a router can then use `when_label` to branch.

Conditions are a **restricted subset of Python expressions** (no function calls,
no attribute/subscript access). References like `$input.op` are rewritten into
safe variables before evaluation.

Example:

```yaml
- id: route_op
  kind: router
  cases:
    add: "$input.op == 'add'"
    sub: "$input.op == 'sub'"
```

#### `llm`

Calls a LangChain chat model using `langchain.chat_models.init_chat_model(...)`.

- Set `model` like `"openai:gpt-4.1-mini"`
- `model_params` are forwarded to the model initializer
- `prompt` supports:
  - plain string (templated via Python `str.format(**inputs)`)
  - multimodal list of tuples: `("text", "...")` / `("image_url", "...")`
- If `output_schema` is present, the model is wrapped with structured output:
  `llm.with_structured_output(schema=output_schema)`

Environment:

- **`OPENAI_API_KEY` must be set** (currently required by the `llm` executor)

### Output mapping

Each node has an `output_mapping` that maps the raw executor result to a node output.

- If `output_mapping` is **empty**, the node output is the **raw result** (can be any JSON or simple value).
- Otherwise you can map:
  - **raw result** using `"$result"` (also accepts `"$jq_result"`, `"$code_result"`, `"$tool_result"`)
  - **fields** from an object result using `$.path.to.field`

Example:

```yaml
output_mapping:
  intent: "$.intent"
  raw: "$result"
```

### Edges and branching

Edges are defined as:

- `{"from": "a", "to": "b"}` for a normal edge
- `{"from": "router_node", "to": "branch_node", "when_label": "some_label"}` for conditional routing

You can fan out from `start` to multiple nodes to run them concurrently, then join
later by connecting multiple upstreams into a downstream node.

## Examples

See `examples/workflows/` for runnable workflow specs:

- `examples/workflows/intent_classifier.yaml`: LLM + structured output
- `examples/workflows/add_numbers.yaml`: simple `python_code` workflow
- `examples/workflows/router.yaml`: conditional routing via labeled edges
- `examples/workflows/concurrent.yaml`: fan-out / fan-in concurrency


## Schema generation

The JSON Schema for the DSL is generated from `Workflow.model_json_schema(by_alias=True)`
and stored as YAML:

```bash
python scripts/generate_schema.py --out docs/dsl_schema.yaml
```

## Development

Run tests:

```bash
uv run pytest -q --cov=wf_runtime --cov-report=term-missing
```

Format:

```bash
black .
isort .
```

## Notes / limitations

- **`tool` nodes are present in the DSL model but not executed yet** (no executor is registered),
  so using `kind: tool` will currently fail at compile time with “Unsupported node kind”.
- **Sandboxing** for `python_code` is RestrictedPython-based and is not a full security boundary.
