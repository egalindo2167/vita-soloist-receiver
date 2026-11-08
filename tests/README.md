# Verification

## Dependency-download follow-up

The next user-reported run shows Windows passing, with native stopped before
compilation by HTTP 504 during dependency download. Eight new tests cover
temporary 504 recovery (including a real local HTTP server), partial-read cleanup,
four-attempt exhaustion, no retry/extract for wrong bytes, invalid/valid cache
handling, immediate failure for permanent HTTP/certificate errors, interrupted
extraction recovery and the official API fallback's binary/no-auth headers.

Fresh official Opus and Mbed TLS archives were hash-verified/extracted in the
local environment. Mbed TLS's standard URL repeatedly returned 504; the official
asset API succeeded with the identical pinned archive. A real CMake download/
extract smoke build exercised the production URL list/header/hash configuration.
All 183 Python tests pass locally with optional native/CLI adapters enabled.
The existing 15 native checks passed too. A new complete GitHub run remains
required; these checks do not certify remote service availability.

## First Windows CI follow-up

The initial uploaded Windows log ran 175 tests, with two errors and 14 expected
optional/platform skips. The fake ngrok process reached real Windows Job APIs;
the supervisor fixture now mocks that boundary explicitly and forces its
Windows branch on every test OS, checking assign, creation flags and close.
The separate real OwnedProcessJob implementation test remains in the suite.

The relay's one-shot server used the production listener's 0.5-second accept
poll as its entire lifetime. It now waits up to five seconds in the fixture and
connects to its explicit IPv4 relay address, avoiding localhost/IPv6 fallback.
A deliberate 650 ms client delay checks that the server survives beyond the old
poll interval. EOF fails rather than spinning, and the server worker is joined
in finally. Production TLS handshake deadlines/authentication are unchanged.

All 175 tests pass locally with the optional native/CLI adapters enabled. This
is Linux plus an explicitly exercised mocked Windows supervisor branch, not
evidence by itself of a successful GitHub Windows run; the following screenshot
reported that job passing as described above. Push the changed files
to start a new workflow run; rerunning the old commit does not apply the fixes.

## Public release packaging checks

The release packager's tests verify that Git ignore/attribute files, workflows/
issue forms and the editable SVG remain in the source package, while private
runtime files, recordings, account/config JSON, build caches and foreign
executables/DLLs do not. A populated favorites template must fail before replacing
an existing release archive. The Windows/GitHub-copy path calls the native test
script through bash, without relying on an executable mode bit.

## Release 1.3 additions

Search tests cover the all-available queue request, the documented 80-entry
window, a 5,000-entry synthetic index, the 10,000-entry safety cap, normalization,
multiple artists, original queue positions, context/reconnect invalidation,
five-row final pages and stale/invalid request IDs/offsets. The availability
probe sends only get_queue(limit=0), with no playback or queue mutations.

Actual local WebSocket and paired TLS fixtures carry 5,000 synthetic entries,
search/page replies and a 79-skip queue-preserving selection. They verify the
following song/context survives, audio hold IDs refresh during the longer jump,
progress is sent and cancellation stops subsequent skips. No live Spotify
account or Windows/Vita hardware is exercised by those fixtures.

The native suite checks QPAG/QJMP validation, atomic rejection of malformed
pages, stale-query/page/revision handling, loading-row protection, controller/
touch paging, keyboard edit/submit/cancel, distant confirmation and jump cancel.
Guarded render checks include search, maximum positions/query strings, the
keyboard and confirmation/progress screens, with exact black blanking.

## Release 1.2 additions

The actual control.c input mapper is checked for previous/next shoulder actions
on Queue/Favorites without changing tabs, Triangle/Left/Right navigation, queue
tokens versus favorite URIs, all four corners of each expanded transport target,
held touches, seek/volume endpoint clamping, mute/restore and touch pagination.
The pure Settings input policy checks gear/SELECT open/close, nested quality,
isolated close gestures, route/details actions and sidebar navigation. Display
preferences are tested for overwrite/reload, invalid/truncated data and missing
files; the PC-link state test checks worker staging without output-loop IO.

