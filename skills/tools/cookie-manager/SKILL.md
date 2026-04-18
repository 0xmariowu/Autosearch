<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F002a -->
---
name: cookie-manager
description: Retrieve per-channel cookies from multiple sources for authenticated search methods.
version: 1
methods:
  - id: get_cookie
    impl: impl.py
    requires: []
---

This tool skill resolves a cookie bundle for one channel at a time.
It exists so authenticated channel methods do not each reinvent cookie lookup.
The return value is a plain name to value mapping ready for an HTTP client.
Channels should treat the mapping as ephemeral runtime state.
The manager does not persist new cookies back to disk.
The first source is the manual JSON file under `~/.autosearch/cookies/{channel}.json`.
That file is the preferred operator-controlled source.
It keeps setup explicit and avoids surprising browser access.
The JSON file must contain a single object with cookie names as keys.
If the file is empty or malformed, the lookup warns and continues.
The second source is the macOS keychain path.
That path is only attempted on Darwin when keychain lookup is enabled.
Non-macOS environments skip keychain without noise.
Keychain support is intended for local developer machines.
It is optional and should not be required for CI.
The third source is `rookiepy`, which is disabled by default.
`rookiepy` is imported lazily so the dependency stays optional.
If the import fails, the manager warns and moves on.
If browser extraction is enabled, it remains a best-effort fallback.
Manual JSON still wins over every other source.
This precedence keeps channel behavior deterministic.
It also makes debugging auth issues simpler.
Security matters more than convenience in this tool.
Cookie values are never logged.
Success logs include only the channel name and the source label.
Failure logs include only the channel name and a reason code.
No cookie content should appear in warnings, info events, or exceptions.
Channel methods should call the tool near request construction time.
A typical flow is: resolve cookie, decide whether auth-only method is available, then attach cookies to the request client.
Methods that can degrade gracefully may switch to an unauthenticated path when `None` is returned.
Methods that require auth should surface a clear unavailable error instead.
This tool is intentionally narrow.
It does not validate channel-specific session freshness.
It does not know whether a cookie unlocks a given endpoint.
It only resolves the best available cookie mapping for the requested channel.
Use it as a shared primitive inside channel implementations, not as a routed search method.
