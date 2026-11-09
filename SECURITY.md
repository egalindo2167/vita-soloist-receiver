# Security model — version 1.3.2

## Reporting a vulnerability

Use this repository's **Security → Advisories → Report a vulnerability** for a
private report after the maintainer enables private vulnerability reporting.
Do not post an exploit, API/provider token, pairing file, host.json or Soloist
account/session data in a public issue. If the private-report button is absent,
open only a non-sensitive issue asking the maintainer to enable it; do not put
the vulnerability details there. Setup/audio bugs belong in [SUPPORT.md](SUPPORT.md).
The project has no guaranteed response window or professional security audit.

Reports/fixes focus on the latest published release; there is no promised
security backport schedule for older builds. Update both host and Vita together
when a release requires it. The threat model below describes current boundaries.

Search uses the existing paired control channel and loopback Soloist API; it
adds no listener, service account or Spotify Web API token. Queries stay in
session memory and are not deliberately logged or saved. The upstream event
bound is 16 MiB, PC indexing is capped at 10,000 entries, and the Vita receives
only five bounded rows per page. Request IDs, offsets, counts, positions and
frame sizes are checked. This is not a security audit of Spotify's local API.
The display.bin preference contains only a validated screen-timeout choice;
malformed/missing data keeps the 60-second default. Capture and transport
authentication policies remain unchanged.


## Threat model

- Unknown network peers must prove the USB pairing key before capture or commands.
- TLS protects audio/control contents; DNS/SNI, timing and traffic volume stay visible.
- Tunnel mode defaults to loopback-only listeners; direct LAN access is explicit.
- Handshake resources are bounded, but public flooding can still interrupt access.
- The Windows user and Vita credential are trusted. Same-user malware, stolen
  pairing files and Soloist's required key argument remain relevant boundaries.

Historical review changes are recorded in CHANGELOG.md. Current guarantees and
limits are described here.

## Included protection

- **TLS 1.3** encrypts and authenticates audio, commands, titles, queues and art.
  Both peers prove possession of a unique random 256-bit pairing secret.
- TLS uses **PSK with ephemeral ECDHE** (PSK-DHE). The Vita permits only this
  TLS 1.3 key exchange mode and ChaCha20-Poly1305/SHA-256 or AES-128-GCM/SHA-256.
  There are no certificates to accept blindly, password/PIN-derived keys,
  TLS 1.2 downgrade, plaintext fallback, session tickets or early data.
- Pairing happens by trusted **USB file transfer**, not unauthenticated network
  enrollment. The PC stores pairing keys using current-user Windows DPAPI;
  the exported file is intentionally a transferable secret. Its matching PC export
  is deleted after the first authenticated role handshake. It contains no Spotify/Soloist login information.
- HMAC-SHA-256 authenticates discovery requests/replies using a key derived from
  the device secret. A fresh 128-bit nonce, three-second response window and
  single-use response check on Vita reject stale/forged discovery replies.
- Each paired device has a separate identity/key. **Manage Vitas.cmd** or
  `host.py --revoke-vita ID` removes its access without changing other devices
  or the Soloist key. Active sockets recheck authorization during I/O/control
  processing; registry changes are cached for at most 0.25 seconds. In-flight
  operations or previously buffered audio may briefly finish.
- Unknown devices are rejected before capture or Spotify command processing.
  Audio/control roles are validated inside TLS. Legacy Vita listeners on
  49152/49153 and old plaintext network CLIs have been removed/retired.
- Pre-authentication uses at most eight TLS workers and four waiting sockets,
  a three-second combined TLS/role deadline per worker, and a bounded backlog.
  New arrivals rotate old unauthenticated work; proved TLS peers are not evicted
  for anonymous work. Loopback relays use these resource bounds rather than a
  single per-IP token bucket shared by everyone. Direct network sources retain
  per-IP/global attempt budgets and bounded tracking. Public floods can still
  exhaust resources; this is availability hardening, not DDoS protection. Control commands are
  limited to 20 per second with a 20-command burst. Frames, artwork chunks,
  Opus packet lengths and queues have strict bounds. These measures reduce
  resource abuse; they do not make the host denial-of-service proof.
- Soloist's WebSocket binds only to **127.0.0.1**. The Soloist key is not sent to
  the Vita, discovery, or audio/control helpers; it is redacted from child logs.
  Setup creates no public firewall exception, router forwarding or UPnP mapping.

Encryption is implemented by Mbed TLS 3.6.7 on Vita and Python/OpenSSL on PC,
not a custom encryption protocol. Pairing and discovery framing are app-specific.
The source archives are pinned and hash checked during the Vita build.

## Rotating identities and export cleanup

