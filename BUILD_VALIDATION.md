# Release 1.3 verification

## Current source and binaries

- Visible Vita/host version **1.3**, title ID **VRXA00001** unchanged, Vita APP_VER
  **01.17**. Release source compiled with official VitaSDK master-linux-v2.540 /
  GCC 15.2. The final application build has no compiler warnings.
- SDK archive: vitasdk-x86_64-linux-gnu-2026-05-24_12-05-02.tar.bz2, SHA-256
  b1a8f4d6e41460c9ecf2c3c4590eb7eb3ea6b690767f508bd5696dbc77a4272e.
- **183 Python tests passed, no skips**, with ResourceWarning treated as an error.
  Python 3.14.9 / OpenSSL 3.5.9 and hash-locked dependencies. The suite includes
  the native receiver TLS/Opus/profile adapters and offline official CLI checks
  (Tailscale 1.104.5, ngrok 3.39.13). No live account or public tunnel was created.
- Twelve new search tests cover title/all-artist matching, Unicode case/accent
  folding, query/offset/ID bounds, stale pages, context/cache invalidation,
  legitimate short queues, the 10,000-entry safety cap and a read-only probe.
- Actual local WebSocket and paired TLS fixtures search a **synthetic 5,000-entry
  queue**, page the last entries, ignore stale requests and keep replies bounded
  to five rows / 2,096 payload bytes. Search does not emit playback commands.
- A real local WebSocket/paired TLS fixture selects upcoming song 79 of 80 with
  79 confirmed sequential skips. It retains the context and following song,
  sends progress and renews audio-hold markers during the longer jump. A second
  fixture verifies cancellation stops future skips without any play(uri).
  A virtual-clock unit case also exceeds the old 20-second overall timeout.
- **15 native C programs passed** AddressSanitizer/UndefinedBehaviorSanitizer
  checks. LeakSanitizer is disabled in this traced environment. Existing test
  scaffolding has unused-stub/sign-compare warnings; application sources do not.
- Native tests cover QPAG/QJMP lengths/counts/positions/query terminators,
  stale query/page/revision rejection, loading-row protection, touch/controller
  pagination, editing/submit/cancel, distant confirmation and jump cancellation.
  Keyboard tests include complete touch bounds, held-input suppression, text
  limits and UTF-8 deletion. Existing audio, TLS, quality and settings checks pass.
- Guarded render checks include maximum query/position text, search pages,
  keyboard, jump confirmation/progress and exact black blanking. Following the
  final singular/plural caption polish, that renderer check was rerun with both
  sanitizers and the final SDK VPK was rebuilt.
- **24 preview PNGs** were generated from the actual renderer and original
  fictional music/artwork fixtures. Search, keyboard, empty results, distant
  confirmation, progress and a synthetic large result page were visually
  inspected. The idle preview is pixel-exact RGB black. Existing player/browser,
  connection/settings/quality/capture screens are regenerated for version 1.3.
- Audio encoding/buffering, native capture helper, Opus DLL, favorites script/
  template and all four LiveArea PNGs remain byte-identical to release 1.2.
  The VPK carries the same font/dependency licenses and its eboot.bin matches
  the final SDK build output. No new native dependency was introduced.
- Search adds capability-negotiated control frames and operations; legacy
  receivers keep their 32-row queue messages. Pairing/profile, audio packet,
  capture routing, quality and saved display formats are unchanged. Both host
  and VPK must be upgraded to use the new search UI.
- Final ZIP checks cover CRC, Python syntax, required sources/guides, VPK
  identity/checksum/licenses and allowed native payloads. It excludes build
  trees/caches, runtime preferences, credentials, recordings, SDKs, and provider/
  driver/Soloist executables. The release has no real account or pairing data.

VPK SHA-256: `884767ca6b0d78ea1d881f1e87e31130aef90fe499fbafdf0bb27765cfbeee35`

Capture EXE SHA-256:
`7849ffbdc907119f552a36878cef88ba5d58e6a2b20d7fd4b050b431b94c8b8f`

Opus DLL SHA-256:
`b60905db3ed1a2b9f33be9d5c74ceb233d53f1dab5ababe27f683604e52389ff`

## Public distribution preparation

The complete Linux native/TLS/Opus build-and-check wrapper was run again after
the packaging/build-script changes: 15 native programs and all 175 Python tests
passed. Two new tests check source/ignore/icon inclusion, omission of runtime
state and foreign binaries, empty favorites and refusal to overwrite an existing
archive if the favorites template contains personal data.

GitHub workflow and issue-form YAML parses successfully. Static checks confirm
pinned official actions, read-only permissions, nonpersistent checkout tokens,
job timeouts and valid local documentation links. The existing dependency-install
commands needed YAML block scalars because their pip options contain colons.
The native wrapper invokes its child script with bash so a Windows source copy
does not need an executable mode bit. These fixes were checked locally; no
GitHub-hosted Actions execution is claimed before repository creation.

The prepared repository includes MIT/upstream notices, Git ignore/line-ending
rules, a public landing README, user/build/support/contribution/publication
guides and bug/feature/PR forms. The ZIP builder now retains .gitignore,
.gitattributes and assets/mark.svg. No Vita or PC runtime logic/native binary
was changed in this distribution pass. The maintainer reports a second user
completed local setup in about 15 minutes; this is reported feedback, not a
measured benchmark or exhaustive feature/network certification.

