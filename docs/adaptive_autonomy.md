# Adaptive Autonomy (Phase 3, redesigned)

Opt-in reflection + memory + adaptive routing layer for the agent, added on the
`phase2-runtime-integration` branch. It implements the highest-ROI gaps from the
architecture audit while deliberately skipping the phases the audit classified
as low-value or speculative.

## What this is

A thin reflect -> decide -> adapt control loop layered on top of the existing
multi-agent system. After each agent step it scores progress, detects
stuck/repeated-failure states, and chooses one of:

- continue        : step succeeded, move to the next agent
- switch_model    : retry the step with an escalated model
- retry           : retry the step with the same model
- delegate_debug  : hand the failure to DebuggerAgent, then retry
- stop            : give up on the step / workflow

It also wires the previously-unused RAG memory store into the loop (recall
before each step, record after) and escalates models along a configured ladder
when a step keeps failing.

## What it does NOT change

- /auto  (autonomous_loop.AutonomousExecutor) is untouched.
- /multi (multi_agent_runtime.MultiAgentRuntime) is untouched.
- model_router.py, tool_registry.py, BaseAgent, and the specialized agents are
  NOT modified. The only modified file is config.py (additive tunables).

The runtime owns its OWN AgentManager, so the per-step model escalation it
performs never leaks into other runtimes or global state.

## Components

- reflection_engine.py : bounded, rules-based evaluator -> control decision
- adaptive_router.py   : failure-driven model escalation over an alias ladder
- agent_memory.py      : bridge that recalls/records via the existing memory_store
- adaptive_runtime.py  : AdaptiveRuntime + run_adaptive() coordinator

## Usage

Simple: call run_adaptive("Add a /weather command and test it"). It returns an
AdaptiveRunResult with .status, .completed, .recovered, .steps and .summary.

Advanced: instantiate AdaptiveRuntime(workflow=("PlannerAgent", "CodingAgent",
"TestingAgent")) and call .run(task). The same decision_fns injection used by
multi_agent_runtime is supported for deterministic, network-free testing.

## Configuration (config.py)

    ADAPTIVE_MAX_STEP_RETRIES       (default 2)      failed attempts per agent before debug/stop
    ADAPTIVE_MAX_ESCALATIONS        (default 2)      model escalations per agent before plain retry
    ADAPTIVE_MAX_DEBUG_DELEGATIONS  (default 1)      DebuggerAgent hand-offs per failing step
    ADAPTIVE_STUCK_THRESHOLD        (default 4)      identical failures -> stuck -> stop
    ADAPTIVE_MEMORY_ENABLED         (default True)   recall/record around steps
    ADAPTIVE_MEMORY_TOP_K           (default 3)      past experiences injected per step
    ADAPTIVE_MEMORY_ONLY_SUCCESS    (default False)  restrict recall to successes
    ADAPTIVE_ESCALATION_LADDER      (default or_qwen, or_deepseek, or_llama)

All are overridable via AGENT_* environment variables.

## Roadmap mapping

This redesign merges the original Phase 3 (reflection), the repair half of
Phase 6, and Phase 8 (routing) into one small layer, and rescopes Phase 4 from
"vector DB" to "integrate the store we already have".

Intentionally NOT built (per audit): Execution Graph (Phase 5), Background Queue
/ long-running tasks (Phase 7), full Sandbox (Phase 9), full Self-Improvement
(Phase 10).
