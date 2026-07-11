# Initial Executor Model Candidates

Status: candidate inventory, not an accepted model-selection decision.

## MiniMax-M3

- Canonical hosted model name in current MiniMax API documentation: `MiniMax-M3`.
- Open-weight/model-card identifier: `MiniMaxAI/MiniMax-M3`.
- Relevant advertised capability: multimodal language/coding/agent operation with a long context window.
- Required before use: confirm API availability, image-input format, tool-calling behavior, pricing, rate limits, data policy, deterministic settings, and exact snapshot/version pinning.

Sources:

- https://platform.minimax.io/docs/guides/models-intro
- https://huggingface.co/MiniMaxAI/MiniMax-M3

## Xiaomi MiMo-V2.5

- Canonical family spelling: `MiMo`, not `MIMO`.
- Candidate model name: `MiMo-V2.5`.
- Relevant advertised capability: native image, video, audio, and text understanding with agent-oriented browsing and action capability.
- Required before use: confirm the exact API model identifier, tool-calling protocol, image limits, pricing, rate limits, data policy, and version-pinning behavior.

Source:

- https://mimo.mi.com/

## Selection rule

Do not compare harness treatments across different executor model snapshots. Record provider, exact model identifier, model revision or release date where available, endpoint, reasoning mode, sampling parameters, image preprocessing, and tool-call protocol in every run configuration.
