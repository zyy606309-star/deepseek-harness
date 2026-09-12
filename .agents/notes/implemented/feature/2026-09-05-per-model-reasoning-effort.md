# Agent Note: Per-Model Default Reasoning Effort

Status: implemented

English | [中文](2026-09-05-per-model-reasoning-effort.zh.md)

## Problem

A model catalog entry could size a model (`contextWindow`, `maxTokens`) but never choose how hard it thinks. Reasoning effort was a route-level knob only: `llm-deepseek` had one provider-wide `reasoningEffort`, and `llm-pi-ai` had one provider-wide `reasoning`. The composer's model picker offered effort levels per model (through `reasoning.efforts`) and used `reasoning.defaultEffort` as the selection default, but that default was always the route's, so two models on one provider that should reason differently could not be configured that way. A deployment that wanted `gpt-5.6-luna` at `max` and another model on the same route at `low` had no setting for it.

## Decision

Add an optional per-model `reasoningEffort` to the model catalog (values `off`/`low`/`high`/`max`), used as that model's default effort when an exact model is selected and no per-conversation effort overrides it. The value rides the existing `reasoning.defaultEffort` seam, so the composer popup and the request path apply it with no new wiring.

- **`llm-deepseek`** (DeepSeek official): `DeepSeekCatalogModel` gains `reasoningEffort`; `modelInfoFor` honors it as the model's `defaultEffort`, falling back to the route default. The `thinking: 'disabled'` deployment policy still forces `off` — a per-model non-off effort cannot override a disabled policy, because the adapter owns that policy and the host cannot tell it apart from an ordinary default.
- **`llm-pi-ai`** (declared OpenAI-compatible routes): `PiAiModelProfile` gains `reasoningEffort`; resolution threads it into a `configuredReasoningEffort` map beside the existing `configuredMaxTokens`, and `modelInfo` reads it as the model's default, falling back to `profile.reasoning`. Only a level the model's own `reasoningEfforts` offers becomes a default (`describableReasoningLevel` yields none otherwise), so a config that names an unsupported level describes as no default rather than hiding the route.

The setting is surfaced on the Models page as a per-row `Thinking intensity` dropdown in both catalog editors (`DeepSeekModelsEditor` and `ModelListEditor`); a blank row inherits the provider default. The shared `validateDeepSeekModels` rejects a value outside the four levels.

## Testing

`packages/llm/llm-deepseek/tests/adapter.spec.ts` asserts a per-model effort becomes that model's default while a sibling model keeps the route default, and that an invalid effort is refused at the resolver boundary. `packages/llm/llm-pi-ai/tests/adapter.spec.ts` asserts a per-model effort wins over the route default for the model that declares it while a sibling inherits the route default. `packages/client/ui-settings-models/tests/components.client.spec.tsx` asserts the validation failure for an out-of-set value.

TODO(keyless-snapshot, optional): this change adds no new model-visible request structure or input — it supplies a configuration source to the existing, already-tested `reasoning.defaultEffort` selection seam (the `deepseek-defaults` snapshot asserts effort reaching the wire; the model-selection path is covered by `ui-model-selection` tests). An assembled web-only snapshot of the full chain — catalog per-model effort → `session.models` `defaultEffort` → `selectModel` → wire request — would be a beneficial enhancement but requires a real host model-selection scenario (the headless snapshot harness creates agents with `provider`/`model` only, so it cannot exercise the selection path); the adapter-level unit tests above and the existing model-selection default-effort tests cover the two halves.

## Alternatives considered

- **Host-layer injection in `buildModelCatalog`** (read each provider's settings section and overwrite `reasoning.defaultEffort`). Rejected: it cannot distinguish an adapter's forced `off` (deployment `thinking: 'disabled'`) from an ordinary default, so it would override a disabled policy, and it couples the host to each provider's settings layout (`models` array vs `providers.<route>` plus `modelOverrides`).
- **A per-model default read straight from the raw profile in `modelInfo`.** Unwritable for pi-ai: `ResolvedPiAiProviderProfile` omits `models`/`modelOverrides`, so the raw per-model field is not reachable there; a resolved map (chosen) mirrors `configuredMaxTokens` instead.

## Consequences

- A deployment can set a per-model thinking intensity and it takes effect on the next selection of that model, with no restart.
- The composer's effort pane still offers the adapter-owned levels; the per-model value only sets which one is preselected.
- `verify-package-invariants` is untouched: this adds configuration resolution and model-info metadata, no new events or mutable runtime relations.