Receiver 1.1 keeps the same 56-byte pairing credential but sends a fresh
nonce/HMAC alias in each TLS identity and discovery query. The host searches
its bounded registry and still requires the TLS PSK proof and correct role.
The stored device ID is not sent by the new receiver. Legacy paired receivers
remain supported with their older visible IDs; SNI/public endpoints and LAN
addressing remain linkable. Discovery is authenticated, not encrypted.

New exports use pairing/DEVICE_ID/vita-pairing.bin. Successful proof deletes only
the matching export, including a matching legacy shared export. The Vita copy
and DPAPI registry remain. Deletion does not revoke a copy someone already stole;
use Manage Vitas.cmd to revoke it. TLS already derives separate traffic keys.
Deriving role keys from a stolen master would not prevent impersonation with
that master; independent asymmetric enrollment is a different future design.

## Listener scope

Automatic mode uses 127.0.0.1 and disables receiver discovery when Funnel/ngrok
is enabled. Without a tunnel it allows LAN listeners for local use. Explicit
Use Remote Only.cmd forces loopback; Use Local and Remote.cmd enables both.
Host Status reports the effective bind. Windows uses SO_EXCLUSIVEADDRUSE rather
than SO_REUSEADDR; Unix keeps SO_REUSEADDR. No Public firewall exception is added.

## Artwork and quality messages

Artwork is accepted only from recognized HTTPS Spotify CDN suffixes, port 443,
without userinfo. Redirects and inherited HTTP proxies are disabled. Download
size and image-pixel limits remain; Pillow is version/hash locked. Bounded raw
artwork chunks retain metadata priority and are slower on remote sessions.

New quality reports travel only inside the authenticated audio connection. The
parser accepts fixed 32-byte legacy or 36-byte receipt messages, known modes/rates, bounded buffer values
and a bounded report rate. No network message can run a shell or change host
code. Auto reacts to receiver buffer/rebuffer/stall signals, not a claimed
unauthenticated endpoint identity. See QUALITY.md and docs/AUDIO_PROTOCOL.md.

## Optional managed TCP tunnels

The optional Funnel and ngrok helpers publish only raw TCP forwarding for audio 48152 and
controls 48153, with loopback upstream addresses. It does not publish Soloist's
WebSocket or UDP discovery. The provider forwards the existing paired TLS bytes;
TLS is terminated at the PC audio/control helpers, not the provider. No app
pairing key or Soloist key is submitted to the relay provider. Existing revocation checks
remain effective across forwarded connections. Remote mode does not broadcast
LAN discovery or silently fall back to a Local connection.

For Funnel, receiver 1.1 sends the original DNS hostname as TLS SNI after
resolving its IP. SNI is public routing metadata and does not grant access;
PSK-DHE authentication remains mandatory. Funnel uses raw `--tcp` passthrough,
not HTTPS termination, TLS-terminated TCP or PROXY protocol. It requires no
Tailscale client on Vita. Tailscale login/keys remain with its installed PC
service; the helper saves only the CLI path and public endpoint profile.

Funnel setup refuses existing Serve/Funnel claims on 443/8443, including matching
routes not owned by this run. Two foreground watch sessions scope the routes to
the spawned CLI processes. Only those processes enter the Windows kill-on-close
job; the global Tailscale service and unrelated routes are left alone. No global
reset, persistent background route or automatic provider fallback is used.
Funnel status means the daemon configuration is confirmed, not a public
reachability check. See FUNNEL_SETUP.md for the live-account/device checklist.

For the optional ngrok path, provider authtokens are stored separately using Windows DPAPI and passed only
to the owned agent's environment, not command-line arguments or the public Vita
profile. Agent log output redacts that token. The control API listens on a
loopback-only port and is read without inherited proxies or redirects. The
exporter validates names, upstream services, TCP URL syntax, ports and size limits.
The public profile contains only addresses and ports. A modified address cannot
bypass mutual TLS authentication, but can cause failed connections/metadata exposure.

The existing host supervises its optional tunnel helper. On Windows the helper
uses a kill-on-close job for its owned agent; normal host stop allows time for
that child to exit. Other agents are not killed or reconfigured. Tunnel setup
creates no router mapping or Public firewall exception. The provider account,
its network metadata, quotas and endpoint availability remain external trust/
operational dependencies. The app is still not an independently audited public
internet service. See [Funnel setup](FUNNEL_SETUP.md) or [advanced ngrok setup](docs/advanced/NGROK_SETUP.md) for required account/device testing.

## Public Wi-Fi and remote use

On a shared network, captured audio/control packets cannot be read or modified
without the pairing key. This does not protect the Vita's other apps, Wi-Fi
stack or browser. Network operators can still observe endpoints, timing and
traffic volume, and can block/drop connections. New-client discovery exposes rotating aliases, a nonce and PC hostname in
authenticated but **unencrypted** packets; older clients also expose their ID. It is not anonymous. Use a manually saved PC IP to avoid discovery broadcasts.

