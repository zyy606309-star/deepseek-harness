---
description: "Wallpaper Engine bridge for the DeepSeek Harness web GUI: Steam install discovery, inventory and media routes, and persisted effect controls."
kind: "package-bundle"
---

# @deepseek-ai/dsh-wallpaper-engine

English | [中文](README.zh.md)

<a id="summary"></a>
## Summary

`dsh-wallpaper-engine` bridges a local Wallpaper Engine install into the web GUI. The host half locates the install through Steam's `libraryfolders.vdf`, enumerates installed wallpapers, and serves an inventory plus media and preview bytes over loopback routes; the browser half draws the selected wallpaper behind the application and exposes the effect controls. It contributes no model-visible tool, prompt text, or session event.

<a id="table-of-contents"></a>
## Table of Contents

- [Use this package](#use-this-package)
- [Understand the implementation](#understand-the-implementation)
- [Further Exploration](#further-exploration)
- [Model Experience](#model-experience)
- [Known Limitations and Deferred Work](#known-limitations-and-deferred-work)

<a id="use-this-package"></a>
## Use this package

The package is loaded as an out-of-tree bundle row; one patch entry composes both halves.

```yaml
- id: wallpaper-engine
  name: '@deepseek-ai/dsh-wallpaper-engine'
```

### Enable the prebundled Web feature

A profile that already lists this package in its bundles needs no further wiring: the browser half declares `platform: web`, so the row also loads in a headless or TUI profile, where the HTTP routes are simply absent.

### Choose and tune a wallpaper

The selection and its four effect knobs persist in the `wallpaper-engine` settings namespace: `id`, `scrim`, `border`, `blur`, and `wallpaperBlur`. A stored section that fails validation falls back to defaults rather than failing the plugin.

### Routes

- `GET /wallpaper-engine/inventory` returns `{ installDir, wallpapers }`.
- `GET /wallpaper-engine/media/<token>` returns video or HTML bytes, with `Range` support.
- `GET /wallpaper-engine/preview/<token>` returns the preview image.

<a id="understand-the-implementation"></a>
## Understand the implementation

Every route registers through the plugin fiber, so unloading the plugin unwinds them. A media or preview URL carries a token that is the base64url form of the absolute path, so no route accepts a filesystem path the client could not already read from the inventory. `webServer` is injected but read through `ctx.get`, because the same bundle also loads in profiles that have no HTTP server. Scene (native 3D) and application wallpapers are enumerated too, but only their preview image is served, because a browser cannot render them.

<a id="further-exploration"></a>
## Further Exploration

- [`dsh-settings`](../../settings/settings/README.md) owns the durable namespace this plugin registers and validates.

<a id="model-experience"></a>
## Model Experience

None, as the package is a browser-side and loopback-HTTP plugin layer that registers nothing model-facing.

#### KV Cache effect

None; the package neither assembles nor sends a provider request.

## Known Limitations and Deferred Work

- **Scene and application wallpapers render as previews only.** A native 3D scene has no browser-renderable form, so the inventory exposes its preview image and the media route refuses it.
- **Install discovery is Steam-shaped.** The plugin reads `libraryfolders.vdf` and probes the common Windows Steam directories; an install outside Steam is not discovered.
- **Steam probe paths are Windows-specific.** The probed directories and the executable lookup assume a Windows host.

<a id="dev-note"></a>
### Dev Note

<details>
<summary>Working context for maintainers — click to expand</summary>

This package is fork-local: upstream ships no Wallpaper Engine bridge, so the fork carries the bundle row and the package together.

</details>

**Runtime invariant:** No companion is published. The package owns no durable state of its own: the selection lives in the `dsh-settings` namespace it registers, and its route table is an effect of the plugin fiber.
