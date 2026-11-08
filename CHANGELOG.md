# Changes

## 1.3

- Public distribution preparation: concise download/setup README, full reference
  retained in USER_GUIDE.md, build/contribution/support guides, issue/PR templates,
  private security-report instructions and step-by-step GitHub publication notes.
- Git ignore/line-ending rules, editable icon source included in release ZIPs,
  empty-favorites release guard and private/runtime/foreign-binary packaging tests.
  CI YAML/dependency commands and Windows-copy-safe shell invocation corrected;
  actions remain pinned/read-only with bounded jobs. Application binaries unchanged.
- Search upcoming songs by title/artists from Queue, with a touch/controller
  keyboard, accent/case-insensitive multiword matching and clear scope/counts.
- Request get_queue(limit=0) and cache all available entries on the PC instead
  of imposing the old 32-row cap. Spotify documents up to 80 upcoming tracks,
  not an entire playlist. Read-only Queue Availability helper checks a live build.
- Encrypted five-row result pages, stale-response rejection, original queue
  positions and bounded PC indexing. Favorites remain 32 unchanged shortcuts.
- Distant selections ask for confirmation, show confirmed-skip progress and
  support cancellation. Longer bounded jump timeouts and refreshed audio holds
  preserve the existing queue/context without playing a URI replacement context.
- Tests cover an actual local WebSocket/paired TLS fixture with 5,000 synthetic
  entries, 79 confirmed skips, cancellation, paging and malformed/stale input.
- Visible version 1.3, APP_VER 01.17. Update both host and VPK for search; pairing,
  audio format/quality, cable route, saved display settings and Funnel are kept.

## 1.2

- Desktop-inspired Vita interface: smooth proportional text, antialiased icon
  controls, green play/pause button, shared playback bar and dedicated Now
  playing/Queue/Favorites navigation. Exact-black background and idle blanking.
- L/R previous/next works in both browsing tabs; D-pad Left/Right switches those
  tabs, Triangle cycles all three pages. SELECT opens Settings; repeat is an icon.
- Larger transport/row/slider touch bounds share geometry with drawing. Touch
  pagination, draggable Spotify volume, speaker mute/restore and seek targets.
- Gear menu contains Audio quality, saved 30/60/120/300-second or Never screen
  timeout, Local/Remote route and PC connection setup. New display.bin only;
  quality, pairing, favorites and tunnel data retain their previous formats.
- Visible version 1.2, APP_VER 01.16. No transport/host logic changes; the 1.1
  host remains compatible. Favorites adding/editing features remain unchanged.

## 1.1

- Bounded receiver-driven catch-up, decoded-frame acknowledgements, 60 ms audio
  batching and Windows default dynamic send buffering. Remote buffer capacity
  2.048 s/prebuffer 1.024 s; Local startup remains 256 ms.
- Authenticated audio hold/release markers discard the old audio connection and
  its app/kernel/tunnel backlog on explicit playback changes. Natural track-end
  audio is retained. Short audio resets can retain the same Vita's Auto rate.
- Stable queue tokens and serial confirmed skips preserve the existing queue/
  context when selecting farther ahead. ID-based prefix merging and debounced
  short snapshots address the 32/10 flicker.
- Explicit agile callback interface, confirmed Soloist expiry messaging, current
  guide headings, favorites walkthrough and review/tuning notes.
- Favorites editing features remain unchanged. Visible version 1.1, APP_VER 01.15.

## 1.0

- Dedicated virtual-cable setup wizard, exact saved endpoint ID, live Soloist
  route verification, and named capture status. Windows default output stays
  available to other apps; no silent device fallback.
- Native Windows process-loopback helper captures only the owned Soloist process
  tree. Checks process creation time/executable, OS support, and live routing;
  excludes other apps even on the cable. Hash-verified executable and source included.
- Paired encrypted audio-setup status, clear true-black Vita error screen, and
  guarded play/activate with pause/recovery on capture failures.
- Startup, pairing, account data, favorites, Funnel, bitrate/Auto choices and
  screen-off/OLED features retained. Windows 11/build 20348+ required for capture.
- Visible application version 1.0; Vita install APP_VER advances from 01.13 to
  01.14 so this release remains an in-place upgrade of the earlier version tags.

## 0.13

Historical assessment: [SECURITY_REVIEW_0.13.md](SECURITY_REVIEW_0.13.md).

- Vita quality menu with independent Local/Remote preferences and live fixed
  96–320 kbps Opus changes. Opt-in receiver-driven Auto with conservative recovery.
- Larger Remote prebuffer and lower-priority/slower Remote cover-art transfer.
- Bounded concurrent TLS admission, loopback-specific resource policy, Windows
  exclusive bind, tunnel-aware loopback defaults and explicit LAN opt-in.
- Rotating new-client TLS/discovery aliases and matching pairing-export cleanup.
- No artwork redirects/proxies; hash-locked installs, pinned CI inputs, and a
  bundled/hash-checked DLL built from upstream Opus instead of a Python wheel.
- Focused security review with confirmed findings, qualifications and residual risks.

## 0.12

- Tailscale Funnel helpers and Vita SNI routing, preserving paired TLS and Opus 320.

## 0.11

- Managed raw TCP remote profiles and optional ngrok support.

## 0.10

- Mandatory paired TLS 1.3 PSK-DHE, USB enrollment and revocation.

## Earlier releases

- Persistent Windows/Soloist bridge, Spotify controls/artwork/browsing, Opus,
  Vita OLED screen-off mode, LiveArea assets and capture/buffering fixes.
