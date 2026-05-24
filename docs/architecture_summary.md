# Architecture Summary

This project is a modular autonomous coding agent. The current system still
preserves the legacy generation pipeline, while Phase 1 adds an autonomous
think-act-observe tool loop through `/auto` and `AutonomousExecutor`.

## Current Architecture

The agent is split by responsibility:

- `agent.py`: CLI entry point, command loop, model switching, background task dispatch.
- `agent_gui.py`: GUI shell around the same agent process.
- `chat_handler.py`: user-turn dispatcher for chat, file Q&A, and generation requests.
- `model_router.py`: rule-based/LLM routing to modes and domains.
- `generation_engine.py`: full project generation orchestration.
- `script_generator.py`: per-script/template generation.
- `script_reviewer.py`: review and compile-fix pass.
- `project_builder.py`: generated file extraction, saving, and project post-processing.
- `tool_registry.py`: legacy command registry plus structured autonomous tools.
- `autonomous_loop.py`: Phase 1 autonomous executor.
- `autonomous_prompts.py`: autonomous-loop prompt builders and observation summaries.
- `autonomous_repetition.py`: repeat-action detection abstraction.
- `recovery.py`: generation checkpoint persistence and resume context.
- `self_mod.py`: guarded self-modification workflow.
- `llm_client.py`: local/cloud model calls and alias resolution.

## Execution Flow

Normal CLI flow:

1. `agent.py` reads input.
2. Direct commands are handled inline (`/model`, `/scan`, `/read`, `/resume`, etc.).
3. Other input is routed by `model_router.detect_mode()`.
4. `tool_registry.get_tool()` returns the legacy callable for that mode.
5. Background-capable modes run through `shutdown_manager.run_in_background()`.

Generation flow:

1. `chat_handler.chat_tool()` detects intent/domain.
2. Full project requests call `generation_engine.run_generation()`.
3. `planner.py` produces script/file plans.
4. `script_generator.generate_single()` creates each file.
5. `script_reviewer.review_script()` and `compile_fix_loop()` improve outputs.
6. `project_builder.extract_and_save_scripts()` writes files.
7. `recovery.RecoveryContext` tracks progress and cleanup.

## Autonomous Loop Flow

The Phase 1 autonomous path is exposed by `/auto <task>` and can also be used
directly via `AutonomousExecutor`.

Loop:

1. Build system/user prompt with available structured tools.
2. Model returns one JSON action:
   `{"thought":"...","tool":"read_file","args":{"path":"..."}}`
3. Executor validates JSON and tool name.
4. Tool runs through `Tool.execute_structured()`.
5. Result becomes an `Observation`.
6. Observation is summarized for the next prompt.
7. Loop stops on `finish`, retry exhaustion, timeout, max steps, or repeated action.

No multi-agent coordination exists yet.

## Tool System

`tool_registry.py` now has two layers:

- Legacy `TOOL_REGISTRY`: uppercase command-mode callables used by `agent.py`.
- Structured tool registry: lowercase tools used by `AutonomousExecutor`.

Core structured tools:

- `read_file`, `write_file`, `edit_file`
- `search_files`, `scan_project`
- `compile_project`, `run_tests`
- `analyze_errors`

Tool metadata includes `schema`, `categories`, and `tags`. Current categories
include `filesystem`, `testing`, `analysis`, `project`, and `memory`.

## Important Abstractions

- `Tool`: base interface for structured tools.
- `ToolResult`: internal structured result with `success`, `data`, and `error`.
- `Observation`: one loop step result.
- `ExecutionState`: full loop state and history.
- `ObservationSummarizer`: compact observation history for prompts.
- `RepetitionDetector`: exact repeated-action detection with a future semantic hook.
- `RecoveryContext`: checkpoint lifecycle wrapper around generation.
- `DOMAIN_REGISTRY`: domain/plugin-style routing metadata.

Compatibility note: `Tool.execute()` still returns legacy JSON text. Internal
autonomous execution uses `Tool.execute_structured()`.

## Key Constraints

- Preserve modular architecture; avoid growing `agent.py`.
- Keep legacy generation, recovery, plugins, reviewer, self-mod, and tests working.
- Prefer registries and interfaces over new if/elif chains.
- Avoid hardcoded models where aliases/config already exist.
- Keep autonomous loop single-agent until Phase 2 explicitly introduces agents.
- File tools must stay workspace-scoped.
- Tool outputs should remain structured internally.

## Extension Points

- Add new structured tools by subclassing `Tool` and calling `register_tool()`.
- Add command-mode tools through legacy `TOOL_REGISTRY`.
- Add domains in `model_router.DOMAIN_REGISTRY`.
- Add generation templates in the relevant `*_templates.py` module.
- Extend autonomous prompts in `autonomous_prompts.py`.
- Replace or augment loop repetition logic through `RepetitionDetector`.
- Add future memory-aware tools under the `memory` category.
- Add self-mod routing targets in `self_mod._MODIFIABLE` and keyword maps.

## Recovery And Checkpointing

Generation recovery is handled by `recovery.py`.

- `GenerationCheckpoint` records task, engine, project name, script pairs,
  completed scripts, failed scripts, status, and timestamps.
- `CheckpointManager` persists checkpoints under `.checkpoints/`.
- `RecoveryContext` creates or resumes checkpoints and marks script state.
- Successful generation deletes the checkpoint.
- Exceptions, interrupts, or incomplete runs keep the checkpoint resumable.
- `/resume <project>` loads checkpoint state and re-enters generation.

The autonomous loop currently keeps in-memory `ExecutionState` only. Persistent
autonomous-loop checkpoints are a future phase.

## Testing Architecture

Tests are under `tests/` and are grouped by subsystem:

- `test_generation_engine.py`: engine detection, saving, Python auto-run.
- `test_integration.py`: generation, recovery, model switching, routing.
- `test_model_advisor.py`: quality scoring and escalation ladder.
- `test_llm_client.py`: model aliases and response handling.
- `test_self_mod.py`: self-mod targeting, safety, patch review.
- `test_project_tools.py`: project helper tools.
- `test_checkpoint.py`: checkpoint save/resume/cleanup.
- `test_autonomous_loop.py`: autonomous JSON parsing, retries, stop conditions,
  summarization, repetition detection, timeout handling.
- `test_tool_registry_structured.py`: structured registry, `ToolResult`, metadata,
  and default tool execution.

For future phases, add focused unit tests first, then integration tests only when
the new behavior crosses module boundaries.
