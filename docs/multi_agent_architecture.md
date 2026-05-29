# Multi-Agent Architecture

Status: BUILT, NOT WIRED. The `agents/` package is fully implemented and unit
testable, but it is not yet invoked by the CLI (`agent.py`), the GUI
(`agent_gui.py`), or the chat dispatcher (`chat_handler.py`). Nothing in the
live runtime constructs an `AgentManager` today. This document describes the
package as it exists so the architecture docs no longer drift from the code.

Wiring the package into the runtime is intentionally out of scope for the
stabilization phase. This document does not propose or imply that wiring.

## Package Layout

The package lives under `agents/`:

- `agents/base_agent.py`: `BaseAgent`, `AgentResult`, `AgentState`,
  `AgentExecutionPolicy`.
- `agents/specialized_agents.py`: the six default role agents.
- `agents/agent_manager.py`: `AgentManager` registration, delegation, lifecycle,
  and orchestration entry points.
- `agents/orchestration.py`: `ExecutionStep`, `ExecutionPlan`,
  `ExecutionStrategy`, and `SequentialExecutionStrategy`.
- `agents/message_bus.py`: `MessageBus`, `AgentMessage`, `BusEvent`.
- `agents/shared_execution_context.py`: `SharedExecutionContext`, `SharedTask`.
- `agents/__init__.py`: the public export surface (`__all__`).

## BaseAgent

`BaseAgent` is the abstract role wrapper around the Phase 1 autonomous loop.
Subclasses declare:

- `name`, `role`, and `preferred_model`.
- `allowed_tools` and `restricted_tools` (allow-list minus restrictions equals
  the effective tool set).
- `system_prompt` describing the role.

Key behavior:

- `run(task, ...)` builds an `AutonomousExecutor` (the bridge to the existing
  loop) and returns an `AgentResult`. A `decision_fn` can be injected so the
  loop runs without live model calls (used by tests).
- `execute_tool(name, args)` enforces permissions and raises `PermissionError`
  when a disallowed tool is requested.
- Local memory is bounded by `AgentExecutionPolicy`; older entries are compacted
  into summaries rather than growing without bound.
- Each agent keeps an isolated `AgentState` so concurrent agents do not share
  mutable execution data except through explicit channels.

`AgentResult` carries `agent_name`, `task`, `status`, `final_answer`, `error`,
`observations`, and `metadata`, and has `to_dict()` for serialization.

## Specialized Agents

Six default roles are defined and registered by default:

- `PlannerAgent` (planning) — read/scan/analyze tools; write/edit restricted.
- `CodingAgent` (coding) — full filesystem tools.
- `ReviewerAgent` (review) — read/analyze tools; write/edit restricted.
- `TestingAgent` (testing) — test and analysis tools.
- `DebuggerAgent` (debugging) — read/edit/analyze tools.
- `ContextAgent` (context) — search/scan/read tools.

Role models are pulled from config aliases (for example
`MULTI_AGENT_MODEL_DEEPSEEK`, `MULTI_AGENT_MODEL_LLAMA`,
`MULTI_AGENT_MODEL_QWEN_CODER`), not hardcoded model names.

## AgentManager

`AgentManager` is the coordination surface:

- Construction with `register_defaults=True` registers all six default agents.
- `register_agent` / `unregister_agent` manage the registry.
- `start_agent` / `stop_agent` manage lifecycle; a stopped agent rejects
  delegation with a failed `AgentResult` (`agent_stopped`).
- `delegate_task(agent_name, task, ...)` runs a single agent.
- `orchestrate(task, workflow=...)` runs a sequence of agents. The default
  workflow is `PlannerAgent` then `CodingAgent` then `TestingAgent` then
  `ReviewerAgent`.
- `lifecycle_snapshot()` and `agent_capabilities()` expose current status and
  tool capabilities.

Delegation and orchestration both accept injected decision functions, which is
how tests exercise coordination without live models.

## Orchestration

`ExecutionPlan.from_workflow(task, workflow, context, ...)` builds an ordered
list of `ExecutionStep` objects. `SequentialExecutionStrategy` (name
"sequential") runs each step in order, passing results forward through the
shared context, and halts on the first failed step — returning `status`,
`results`, the `failed_step`, and the `shared_context`.

This is strictly sequential. There is no DAG execution, no replanning, and no
reflection in the current package, and none are added during stabilization.

## Message Bus

`MessageBus` provides per-agent mailboxes and an event channel:

- `send` / `receive` (FIFO; `receive` pops, `peek` does not).
- `broadcast` to all known mailboxes.
- `publish` accepts an `AgentMessage` or a dict (via `AgentMessage.from_dict`)
  and raises `ValueError` when sender/recipient are missing.
- `subscribe` / `emit_event` deliver `BusEvent` objects to subscribers whose
  type matches the event type or the wildcard "*". Subscriber exceptions are
  captured in `subscriber_failures` and never interrupt publishing.
- `history`, `events`, and `clear` support inspection and reset.

Access is guarded by a re-entrant lock for thread safety.

## Shared Execution Context

`SharedExecutionContext` holds cross-agent goals, metadata, shared memory, and
`SharedTask` records. `update_task` transitions the global state to idle when all
tasks reach a terminal state. `snapshot()` returns a serializable view. Access is
guarded by a re-entrant lock.

## Relationship To The Autonomous Loop

Each agent delegates real work to `AutonomousExecutor` from `autonomous_loop.py`.
The multi-agent layer adds roles, permissions, messaging, shared context, and
sequential orchestration on top of the same single-executor loop. It does not
replace or modify the loop.

## Testing

The stabilization phase adds unit coverage for every module above:
`test_base_agent.py`, `test_specialized_agents.py`, `test_agent_manager.py`,
`test_orchestration.py`, `test_message_bus.py`,
`test_shared_execution_context.py`, and `test_agents_exports.py`. These tests use
injected decision functions and temporary workspaces, so they never require a
live model or network access.
