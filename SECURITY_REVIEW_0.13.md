# Review of the supplied findings — release 0.13

Reviewed against the actual 0.12 sources, then verified the changes described
below with protocol, native and integration tests. This is a focused review of
the supplied list, not an independent full security audit.

| Finding | Assessment | Result in 0.13 |
| --- | --- | --- |
| 1. Shared loopback rate bucket and serial handshake | Confirmed. The old per-IP bucket combined everyone behind Funnel; inline TLS/role work blocked the accept path. | At most eight concurrent handshake workers and four waiting sockets, newest-waiting admission with rotation of old unauthenticated work, a three-second total handshake/role budget, and no shared per-IP token bucket for loopback relays. Completed TLS proofs are not evicted to admit anonymous work. Failure spikes have aggregate log notices. |
| 2. Soloist key in argv | Confirmed exposure; suggested environment/stdin replacement is not supported by the current documented CLI. | Retained the required official CLI. DPAPI storage and log redaction remain. No fake environment workaround, command-line memory editing or claim that process/audit logs are protected. See the explanation below. |
| 3. All-interface receiver listeners with a tunnel | Confirmed unnecessary exposure for remote-only use. | Automatic mode uses 127.0.0.1 and disables receiver discovery whenever Funnel/ngrok is selected. Explicit Local and Remote mode enables LAN too. Soloist's separate API remains loopback. |
| 4. Windows SO_REUSEADDR | Confirmed Windows-specific port-sharing risk. | TCP listeners use SO_EXCLUSIVEADDRUSE on Windows; Unix keeps SO_REUSEADDR. An impostor still cannot authenticate, but unnecessary port sharing is removed. |
| 5. Plaintext pairing export left behind | Confirmed. | New exports use a unique per-device subfolder. After the device proves the key and correct role, only the matching export is deleted; legacy matching exports are cleaned too. The protected registry and Vita file are retained. Revocation cleans matching exports; a locked-file deletion failure logs manual cleanup instructions. |
| 6. Stolen pairing file can impersonate either endpoint | True property of the existing mutual-PSK trust model, not a failure of TLS's separate traffic keys. | Documented boundary retained. Deriving both role keys from a stolen master would not solve it. A future independent asymmetric enrollment would require a different pairing design. Revoke and replace a stolen credential. |
| 7. Stable device ID visible | Confirmed for 0.12. | New Vita uses a fresh nonce plus a key-derived alias in each TLS identity and discovery query, rather than exposing its stored ID. Host resolves against the bounded paired registry. Legacy receivers remain identifiable; SNI/public endpoint/timing remain visible. |
| 8. Artwork redirect escapes source check | Confirmed. | Artwork redirects are rejected, inherited HTTP proxies are disabled, and initial HTTPS/Spotify-CDN/port/userinfo checks remain enforced. Download and pixel limits remain. Pillow is updated and hash locked. |
| 9. Mutable CI/dependencies/opaque Opus wheel | Confirmed hardening gaps. | SDK image pinned by digest; actions pinned by commit; managed installs require exact dependency versions and published wheel hashes. Removed opuslib-next-bundled. Ship a hash-checked Windows DLL built from pinned upstream Opus 1.6.1, with build instructions/licenses. CI adds Windows and native checks and checksum artifacts. |
| 10. Code running as the same Windows user | Correct scope boundary. | Still trusted: it can change startup scripts, unlock that user's DPAPI secrets and capture audio. No claim that transport encryption isolates same-user malware. |

## Availability qualification

The old serial blocking and small shared loopback bucket were real. The fix
improves availability and bounds memory/worker counts; it cannot guarantee that
a public internet service survives sustained network/CPU/backlog exhaustion.
No IP allowlist can recover Funnel's real external source IP in raw passthrough
mode. An unauthenticated claimed ID is never enough to bypass TLS authentication.

Two tests cover the distinction: twelve silent sockets at the app listener do
not serially block a paired reconnect, and sixteen wrong-key ClientHellos through
an actual SNI-gated opaque relay do not exhaust a shared-IP bucket before the
next valid connection. The silent-socket test applies to raw backend/LAN/TCP
access; Funnel itself needs a parseable SNI ClientHello before forwarding, so a
bare silent internet TCP socket should not be assumed to reach this backend.
These checks cover availability at the app boundary, not DDoS resistance.

## Why the Soloist argv finding remains

Spotify documents the API key as a required `--api-key` argument. Its example
using `--api-key "$SOLOIST_API_KEY"` is shell substitution: the expanded secret
still reaches the process command line. The documentation lists environment
defaults for directories, not an API-key environment or stdin interface.
Removing our CLI argument on that assumption would break startup. Stripping an
inherited variable in this app is a precaution, not proof of upstream support.

Sources checked:

- <https://developer.spotify.com/documentation/soloist/reference/command-line>
- <https://developer.spotify.com/documentation/soloist/concepts/overview>
- <https://developer.spotify.com/documentation/soloist/concepts/authentication>

Only Soloist receives that argument. Audio/control/tunnel helpers do not receive
the key. Current-user DPAPI protects the saved copy; redaction protects our own
logs. Neither protects another process's command-line view, Windows process
auditing, antivirus telemetry or crash dumps. Upstream support for a different
secret input is needed to eliminate that exposure without changing Soloist.

## Identity/privacy qualification

The pairing ID stays unchanged in the private USB credential and host registry,
so existing pairing files remain valid. The new wire identity is a domain-separated
HMAC alias of a fresh random nonce; the key itself is not sent. TLS still verifies
the PSK binder and ephemeral handshake. Replaying an observed alias does not
authenticate without the pairing key. Legacy ID-based handshakes remain accepted
only for compatibility with older paired receivers.

Funnel's DNS hostname and ClientHello SNI remain public routing metadata.
Certificate Transparency publishes names for public certificates actually issued;
it is too strong to infer that this raw PSK forwarding mode necessarily issued
a certificate just because HTTPS capability is enabled. The endpoint should be
treated as discoverable regardless. Tailscale's certificate privacy guidance:
<https://tailscale.com/docs/how-to/set-up-https-certificates>.

## Supply-chain and verification limits

See SUPPLY_CHAIN.md for exact source/SDK/action pins, DLL hash and build commands.
Hash pinning detects substitutions relative to the trusted release; it does not
audit the packages, authenticate a checksum obtained from an attacker, sign the
release, or make a mutable Windows user directory trustworthy.

The local native/Python checks and VPK cross-build run here are recorded in
BUILD_VALIDATION.md. The checked-in Windows/CI jobs have not been executed on a
remote GitHub runner here. Actual Windows DLL loading, audio capture, Vita menu
input and long remote sessions must still be exercised on the user's devices.