An extracted final archive was staged in a new temporary Git repository: 220
source/docs/runtime-library files were eligible, and the two dist output files
were ignored. Required .github files, editable icon and allowed native payloads
were included. Private-file ignore cases, native-binary exceptions, CMD CRLF /
shell LF attributes, extracted Markdown links and YAML were checked. The final
archive has 222 files; its VPK/capture-helper/Opus hashes match the preceding
1.3 application build exactly.

The recorded VPK hash describes the supplied build, not a promise that a rebuild
in another path/toolchain is byte-identical. Rebuilt outputs have newly generated
dist/SHA256SUMS.txt; local packaging does not attest to a successful remote build.

## First Windows CI follow-up

The uploaded initial Windows log (Python 3.14.10) ran 175 tests with two errors
and 14 optional/platform skips. Its mocked ngrok process reached a real Windows
Job API; the other error was a TLS relay handshake timeout. Inspection exposed
the fixture's one-shot 0.5-second accept lifetime and localhost resolution race.

The supervisor fixture now explicitly mocks the Windows job boundary, exercises
the Windows branch on Linux too, and checks assign/close/creation flags. The
relay fixture has a bounded five-second accept wait, explicit IPv4 endpoint,
650 ms delayed-client regression, EOF rejection and finally-based worker join.
No tests were removed/skipped to hide these errors; production TLS deadlines,
authentication, process containment and all application binaries are unchanged.

After the fixes, the complete **175-test suite passed with no skips** on Linux
with all optional native/CLI adapters, using Python 3.14.9 / OpenSSL 3.5.9.
As a negative control, restoring the old 0.5-second accept lifetime makes the
delayed-client relay test fail with the expected authenticated-accept timeout.
The corrected Windows branch was tested locally with mocks; the following
user-reported run showed the Windows job passing. SHA-pinned official actions were also updated to verified
Node 24 releases; their YAML, inputs and read-only/nonpersistent-token policy
were checked locally. The final VPK CI build has not yet passed.

## Dependency-download follow-up

The user's next screenshot shows Windows passing and native failing during
source download with HTTP 504, before compilation/tests. A fresh local check
downloaded/verified Opus successfully but reproduced repeated 504s from Mbed
TLS's standard release URL. Its official GitHub asset API returned the identical
5,473,689-byte archive with the unchanged pinned SHA-256.

The helper now retries temporary HTTP/network failures up to four times with
2/4/8-second waits and a 30-second socket timeout. Mbed TLS uses that official
API as a fallback after a temporary primary-URL failure. CMake has the same
alternative URL, explicit archive filename, binary Accept header and existing
required hash. No account/token, third-party mirror or generated source snapshot
is used. Wrong hashes/certificates/permanent HTTP errors fail closed. Downloads
and extraction are staged atomically to avoid incomplete cache entries.

Eight new tests cover retries, cleanup, exhaustion, invalid-cache recovery,
hash/certificate rejection, interrupted extraction and API request headers,
including a real local HTTP 504-then-success fixture. All **183 Python tests
passed with no skips** using the optional native/CLI adapters. The existing 15
native sanitizer programs passed. One local full run initially hit missing
execute permission on the cached test decoder; after correcting that local file
permission, the full suite passed. No test was skipped to hide that failure.

Fresh real downloads exercised the helper's primary-504 → official-API path and
verified/extracted the archive. A standalone CMake download/extract build using
the exact production URL/header/hash block also passed. These are source-fetch
checks, not a claimed complete GitHub/VitaSDK build. Vita/PC runtime source,
native payloads and the supplied VPK are unchanged. A new complete GitHub run
still needs to finish before publication.

## Upstream and hardware limits

Spotify's current announcement documents **up to 80 upcoming tracks**. Its API
allows get_queue(limit=0) for all available entries, not necessarily an entire
playlist. No live Spotify session was available here; synthetic 5,000-entry
success does not demonstrate Spotify returning that many entries. SEARCH.md
links the primary sources and describes the read-only Queue Availability check
for a user's actual build. Full large-playlist search needs another data source.

Actual Windows WASAPI/cable behavior, physical Vita touch/keyboard/panel handling
and sustained Wi-Fi playback have not been executed here. The Windows helper
is unchanged from its source-verified 1.1 build. The first Windows CI log is
described above; a later screenshot reports Windows green. No Windows audio-
hardware execution or completed final GitHub VPK build is claimed in this pass.
Passing automated checks is not a security audit.

Install over the existing title without deleting data and run Upgrade Host.
Check a large playlist's returned count with Queue Availability.cmd, submit a
search on Vita, page results, clear/cancel editing, and confirm no-match text.
Check L/R skip while results are open, a distant selection preserving context/
following songs, progress cancellation and stale results after context change.
Verify ordinary playback, favorites, both quality preferences, saved timeout,
OLED screen-off/wake, Local/Remote and reconnect still work on your setup.
UI_GUIDE.md and SEARCH.md describe expected behavior. Keep NETWORK_TUNING.md
and AUDIO_SETUP.md for device/network diagnosis.
