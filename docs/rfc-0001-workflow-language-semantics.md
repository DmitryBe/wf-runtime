# RFC-0001: Workflow Language Semantics (wf-runtime DSL)

- **Status**: Draft
- **Last updated**: 2026-01-15
- **Target implementation**: `wf_runtime` (this repository)

This document specifies the semantics of the `wf-runtime` workflow language: how a workflow is structured, how nodes connect, how data is passed, and what “execution” means in the runtime.

Normative keywords (**MUST**, **SHOULD**, **MAY**) are used as defined in RFC 2119.

## Goals

- **Provide a stable semantic contract** between workflow authors and the runtime.
- **Define data passing** (references, input mappings, output mappings).
- **Define control flow** (edges, routers, concurrency, termination).
- **Define error behavior** (node failures, `fail_fast`, and the error model).

## Non-goals

- **Security boundary guarantees** for `python_code` sandboxing.
- **A complete “tool registry” spec** (`kind: tool` exists in the DSL schema but is not executed by the runtime today).
- **A versioned migration system** for workflows beyond the `version` field.

## Quick pointers (source of truth)

- **DSL model**: `src/wf_runtime/dsl/models.py`
- **Generated JSON Schema**: `resources/dsl_schema.yaml` (also copied to `docs/dsl_schema.yaml` when generated)
- **Compiler/execution**: `src/wf_runtime/compiler/compiler.py`, `src/wf_runtime/compiler/builder.py`
- **Data mappings**: `src/wf_runtime/engine/mappings.py`
- **State model**: `src/wf_runtime/engine/state.py`

## Terminology

- **Workflow**: A YAML/JSON document describing nodes, edges, schemas, and output mapping.
- **Node**: A step with a `kind` and `id`. It reads inputs from workflow state, executes, and writes an output back to workflow state.
- **Edge**: A directed connection from one node to another (including implicit system nodes `start` and `end`).
- **Workflow state**: The runtime’s in-memory state, containing the original input, all node outputs, final output, and any errors.

## Workflow document structure

A workflow document is a JSON/YAML object with (at minimum):

- **`id`** (string): unique workflow identifier.
- **`version`** (integer): workflow version (semantic meaning is owned by the author/tooling).
- **`input.schema`** (JSON Schema object): schema for the invocation input.
- **`nodes`** (list): user-defined nodes (MUST NOT include `start` or `end`).
- **`edges`** (list): connectivity between nodes (MAY reference implicit `start` and `end`).
- **`output.input_mapping`** (object): mapping used to compute final workflow output from `$input` and `$nodes.*`.
- **`output.schema`** (JSON Schema object): schema for the final output object.
- **`fail_fast`** (bool, default `true`): whether node errors halt execution immediately.

### Node identity rules

- **`node.id` MUST be** lowercase snake_case and match `^[a-z][a-z0-9_]*$`.
- **`start` and `end` are reserved** and MUST NOT be used as user node ids.
- Node ids MUST be unique within a workflow.

## Execution model

### Implicit system nodes

The runtime injects two internal nodes:

- **`start`**: entry point (no-op passthrough).
- **`end`**: finish point; computes the final output using `workflow.output.input_mapping`.

Workflow authors MUST NOT define these nodes manually; they are always present.

### Workflow state (conceptual model)

During execution, the runtime maintains a state object with keys:

- **`input`**: the original invocation input (object).
- **`data`**: a map of `node_id -> node_output` for all nodes that have produced outputs.
- **`output`**: the final workflow output (object), written by the `end` node.
- **`errors`**: a list of error objects, appended as nodes fail.
- **`last_node`**: last node that produced an update.

### Data flow

- A node reads **only** from:
  - `state.input` via `$input...` references
  - `state.data` via `$nodes.<node_id>...` references
  - (advanced) other state keys via `$state.<key>`
- A node writes **only** its own output to `state.data[node_id]` (and MAY also append an error).
- Node outputs are **JSON values** (object/array/string/number/bool/null). If you want to reference a field like `$nodes.some_node.foo`, that node’s output MUST be an object containing the `foo` key.

### Control flow

- **Edges define execution order**. An edge `A -> B` means “B is downstream of A”.
- **Fan-out**: multiple outgoing edges from a node enable downstream work to proceed (often concurrently).
- **Fan-in**: multiple upstream edges into a node are used as a join point; the node typically consumes multiple `$nodes.*` values.

The runtime compiles the workflow into a LangGraph state machine; concurrency and synchronization semantics follow that compilation model.

### Workflow validity constraints

A valid workflow MUST:

- Have **at least one edge from `start`**.
- Have **at least one edge that reaches `end`** (directly or via a branch route).

### Error behavior and `fail_fast`

Nodes report failures by appending an error entry to `state.errors` with:

- `node_id` (string)
- `type` (string)
- `message` (string)
- `details` (object)

If **`fail_fast: true`**, the runtime treats a node error as fatal and stops execution by raising a runtime exception when that node returns an update containing non-empty `errors`.

If **`fail_fast: false`**, execution MAY continue; the final state MAY contain `errors`. (The API-level executor currently treats any final `errors` as a workflow failure.)

## Mappings and expressions

### `input_mapping` (compute node inputs)

Many node kinds accept `input_mapping: {key: valueSpec}`. The runtime resolves it into a concrete input object passed to the node executor.

Each `valueSpec` can be:

- **Constant**: any non-string, or a string that does not start with `$`.
- **Reference**: a string starting with `$` that resolves from workflow state.

#### Reference syntax

