# DeepSeek Harness (personal fork)

English | [中文](README.zh.md)

This repository is a personal fork of [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (`dsh`), an open-source agent harness built on [Cordis](https://github.com/cordiverse/cordis) where everything is a plugin. It tracks the upstream `0.1.5-rc.2` line and carries the additions listed below; every package not named here is upstream code at that version.

Upstream documentation, guides, and the plugin catalogue live at [deepseek-harness.github.io](https://deepseek-harness.github.io/deepseek-harness/).

## What this fork adds

### Conversation timeline

[`@deepseek-ai/dsh-session-timeline`](packages/session/session-timeline/README.md) adds rewind, delete, and regenerate for a persisted Session, a composer compact button, and optional restoration of workspace files captured by durable checkpoints. Deleting or rewinding a turn truncates the tail durably: [`Session.truncate`](packages/core/session/README.md) and the persistence backends drop the removed events from the live Session and the current generation instead of writing a surface marker.

### Session hand-off

A Session row's overflow menu copies its ID, and the Web profile mounts [`tool-session-query`](packages/session-query/tool-session-query/README.md) so a new Session can search and read the Session it was handed.

### Cheaper history reads

[`packages/session/session-persistence-jsonl`](packages/session/session-persistence-jsonl/README.md) decodes a contiguous log suffix for one history page instead of restoring the whole artifact, so opening a long stored Session no longer builds its full object graph, and the Session controller serves cold pages without promoting an agent.

### Compaction fixes

[`compaction-basic`](packages/compaction/compaction-basic/README.md) prices pre-step pressure against the model a Session is about to use, and a summarization that hits its generation cap keeps the text it produced.

### Local wallpaper

[`@deepseek-ai/dsh-wallpaper-engine`](packages/extensions/wallpaper-engine/README.md) renders a local Wallpaper Engine install behind the Web GUI and persists its effect controls.

### Reverse-engineering preset

The shipped [`reverse`](apps/cli/config/agent-presets/reverse/preset.yml) agent preset carries the [`xiaojianbang-auto-reverse`](.agents/skills/xiaojianbang-auto-reverse/SKILL.md) skill and mounts the [`crawler-mcp`](crawler-mcp/README.md) Model Context Protocol server for CDP-driven browser, network, and JavaScript reverse-engineering work.

<a id="run"></a>
## Run this fork

<a id="run-from-source"></a>
### Run from source

```sh
git clone https://github.com/zyy606309-star/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh --profile web web
```

`pnpm run build` prepares the repository artifacts, and `pnpm dsh` serves them without rebuilding. The Web UI prints a launch URL carrying a one-time token; opening that URL sets the session cookie the browser needs afterwards.

## Track upstream

`origin` is this fork and `upstream` is `deepseek-ai/deepseek-harness`:

```sh
git fetch upstream
git merge upstream/master
pnpm install
```

## Known limits in this fork

- **Windows without Developer Mode.** Symbolic links cannot be created, so the symlink-based specs fail with `EPERM` and `apps/cli/tests/profiles/acp/cordis.yml` checks out as a text file holding its target path.
- **Fork Actions secrets.** The `E2E (real DeepSeek API)` and installed-wheel jobs require the repository secret `DEEPSEEK_API_KEY_EXTERNAL`; without it they fail in preflight rather than self-skipping.
- **The reverse preset is machine-specific.** Its skill and MCP entries carry absolute Windows paths that must be repointed on another host.
- **Rewritten history.** Branch `archive/remote-master-2026-09-13` holds the pre-`0.1.5` fork lineage; a clone still on that lineage syncs with `git fetch origin && git reset --hard origin/master` rather than a pull.

## Development

Start with the [development guide](docs/development.md) and the [architecture documentation](docs/architecture.md). Agents follow [AGENTS.md](AGENTS.md); contribution rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Upstream copyright and third-party dependency licenses are disclosed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
