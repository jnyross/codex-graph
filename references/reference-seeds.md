# Reference selection seeds

Use these verified sources as fallback inputs for the generated `## References & Links` section. Select only links relevant to the goal and chosen graph. Goal-specific official and community sources should come first.

## Official OpenAI and standards sources

- **Build skills** — https://developers.openai.com/codex/build-skills  
  Use for current Codex skill structure, discovery, optional `references/`, `scripts/`, and `agents/openai.yaml` resources, and installation locations.

- **Codex subagents** — https://developers.openai.com/codex/agent-configuration/subagents  
  Use for bounded delegation, collecting independent worker results, and the caution around parallel writes.

- **Codex configuration reference** — https://developers.openai.com/codex/config-reference  
  Use to verify current Code Mode and multi-agent feature configuration and lifecycle tool names.

- **Codex worktrees** — https://developers.openai.com/codex/environments/git-worktrees  
  Use for repository isolation and parallel chats in Codex Desktop.

- **Codex sandboxing** — https://developers.openai.com/codex/sandboxing  
  Use for technical execution boundaries and approval behavior.

- **Codex hooks** — https://developers.openai.com/codex/hooks  
  Use when the goal involves policy enforcement around direct or nested Code Mode tool calls.

- **Codex best practices** — https://developers.openai.com/codex/learn/best-practices  
  Use for prompting, context, planning, validation, and repository guidance.

- **How OpenAI uses Codex** — https://openai.com/index/how-openai-uses-codex/  
  Use for the design-first, implementation-second pattern on larger changes.

- **Code Mode protocol source** — https://github.com/openai/codex/blob/main/codex-rs/code-mode-protocol/src/description.rs  
  Use as the primary implementation reference for raw JavaScript input, `tools`, `ALL_TOOLS`, `text`, `exit`, pragmas, and awaited execution semantics.

- **Codex open-source repository** — https://github.com/openai/codex  
  Use to verify current tool schemas, runtime behavior, and implementation details when public docs are incomplete.

- **Using PLANS.md for multi-hour problem solving** — https://developers.openai.com/cookbook/articles/codex_exec_plans  
  Use for larger tasks that need durable execution plans and checkpoints.

- **OpenAI Skills catalog** — https://github.com/openai/skills  
  Use for maintained examples of production Codex skills.

- **Agent Skills specification** — https://agentskills.io/specification  
  Use for the portable `SKILL.md` format and metadata constraints.

## Community and operational sources

Treat issue reports as implementation evidence, not normative documentation. Prefer recent reports that reproduce against the current Codex release, and state their status when relevant.

- **Graph-max workflow post by Alex Kotliarskyi** — https://x.com/alex_frantic/status/2080776965070496115  
  Use as a community example of drawing a graph, implementing it as code, and running it.

- **Independent Code Mode calls and `Promise.allSettled`** — https://github.com/openai/codex/issues/35050  
  Use for the operational pattern of parallelizing independent nested calls while serializing dependencies and mutations.

- **Preserve live nested execution handles** — https://github.com/openai/codex/issues/35613  
  Use as a concrete warning not to discard session IDs for work that may still be running.

- **Outer Code Mode output budget and pragmas** — https://github.com/openai/codex/issues/33402  
  Use when a script aggregates enough nested output to require an explicit outer `max_output_tokens` budget.

- **Nested subagent wait behavior** — https://github.com/openai/codex/issues/35108  
  Use as current operational context for long-running nested waits and explicit handle preservation.

- **Awesome Codex Workflows** — https://github.com/shinpr/awesome-codex-workflows  
  Use to find concrete Codex-first workflow, worktree, review-gate, and orchestration examples.

- **codex-workflows** — https://github.com/shinpr/codex-workflows  
  Use as a community example of scope control, specialist handoffs, quality gates, and evidence-backed completion.

## Goal-specific source rules

1. Prefer the official documentation or repository for every named framework, language, API, standard, law, or dataset.
2. Match versioned documentation to the dependency version actually observed in the repository.
3. For community evidence, favor maintained repositories, issue trackers, discussions, reproducible examples, and engineering write-ups with concrete artifacts.
4. Include dissenting or failure evidence for evaluative, high-risk, or research-heavy goals.
5. Open and verify sources rather than treating search snippets as evidence.
6. Use direct canonical links and remove tracking parameters.
7. Record a publication, update, or verification date when freshness matters.
8. Never invent a link to satisfy the official/community minimum. Fall back to the verified seeds above.
9. Do not overload the generated deliverable with generic Codex links. Include only the few that explain the chosen runtime or topology.
10. Distinguish official behavior from community observations and unresolved issue reports.