- **`$input`**: the entire invocation input object.
- **`$input.foo.bar`**: nested values inside the invocation input.
- **`$nodes.node_id`**: the entire output of a node.
- **`$nodes.node_id.key`**: a field inside a node’s object output.
- **`$state.some_key`**: access to other workflow state keys (advanced; SHOULD be avoided by workflow authors).

#### Strict vs non-strict resolution

Most nodes use **strict resolution**:

- Missing keys/attributes in `$input.*` / `$nodes.*` raise an error and the node fails.

Some features use **non-strict resolution** (missing becomes `null`/`None`):

- `jq_transform` inputs are resolved non-strictly to support “pick first non-null” patterns after branching.
- Router condition references are resolved non-strictly so missing data is simply falsy rather than fatal.

### `output_mapping` (shape node outputs)

After a node executor returns a raw `result`, `output_mapping` shapes what is stored as that node’s output.

- If **`output_mapping` is empty** (`{}`), the node output is the **raw result**.
- Otherwise, `output_mapping` is an object whose values can be:
  - **`"$result"` / `"$tool_result"` / `"$jq_result"` / `"$code_result"`**: store the raw result
  - **`"$.a.b"`**: read from object result (JSONPath-lite, dict-only; missing returns `null`/`None`)
  - **constants**: stored literally

## Edges and branching

### Edge forms

The DSL supports two equivalent ways to express routing:

- **Simple edges**:
  - `{from: "a", to: "b"}`
  - `{from: "router_node", to: "branch_node", when_label: "add"}`
- **Branch edges**:
  - `{from: "router_node", routes: [{to: "a", when_label: "x"}, {to: "b", when_label: "y"}]}`

The runtime flattens branch edges into per-route conditional edges at compile time.

### Router semantics

- A `router` node evaluates `cases` in order and picks the **first matching label**.
- If no case matches, `default` is used.
- The router writes output `{ "label": "<picked_label>" }` to `state.data[router_id]`.
- Conditional edges leaving the router use `when_label` to match that label.
- A fallback label of **`else`** is supported (and is always taken when used as a condition in router evaluation).

## Node kinds (semantic contract)

### `noop`

- **Inputs**: `input_mapping`
- **Behavior**: resolves `input_mapping` and returns it as the node result.
- **Output**: shaped by `output_mapping`.

### `python_code`

- **Inputs**: `input_mapping`
- **Behavior**: runs `code` in a RestrictedPython-based sandbox runner.
- **Code contract**: user code MUST return a JSON-serializable object (typically a dict).
- **Timeout**: controlled by `timeout_s`.

### `jq_transform`

- **Inputs**: `input_mapping` (resolved non-strictly)
- **Behavior**: runs a jq program (`code`) with the resolved input object.
- **Output**: raw jq result (if `output_mapping: {}`) or shaped by `output_mapping`.

### `router`

- **Inputs**: `cases` (map `label -> condition expression`) and optional `default`
- **Behavior**: picks a label and outputs `{label: "<picked>"}`.
- **Condition language**: a restricted subset of Python expressions (no calls, no attribute/subscript access). `$input.*`, `$nodes.*.*`, `$state.*` references are substituted into safe variables before evaluation.

### `llm`

- **Inputs**: `input_mapping` used for prompt templating (via Python `str.format(**inputs)`).
- **Behavior**: calls a LangChain chat model (`model`, `model_params`).
- **Prompt**:
  - text: string template
  - multimodal: list of `{type: "text"|"image_url", content: "...template..."}` parts
- **Structured output**: when `output_schema` is present, the model is wrapped with structured output.
- **Environment**: the current implementation requires `OPENAI_API_KEY`.

### `http_request`

- **Inputs**: `input_mapping` MUST include:
  - `url` (string; supports `.format(**inputs)` templating)
  - `method` (`GET|POST|PUT|DELETE`, case-insensitive; MAY be a `$...` expression)
- **Behavior**:
  - For `GET`/`DELETE`: other keys become query parameters.
  - For `POST`/`PUT`: other keys become JSON body.
- **Output (raw)**: object with `ok`, `status`, `headers`, `body_bytes_len`, and one of `body_json` / `body_text` / `body_b64`.
- Non-2xx responses are treated as node errors (with response details attached).

### `tool` (reserved / not executed)

The DSL schema includes `kind: tool`, but there is currently **no executor registered** for it in the runtime; using it will fail at compile time.

## Principles for constructing workflows

- **Schema-first**: define strict `input.schema` and `output.schema` to catch mistakes early.
- **Keep node outputs stable and explicit**: prefer object outputs with named fields so downstream `$nodes.*.field` references are readable.
- **Use mappings as the “wiring layer”**: nodes SHOULD be small and focused; use `input_mapping`/`output_mapping` to connect them rather than coupling logic across nodes.
- **Prefer `router` + `jq_transform` for branching joins**: after branching, use `jq_transform` with non-strict inputs (e.g. `(.a // .b)`) to reconcile optional branch outputs.
- **Avoid `$state.*` in workflows**: it is intended for engine internals and may change.
- **Treat side-effecting nodes carefully**: `http_request` and other external calls SHOULD be isolated, time-bounded, and have error handling paths.
- **Design for observability**: keep ids meaningful; consider emitting node-completed events via `CompileContext.emit_event` (runtime integration feature).

## Canonical examples

See `examples/workflows/` for runnable specs demonstrating the semantics:

- **Sequential**: `add_numbers.yaml`
- **Router branching**: `router.yaml`
- **Fan-out / fan-in concurrency**: `concurrent.yaml`
- **Multimodal LLM**: `analyze_image.yaml`