Screen tests include short/long/Never timeouts, persistent dimming, manual off and
wake suppression. Renderer checks use guarded framebuffers for all pages,
long/Latin-accented text, maximum lists/hostnames, artwork, both quality tabs,
every Settings row, all capture errors and exact black idle frames. The smooth
font/icons are compiled from the same sources in preview/native/SDK builds.

Screenshots in docs are generated with tests/ui_preview.c. Build a preview with:

```sh
cc -std=c11 -O2 tests/ui_preview.c src/ui_render.c src/ui_draw.c src/ui_font_data.c src/search_keyboard.c -lm -o /tmp/vita-ui-preview
/tmp/vita-ui-preview player > /tmp/vita-player.ppm
```

This does not emulate physical touch response or Sony display-off behavior.
UI_GUIDE.md lists device checks/controls. The 1.1 transport integrations remain.

## Release 1.1 additions

Receiver pacing tests use exact decoded-frame acknowledgements, bounded in-flight
windows, legacy/stale feedback, wrap/invalid counter cases, unchanged batching,
and a deterministic Wi-Fi-stall model. An actual TLS stream test blocks the sender
for 600 ms while capture/playout continue, then checks buffer recovery without a
rebuffer and verifies the original 20 ms packet sizes. A write spy confirms three
unchanged Opus frames per normal write, including final short batches.

Queue tests cover 10/full snapshot races, cached-tail matching, legitimate short
queues, context invalidation, stale tokens, duplicates, paused selection and
serial skip confirmation. A real WebSocket + paired audio/control TLS fixture
selects the sixth upcoming item, retains the context/following queue, and closes/
reopens only audio on AFLU: the new connection contains the new synthetic PCM,
not bytes buffered in the previous stream. No play(uri) is used for that selection.

Native tests exercise VAQ2 bytes/capacity, AFLU validation, hold/release/coalescing/
loss timeouts, pending-socket ownership, and actual queue-vs-favorite button/touch
command mapping. Expired-build messaging uses confirmed exit code 10, with no
assumed build/installation date. The native helper is rebuilt/hash-pinned after
its explicit agile-interface update.

These are automated/synthetic cases, not physical Wi-Fi, Windows driver or Vita
measurements. Acceptance checks: NETWORK_TUNING.md and AUDIO_SETUP.md.

## Release 1.0 additions

The suite now includes dedicated-cable selection, exact missing-device rejection,
preservation of key/network/quality/favorites settings, live routing verification,
unsupported-build rejection, and binding to the owned Soloist PID/start time/path.
Actual child pipes test startup status validation, PCM/gain, native error delivery
and child/thread cleanup; their audio data is synthetic, not Windows WASAPI.
An authenticated TLS test rejects unpaired requests before opening capture and
delivers VAER on a source error. A real local WebSocket/TLS test checks capture
guard pause, blocked track selection, and recovery without restarting the bridge.

Native C checks add the route/process-identity policy and VAER validation. OLED
renderer tests cover all seven capture-error messages with bounds/black checks.
The helper's C ABI is cross-compiled for Windows x64 with -Wall -Wextra -Werror;
its hash is verified in the Python suite. The Windows CI job also runs its
--version/--info entry points. Adding that job is not evidence it ran remotely.

Real capture isolation, Volume mixer persistence, virtual-cable behavior and
device hotplug still require the Windows/Vita checks in **AUDIO_SETUP.md**.
The Linux suite cannot execute the Windows native helper or the audio driver.

## Running the suite

Use Python 3.14 and the platform hash lock: pc/requirements-windows-x64.lock
or pc/requirements-linux-x64.lock, installed with --require-hashes --only-binary=:all:. TLS-PSK must be supported by its OpenSSL.

```sh
python3.14 -m unittest discover -s tests -p 'test_*.py' -v
```

