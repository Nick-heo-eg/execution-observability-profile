# Contributing Guidelines

Before submitting a PR, answer these questions:

1. **Which layer does this belong to?** This repo is Layer 4 (observability profile). See [LAYER_REGISTRY](https://github.com/Nick-heo-eg/execution-boundary/blob/master/LAYER_REGISTRY.md).
2. **Does this add enforcement logic?** If yes, it belongs in `execution-gate` or `agent-execution-guard`, not here.
3. **Does this change semantic convention attributes?** Attribute additions are additive only. Removals or renames require an issue first.
4. **Is this a new collector topology?** Add under `profiles/` with a clear platform label (k8s, vm, etc.).

PRs that add gate/enforcement logic will be closed — this repo observes, it does not enforce.
