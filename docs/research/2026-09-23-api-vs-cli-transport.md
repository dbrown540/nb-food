# Same model, two transports: API vs headless Claude Code (2026-09-23)

Question: do readings of Claude Opus 5 through headless Claude Code (`claude -p`,
billed to the signed-in plan) match readings through the Anthropic API?

Setup: the same 20 random items (seed 20260923), the same battery, schema,
three readings and route. API: Messages API, thinking disabled, structured
output via output_config. CLI: one fresh `claude -p` session per reading with
no tools, MCP servers, settings, skills or memory, the battery as the system
prompt and the answer schema via --json-schema (Claude Code returns it through
its structured-output tool). The CLI's JSON names the serving model from the
provider response (`modelUsage`, provider firstParty).

## Findings

- Attribute tags: 153 / 180 answers the same (85%). 16 moved from unknown
  (API) to no (CLI), none from yes to no. Most of the 16 follow the battery's
  own rule (a description that lists the parts, a savory dish not being high in
  sugar); a few are doubtful (a salad listing pine nuts read as "no seeds";
  tuna sashimi read as "not spicy").
- Food mapping: 18 / 20 items the same.
- Thinking was not the cause: with thinking off the CLI gave the same "no" on
  the test item. The answer channel differs (a tool call inside Claude Code
  against a native structured response), so the transport is part of the
  model basis and readings from the two are never mixed.
- Context: a default `claude -p` call loaded about 118k tokens (global
  instructions, memory, skills, connectors) in four turns; with every source
  switched off it loads about 2.8k tokens in two turns.

## Decision

Deterministic vs judgment: unchanged, a T2 judgment. The CLI transport is
accepted as the path for the grocery run because it bills the owner's plan and
still records a provider-reported model identity; its basis carries
`transport: claude-code-cli`, so an API re-read later is a new basis, not a
silent swap. The doubtful "no" answers are an open item for a measurement on a
labelled sample, the same gap the battery already carries.