As an alternative to managed TCP tunnels, a personal **VPN between your home network
and a gateway/travel router the Vita joins** can route the connection. The gateway runs WireGuard,
Tailscale or an equivalent supported VPN; the Vita does not need that VPN app.
The gateway must route the Vita's traffic to the reachable PC/VPN address and
restrict access to the host ports. A phone hotspot does not automatically route
its tethered clients through the phone's VPN; verify that capability separately.

A commercial VPN's usual public exit server does not by itself give inbound
private access to your PC. A mesh/private-network feature or personally configured
VPN gateway is needed. Vendor platform and routing support must be checked for
the chosen hardware. This release installs no VPN client or VPN gateway. Its optional managed TCP
tunnel helper can instead forward the app through an external provider; that
provider is obtained/configured separately and no relay server is bundled. Ordinary broadcast discovery normally does not cross
routed VPNs; enter the reachable PC address with Select on the Vita.

Keep Windows Firewall limited to trusted Private/VPN interfaces and peers;
avoid broad Public-profile exceptions. Do not forward TCP 48152/48153 directly
from the internet. UDP 48154 is optional when using a manual address. Existing
home/client isolation and firewall rules still apply even with correct pairing.

## Secrets and remaining trust

The Vita file at `ux0:data/vita-audio-receiver/vita-pairing.bin` is readable to
someone with filesystem/homebrew access to that Vita. A stolen file can
impersonate the device **or the host to that device**. Revoke it on the PC, then
create and USB-provision a new identity/key. Remove old credentials before giving
away a Vita. Do not include pairing files, paired-vitas.json or host.json in bug
reports, source archives or shared backups. A full malicious same-user PC process
is outside this protection: it can use DPAPI and access the normal audio session.

The managed host captures only its owned Soloist process and child processes
through Windows process loopback (build 20348+). A dedicated virtual-cable output
keeps Soloist off physical speakers, while unrelated apps remain excluded even
if routed to the cable. The helper verifies the owned PID's creation time and
executable, checks the exact configured render endpoint and live routing, and
stops on a device/process/active-route failure. It never falls back to the
Windows default. Setup is blocked until a live route has been verified, and
the native helper is hash-checked and contained in a kill-on-close Windows job.
Routing checks are periodic: they cannot prevent every first sample Windows
itself might send after a route changes. See AUDIO_SETUP.md for details.

The separate, explicitly selected SoundCard endpoint diagnostic can still
record all apps on that endpoint; it is not the managed streaming backend.
Pair only devices you control. At most 16 credentials are stored; only one
active audio/control session is served at a time. Process isolation is not a
boundary against malicious software running as the same Windows user.

Keep Python, Windows, Soloist, the Vita environment and crypto libraries updated.
Pinned versions support reproducible builds, not indefinite security. Future
crypto fixes require a rebuilt VPK/host update. This release has automated
interoperability/rejection checks but has not undergone an independent audit or
physical Windows/Vita security test; it should not be treated as a public
internet service.

## References

- Python TLS-PSK API (3.13+): https://docs.python.org/3/library/ssl.html#ssl.SSLContext.set_psk_client_callback
- Mbed TLS releases: https://github.com/Mbed-TLS/mbedtls/releases
- OWASP TLS guidance: https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html
- Windows DPAPI: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- Vita kernel random API: https://docs.vitasdk.org/group__SceRngUser.html


## Upstream key input and build dependencies

Soloist currently documents its API key only as a CLI argument. DPAPI protects
its saved copy and our logs redact it, but command-line inspection/process
telemetry can still expose it. A shell environment substitution does not remove
that argument. The key is not passed to receiver audio/control/tunnel helpers.
The upstream Soloist command-line key contract and its visibility limits remain
unchanged; historical details are linked from CHANGELOG.md.

Setup/Upgrade use exact hashed wheel locks. The third-party Opus wrapper/wheel
is removed; the Windows encoder DLL is built from pinned upstream source and
hash checked before loading. SDK/actions are pinned, with checksum generation
and Windows/native test jobs. These controls make inputs reviewable; they do
not replace an audit, signatures or Windows-user isolation. See [supply-chain inputs](docs/dev/SUPPLY_CHAIN.md).

## Version 1.1 control and pacing

VAQ2 feedback, capability flags, queue-selection tokens and AFLU hold/release
markers stay inside authenticated role-bound TLS connections. Sizes, counts,
flag values, counter progress and pacing windows are bounded. Unknown/stale queue
selections are rejected, and reset markers do not change pairing or network scope.
The audio-only reset discards old socket and capture buffers; it does not create
a plaintext path or a new inbound Vita service. See [network tuning](docs/NETWORK_TUNING.md).