Tests use temporary credentials with explicit registry dependency injection.
Production always uses Windows DPAPI. No environment variable disables
production authentication. Tests cover encrypted audio/controls and reconnect,
real Opus encode/decode, a fake local Soloist WebSocket, capture scheduling,
revocation, invalid credentials, TLS/plaintext downgrade rejection, malformed
registry data, discovery and bounded rate tracking. Windows APIs use mocks on
Linux; actual Windows capture, startup, DPAPI and Vita hardware need device tests.

## Native receiver checks

Build a native fixed-point Opus library separately, using the version in
CMakeLists.txt. Then from the project root:

```sh
OPUS_SOURCE=/path/to/opus-1.6.1 OPUS_LIBRARY=/path/to/native/libopus.a tests/run_native.sh
```

Fifteen native programs run with address/undefined-behavior sanitizers. LeakSanitizer
is disabled by this helper because the build environment uses a tracing sandbox.
This is not evidence of full firmware/hardware emulation.

## Exact Vita TLS client interoperability

Build Mbed TLS 3.6.7 natively with the same src/tls_config.h. The pinned archive
URL/hash are in CMakeLists.txt. For example, after unpacking it:

```sh
cmake -S /path/to/mbedtls-3.6.7 -B /tmp/native-mbedtls \
  -DENABLE_TESTING=OFF -DENABLE_PROGRAMS=OFF \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DMBEDTLS_USER_CONFIG_FILE="$PWD/src/tls_config.h"
cmake --build /tmp/native-mbedtls -j4
cc -O2 -shared -fPIC -DSECURE_NET_HOST_TEST -D_POSIX_C_SOURCE=200809L \
  -DMBEDTLS_USER_CONFIG_FILE=\""$PWD/src/tls_config.h"\" \
  -I/path/to/mbedtls-3.6.7/include src/secure_net.c \
  /tmp/native-mbedtls/library/libmbedtls.a \
  /tmp/native-mbedtls/library/libmbedx509.a \
  /tmp/native-mbedtls/library/libmbedcrypto.a -lpthread -o /tmp/vita-tls.so
VITA_TLS_TEST_LIB=/tmp/vita-tls.so python3.14 -m unittest discover -s tests -v
```

This uses the receiver's actual TLS/PSK/discovery code. Only mutexes, sockets,
clock and OS entropy adapters change to host equivalents. Tests check both
channels, record ordering, reconnect, unpaired host rejection, malformed pairing
files and discovery tamper/nonce/replay/expiry handling. Without this optional
native library, these checks are reported as skipped.

To feed an actual TLS audio stream into the native fixed-point Opus parser too,
build tests/opus_stream_test.c + src/opus_stream.c with the native Opus library,
and set VITA_OPUS_TEST_DECODER to that executable when running Python tests.

A physical device pass should verify: install over existing title, missing-file
pairing screen, USB provision, first TLS connect, playback/control/artwork,
close/reopen reconnect, screen-off continuity, revoke from PC, rejection of the
old file, and successful replacement pairing. Inspect new counter changes if
hitches occur. Do not attach credentials or private recordings to test reports.

## Remote tunnel verification (0.11)

The native suite also exercises the real PC link state code for Local/Remote
handover and pending socket adoption, plus strict remote-profile parsing.
Network stubs in pc_link_test_platform.h are state-test scaffolding, not a DNS
or Vita socket emulator. The renderer checks all remote screens with maximum
hostname lengths and guarded buffers.

Optional extra checks when running the Python suite:

```sh
cc -shared -fPIC -O2 src/remote_profile.c -o /tmp/vita-remote-profile.so
VITA_REMOTE_TEST_LIB=/tmp/vita-remote-profile.so \
VITA_TLS_TEST_LIB=/tmp/vita-tls.so \
VITA_NGROK_TEST_AGENT=/path/to/official/ngrok \
python3.14 -m unittest discover -s tests -v
```

