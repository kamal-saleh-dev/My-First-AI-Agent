# Multi-Agent Runtime (`/multi`)

Phase 2 Runtime Integration exposes the existing multi-agent system through a
single, explicit, **opt-in** runtime entry point. It does **not** introduce any
Phase 3 capability (no reflection, replanning, vector memory, semantic
retrieval, DAG execution, or long-term memory), and it leaves the `/auto`
autonomous loop completely unchanged.

## Command

```

/multi <engineering task>

/multiagent <engineering task>   # alias

```

Nothing runs unless the user explicitly types the command — the multi-agent
system is never invoked implicitly.

## Dispatch flow

`/multi` reuses the existing routing chain, exactly like `/auto`:

1. `model_router.detect_mode()` returns `("MULTI", "general")`.
2. `tool_registry.get_tool("MULTI")` returns `_tool_multi`.
3. `_tool_multi` lazily imports and calls `multi_agent_runtime.MultiAgentRuntime().run(task)`.
4. The runtime calls `AgentManager.orchestrate(...)`, which builds an
   `ExecutionPlan` and runs it through the `SequentialExecutionStrategy`.

`MULTI` is registered in `BACKGROUND_TOOLS`, so it runs in the background and
emits the standard `AGENT_IDLE` sentinel on completion — identical handling to
`/auto`.

## Reused components (nothing rewritten)

| Component | Role in the runtime |
| --- | --- |
| `AgentManager` | Registers default agents; delegates and orchestrates. |
| `BaseAgent` + `PlannerAgent` / `CodingAgent` / `ReviewerAgent` / `TestingAgent` | The workflow steps. |
| `MessageBus` | Inter-agent messaging + `message_published` observer events. |
| `SharedExecutionContext` | Shared goals, tasks, and memory across the run. |
| `ExecutionPlan` | Built by `orchestrate` from the workflow. |
| `ExecutionStrategy` | `SequentialExecutionStrategy` (the existing default). |

Default workflow: `PlannerAgent → CodingAgent → ReviewerAgent → TestingAgent`.

## Visibility

The runtime surfaces four signals:

- **Active agent** and **delegated task** — live, via a `MessageBus`
  subscription to `message_published` events (each delegation sends an
  `AgentManager → agent` message before the step runs).
- **Step result** — per-step status + final answer/error, rendered from the
  orchestrate return value.
- **Orchestration status** — the final `completed` / `failed` status.

Visibility output is routed through an injectable `emit` callback (defaults to
the app's `safe_print`), and every signal is also recorded on
`MultiAgentRunResult.events` for programmatic inspection and testing.

## Programmatic use

```

from multi_agent_runtime import MultiAgentRuntime, run_multi_agent

result = run_multi_agent("add a health endpoint and tests")

print(result.status)            # "completed" / "failed"

print(result.workflow)          # ordered agent names

for step in result.results:     # one dict per agent step

print(step["agent_name"], step["status"])

```

Injecting `decision_fns` (one decision function per agent) makes runs fully
deterministic and LLM-free — this is how the test suite exercises the runtime.

## Relationship to `/auto`

`/auto` runs a single `AutonomousExecutor` loop and is unchanged. `/multi` adds
a parallel, opt-in path that orchestrates several specialized agents over the
existing sequential strategy. The two commands are independent modes resolved
by `model_router.detect_mode()`.

## Explicitly out of scope (Phase 3)

Reflection, replanning, vector memory, semantic retrieval, DAG execution, and
long-term memory are intentionally **not** implemented here.
