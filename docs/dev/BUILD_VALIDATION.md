# Release 1.3.1 verification

## Outputs and checks performed

- Vita/host visible version **1.3.1**, title ID **VRXA00001** retained, Vita
  APP_VER **01.18**, LiveArea revision 18. The application cross-build completed
  with official VitaSDK master-linux-v2.540 / GCC 15.2, without application
  compiler warnings. No icon/accent/branding redesign was made in this revision.
- SDK archive SHA-256:
  `b1a8f4d6e41460c9ecf2c3c4590eb7eb3ea6b690767f508bd5696dbc77a4272e`.
- **191 Python tests passed with no skips**, ResourceWarning treated as an error,
  using Python 3.14.9 / OpenSSL 3.5.9 and locked dependencies. Optional native
  TLS/profile/Opus adapters and official offline ngrok/Tailscale CLI checks were
  enabled. No account, public tunnel, release or message was created by tests.
- New cases check preserved PCM/Opus bitrate settings on upgrade, supported
  Python ABI/architecture/TLS preflight, native hash/source-commit binding,
  tag/version mismatch, public-release/moved-tag refusal, exact draft asset
  names/checksums and tamper rejection. A real VPK package check caught binary
  integer metadata being decoded as text; the validator now reads the identity
  string fields only, with a dedicated mixed-type SFO regression test.
- **15 native C test programs passed** AddressSanitizer/UndefinedBehaviorSanitizer
  checks. LeakSanitizer is disabled in this traced environment. Control/render
  cases include opening/cancelling/confirming disconnect, fresh touch handling,
  one-shot requests, guarded framebuffer bounds and exact-black blanking.
  Existing scaffold-only unused-stub/sign-compare warnings are not application
  source warnings.
- Windows EXE and Opus DLL were rebuilt from the checked source using the pinned
  Zig 0.15.2 / Opus 1.6.1 recipes. Both are x86-64 PE files; generated expected
  hashes and pc/native/SHA256SUMS.txt match. Linux cannot execute the Windows
  payloads; the revised Windows CI job is responsible for their native checks.
- **25 renderer previews** include player, queue/favorites/search, keyboard,
  settings/quality, connection/error states, black idle and the new disconnect
  confirmation. They use original fictional music/artwork fixtures. The modal
  and player previews were visually inspected; idle remains pixel-exact black.
- Final ZIP checks cover CRC, Python syntax, Markdown links, workflow YAML,
  required source/docs/native files, VPK identity and bundled licenses. Runtime
  credentials/preferences/recordings, build caches/SDKs, and separately obtained
  Soloist/provider/driver executables are excluded. Favorites is an empty template.

Local preparation hashes (CI rebuilds may produce different hashes):

| Output | SHA-256 |
| --- | --- |
| Vita VPK | `71c8384b35302517b09c6878640cba1c91662c0719662f581c9263acf65f2cc2` |
| Capture EXE | `edb76237cb796b12d7c9258ba82e7a090c9c68409f40002583b843a475f8bd35` |
| Opus DLL | `bedfd641d5bf47bef9af4c7bcb47da6f509c3c012809d6b87e283fdadfb94b17` |

These are file identities, not an assertion of byte-identical rebuilds or digital
signatures. Release loaders use each package's generated expected native hashes.

## Publication checks and limits

The official public GitHub API confirmed **egalindo2167/vita-soloist-receiver**
exists with default branch main. No public tag/release existed when checked.
All configured external actions are full-commit pins with Node 24 runtimes;
inputs/name/path and the SDK image digest were checked. Workflow jobs normally
have contents:read with nonpersistent checkout credentials. Only a matching
version-tag push grants the final draft job contents:write.

The revised workflow builds Windows payloads from the checkout, tests those
outputs on Windows, builds the VPK, and packages a versioned ZIP with source/run
metadata and hashes. Draft-publication tests use fake gh calls and assert that
public releases and moved tags cannot be overwritten. No actual push/tag/draft
or complete GitHub-hosted run of this new workflow was performed here. The
user's earlier Windows-green screenshot applies to the preceding workflow.
A successful tag run and review of its exact draft assets are still required.
See [PUBLISHING.md](PUBLISHING.md); do not substitute the local preparation ZIP
for those CI-built public assets.

The native Windows components are unsigned. Actual Windows audio routing,
Smart App Control enforcement, firmware touch/panel/screen-off behavior and
sustained physical Vita Wi-Fi playback have not been tested in this Linux
environment. Passing checks is not an independent security audit.

The title ID was not globally certified available: the official VitaDB catalog
lookup did not yield a usable catalog. Confirm it with the current catalog/
maintainer before a separate VitaDB submission. Retaining the current ID avoids
creating a different installed app/data location for existing testers.

## Functional acceptance checks on Windows and Vita

Use the host and VPK from the same release. Upgrade Host should preserve the
saved codec/bitrate, routing, login/key, pairing and remote options. Install over
the existing title without deleting data. From Now playing, Circle must show a
confirmation; Circle cancels, X disconnects, and Queue/settings/keyboard retain
ordinary back behavior. Test a fresh tap as well as controller input.

On a fresh PC follow [HOST_SETUP.md](../../HOST_SETUP.md), including standard x64
Python, virtual cable, trusted Private LAN/firewall and USB pairing. Test cable
isolation, muted physical speakers, restart/reconnect, both quality preferences,
Local/Remote modes and screen-off playback. Record actual Windows policy blocks
without disabling protection. See [AUDIO_SETUP.md](../../AUDIO_SETUP.md) and
[network tuning](../NETWORK_TUNING.md) for diagnostic counters.

Search remains limited to entries Soloist actually returns. Spotify documents
up to 80 upcoming tracks. Existing synthetic 5,000-entry pagination fixtures and
79-confirmed-skip/cancellation tests do not demonstrate that Soloist returns a
whole large playlist. [SEARCH.md](../../SEARCH.md) documents the read-only probe,
limits and skip/history cautions. Long-jump limits and branding are unchanged.

Pre-public implementation records remain in
[DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md) and the historical review files.

## Native CI stall follow-up

The supplied GitHub log shows both dependencies and all 15 native programs
finished within about 43 seconds. Python then stalled before the next test
result, until the 30-minute job deadline. The prior download retry recovered;
compiler warnings did not stop this run.

The next module's two TLS audio tests, plus a capture-error test, had header
loops that never handled EOF. An encoder startup failure could therefore close
the socket and leave a test spinning forever. Those reads now fail on EOF.
The native Opus shared library also lacked a SONAME and unversioned linker
name, making ctypes discovery unreliable on fresh runners without system Opus.
The native build now supplies both; library discovery was verified with the
system-cache/compiler search paths deliberately bypassed.

Both CI Python invocations now use a 120-second per-test watchdog, printing
the test name and all thread stacks before exiting with failure (124). This
does not skip tests or extend the job deadline. Regression checks cover partial
header EOF and a real intentionally hung child test with a short deadline.
These two checks passed on the available Python 3.12 runtime. The earlier
191-test Python 3.14 run remains recorded above; the full revised suite was
not rerun here because that transient interpreter is no longer available.
No PC/Vita runtime source, native shipped binary or VPK changed in this fix.
A new GitHub run must verify the corrected fresh-runner path.