The official ngrok v3 agent runs only `version` and `config check` here; it is
not bundled and no live public endpoint/account is provisioned by tests. The
full helper lifecycle is also exercised against a real local subprocess and
HTTP /api/endpoints fixture, including public profile export, secret redaction,
proxy avoidance and owned-child shutdown. A separate opaque TCP relay carries
actual paired audio, Spotify commands and native receiver TLS without
terminating encryption. Windows kill-on-close process-job flags and setup/key
storage are checked with mocks on Linux.

Device/account checks: generate ngrok TCP endpoints on your own account, copy
the public remote profile, select Remote mode, verify both audio and Spotify
controls, switch to a separate Wi-Fi/mobile-data network, and check screen-off
continuity. Check Local mode still works, Stop Tunnel closes remote access,
revocation works remotely, and sign-in restarts enabled tunnels. If unreserved
addresses change, export/copy the new profile before retrying. Never include
provider tokens, pairing keys or private recordings in reports.

## Funnel verification (0.12)

The native TLS client now runs through a ClientHello/SNI-gated TCP forwarder
for both roles and reconnects. Its encrypted records remain intact, no SNI
is rejected at ingress, and an unpaired host is rejected even with correct SNI.
The existing Opus/control integrations still test actual paired transport.

Set `VITA_TAILSCALE_TEST_CLI=/path/to/official/tailscale` to exercise the installed
CLI's `version` and `funnel --help` flags without logging into a tailnet or
publishing a service. A separate local CLI/state fixture runs as real subprocesses
and checks both foreground sessions, profile export, partial startup failures,
cleanup and preservation of an unrelated route. It models the documented daemon
JSON, not a live Funnel service. Windows job integration uses mocks.

Provider selection tests check explicit opt-in, no simultaneous managed ngrok,
no change to 320 kbps/Soloist key, and failure rollback. Config validation rejects
conflicts, malformed status, TLS termination, HTTPS/PROXY modes, unexpected
upstreams and routes outside the owned foreground sessions. Exporting uses only
the active provider. The official CLI and source are external references and
are not bundled with the receiver.

For live account/Windows/Vita checks, follow FUNNEL_SETUP.md: approve Funnel on
your PC, confirm public DNS, copy the public profile, use a separate Vita network,
verify audio/controls/artwork, stop/start, revocation and sign-in restart.
No live Tailscale account or public route is created by the test suite.


## Release 0.13 checks

On Linux with Python 3.14 and the Linux wheel lock installed, this builds the
hash-pinned libraries, native TLS/profile adapters and Opus decoder, then runs
the native/Python suites:

```sh
bash tools/build_native_checks.sh /tmp/vita-native
```

The script produces its own shared upstream Opus for Python tests too. Existing
optional VITA_TAILSCALE_TEST_CLI/VITA_NGROK_TEST_AGENT paths enable their offline
flag/config checks; without those two external CLIs the checks are skipped.

Additional checks cover concurrent listener admission under silent peers, real
SNI ingress with junk PSK handshakes, rotating identity/discovery aliases,
revocation, per-device export cleanup, Windows exclusive bind, tunnel-aware
scope and DLL tamper rejection. A real HTTP redirect test verifies that artwork
never contacts its redirected target. The supplied security claims and
qualifications are documented in SECURITY_REVIEW_0.13.md.

Quality tests include fragmented/coalesced/invalid feedback, fixed preferences,
Auto down/up hysteresis, startup/counter resets, stale feedback and TCP stall
signals. One encrypted SNI-relayed stream changes 128 -> 320 -> Auto 192 without
reconnecting, and the actual native Vita decoder decodes the whole changing-rate
stream. Native tests cover preference validation/persistence, feedback bytes,
settings-worker staging and quality-menu framebuffer/OLED bounds.

The workflow includes a Windows job using the actual bundled encoder DLL. The
initial Windows log and subsequent fixture corrections are described above;
the new download-fix run remains to be verified. Windows capture, Vita touch
input and sustained variable-network Auto behavior remain physical-device checks.
