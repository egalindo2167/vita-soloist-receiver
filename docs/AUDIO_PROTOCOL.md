# Paired audio/control link 1.3.1

Audio stays on TCP 48152 at the PC host. Discovery and control ports do not
change. All multi-byte wire integers are little endian. PCM is stereo signed
16-bit, 48,000 samples/second/channel.

## Secure negotiation

All audio and control bytes are inside authenticated TLS 1.3 PSK-DHE sessions.
See ../SECURITY.md. The Vita initiates TCP to PC audio 48152/control 48153; it
has no inbound listeners. TLS 1.2, plain TCP, VRX1/VRX2 and legacy PCM fallback
are unsupported. PCM is still selectable, but always inside TLS.

Inside TLS the Vita sends `VRA3` for audio or `VRC3` for control. The server
checks the role against the port and acknowledges `VSA1`. No capture or commands
are accepted before TLS and role verification. The audio host then chooses its
configured codec. Startup acknowledgement remains encrypted too.

The host sends a 16-byte header. The receiver validates it, creates the decoder
when needed, and opens the same 48 kHz MAIN audio output as before. The receiver
then sends `VPOK` plus uint32 48000, or `VPER` plus an error code. PCM is raw
unframed interleaved samples after the handshake.

| Header offset | Bytes | PCM value | Opus value |
| --- | ---: | --- | --- |
| 0 | 4 | ASCII VPCM | ASCII VOPS |
| 4 | 4 | uint32 48000 | uint32 48000 |
| 8 | 2 | uint16 2 channels | uint16 2 channels |
| 10 | 2 | uint16 16 bits/sample | uint16 960 decoded frames/channel |
| 12 | 4 | uint32 1024 output frames | uint32 bitrate in bits/sec |

## Audio setup errors (1.0)

After TLS and VRA3/VSA1 role authentication, the host can send a 16-byte error
instead of VPCM/VOPS. The encrypted little-endian layout is `VAER` (4 bytes),
uint32 code (1..8), uint32 version (1), uint32 reserved (0). It then closes the
audio session. No decoder/port or audio acknowledgement is started for VAER.
Unknown codes, versions, flags and wrong-sized headers are rejected as malformed.
The Vita retains the specific message across retries until a real audio startup
succeeds. Its existing reconnect and OLED policy still run.

| Code | Meaning |
| --- | --- |
| 1 | Dedicated capture is not configured |
| 2 | Exact saved cable/render endpoint missing or inactive |
| 3 | Owned Soloist process missing or identity changed |
| 4 | Soloist has a mismatched active output route |
| 5 | Windows build does not support process capture |
| 6 | Native helper, routing API or WASAPI initialization failed |
| 7 | One-time Soloist/cable routing verification incomplete |
| 8 | Confirmed Soloist expired-build exit code on the PC |

The native helper's local stdout is a separate private child pipe: 16-byte
`VACP`, uint32 version 1, uint32 status, uint32 HRESULT, followed by raw PCM only
on success. Stderr carries bounded JSON errors/discontinuity counts. This pipe
is not a network listener and contains no pairing or API keys. The host supplies
only a checked PID/start-time/executable identity and selected render endpoint.
See AUDIO_SETUP.md for process-only capture versus explicit endpoint diagnostics.

## Opus payload

Each packet is uint16 length followed by that many raw Opus bytes, without an
Ogg/RTP container. Valid lengths are 1..1275; valid decoded duration is exactly
960 frames/channel (20 ms). The decoder checks duration before decoding and
rejects oversized, invalid or unsupported packets. The incremental parser
preserves partial lengths/payloads across TCP reads and stops consuming input
when another complete decoded frame would not fit the PCM queue.

The encoder uses OPUS_APPLICATION_AUDIO, OPUS_SIGNAL_MUSIC, complexity 10, CBR,
and DTX off. Default bitrate is 320000; each packet has 800 codec bytes and 2
framing bytes. Capture produces 1024-frame blocks; a sample-preserving reblocker
feeds 960-frame codec inputs. The audio engine still consumes alternating
1024-frame output buffers from the original PCM queue. No samples are discarded
to reconcile the different frame sizes. A finite diagnostic source pads its
last short codec input with silence; live capture normally runs continuously.

The protocol is unchanged by screen blanking. Opus is a lossy network transport;
the header's bitrate is not a report of Spotify's source quality. TCP/IP, Wi-Fi,
TLS, control/artwork and one-time startup overhead are outside the quoted audio rate.
Restrict firewall scope; optional raw TCP tunnels or a personal VPN can carry
remote connections. See [security](../SECURITY.md) and [Funnel setup](../FUNNEL_SETUP.md).

## Pairing file and discovery

The private 56-byte `vita-pairing.bin` still contains magic `VASEC01\0` (8 bytes),
a random ID (16 bytes) and random key (32 bytes). Receiver 1.1 sends an ASCII
TLS identity `v2:NONCE_HEX:ALIAS_HEX`, where each hex field is 32 lowercase
characters and ALIAS is the first 16 bytes of:

`HMAC-SHA256(PSK, ASCII "VitaAudioReceiver alias v2 tls" || nonce)`.

The identity nonce is fresh per connection. The host resolves the alias against
at most 16 paired keys; OpenSSL still validates the PSK binder/handshake. The
stored ID never appears in a new receiver's TLS identity. Legacy paired clients
may still use their ID's 32 lowercase hex characters. The key remains the external
32-byte TLS PSK.
Registry keys on Windows are DPAPI protected. Never bundle an actual credential.

New UDP request on 48154: `VAD2` (4), alias (16), fresh nonce (16), HMAC (32) = 68 bytes.
Alias is the first 16 bytes of HMAC-SHA256(PSK,
ASCII "VitaAudioReceiver alias v2 discovery" || nonce).
Reply: `VAH2` (4), alias (16), echoed nonce (16), audio uint16 (2), control uint16
(2), ASCII hostname zero-padded (32), HMAC (32) = 104 bytes. Integers are LE.
The MAC covers all preceding packet bytes and uses
`HMAC-SHA256(PSK, ASCII "VitaAudioReceiver discovery v1")` as its key. Reply is
accepted once, only against the latest nonce within three seconds. TLS still
authenticates the destination; discovery alone never authorizes audio/controls.
The host also answers legacy VAD1/VAH1 packets with their stored ID for older Vitas.

TLS contexts use OS entropy, no saved sessions, no early data, and no tickets.
Library versions, config, source hashes and build steps are in CMakeLists.txt,
src/tls_config.h and tests/README.md.

## Remote endpoint profile (0.11)

`ux0:data/vita-audio-receiver/remote-host.txt` is a public ASCII configuration,
not a credential. Maximum file size is 768 bytes. LF and CRLF are accepted.
Every field must appear exactly once; unknown/duplicate fields, invalid DNS
labels, noncanonical/invalid numeric IPv4 addresses, invalid ports, embedded
NULs and oversized input are rejected. The header and four fields are:

```text
VART1
audio_host=0.tcp.ngrok.io
audio_port=12345
control_host=1.tcp.eu.ngrok.io
control_port=54321
```

These are examples, not working endpoints. Hostnames may be up to 253 ASCII
characters with labels of 1..63 characters. Ports are decimal 1..65535. The Vita
resolves IPv4 endpoints on its network worker, with bounded retries. Connecting
TCP may take up to five seconds; client TLS negotiation has a ten-second bound.
TLS/role authentication is otherwise unchanged. The two services can have
different hostnames and ports. Remote mode never broadcasts discovery, selects
plaintext, or automatically falls back to the local address. Explicit Triangle
selection switches modes only while disconnected, draining pending old sockets
before the new route becomes eligible. The selected mode is saved separately
from host.txt; the existing manual Local address is preserved.


## TLS hostname routing (0.12)

Remote DNS endpoints now send the original hostname in ClientHello SNI. Numeric
IPv4/local endpoints omit it. The pairing PSK, TLS 1.3 PSK-DHE ciphers and inner
role authentication are unchanged; SNI is public routing metadata. This allows
Tailscale Funnel raw TCP passthrough without terminating app TLS at the relay.
For Funnel, both profile hostnames are the PC's public ts.net DNS name, with
audio_port=443 and control_port=8443. Do not substitute a resolved relay IP.
Opus stays at the configured bitrate, default 320 kbps.


## Live receiver feedback — 1.1

After VPOK the receiver sends **VAQ2** over the authenticated audio socket, about
once per 250 ms and promptly after a quality change. The first seven little-endian
uint32 fields are compatible with the legacy VAQ1 meanings. VAQ2 appends a cumulative
count of decoded/received PCM frames for this audio connection (uint32, modular
wrap). New connections reset the count; it is not the number of frames played.

| Offset | Field |
| --- | --- |
| 0 | ASCII VAQ2 |
| 4 | Selected mode: 0 Auto or 96/128/160/192/256/320 kbps |
| 8 | Cumulative rebuffer count for this audio session |
| 12 | Decoded PCM buffer milliseconds, bounded to 2048 |
| 16 | Output seconds played in this session |
| 20 | Playing: 0 or 1 |
| 24 | Remote route: 0 or 1 |
| 28 | Actual received CBR kbps, or 0 for PCM |
| 32 | Cumulative received PCM frames, modulo 2^32 |

Frames are exactly 36 bytes. The host also accepts legacy 32-byte VAQ1 (buffer
bound 2000 ms). Incomplete tails are bounded to 35 bytes; malformed tags/fields,
oversized reads, excessive report rate or impossible/backward acknowledgements
end the session. All auth/revocation checks remain. The receiver receipt count
lets pacing include audio buffered by TCP/Funnel before it reaches the Vita.

The VOPS header and length-prefixed 20 ms Opus packets are unchanged. The host
joins three such packets per normal 60 ms write/TLS record. CBR bitrate changes
still use OPUS_SET_BITRATE without resetting the decoder. Packet bytes * 400
continues to identify decoded bits/sec. TCP may split a batch into multiple segments.

Capacity is 96 output blocks (2048 ms); Remote prebuffer is 48 (1024 ms), Local
12 (256 ms). Receiver-driven pacing can deliver captured backlog up to 4x while
keeping normal-speed playback and a bounded window. See [network tuning](NETWORK_TUNING.md).

## Control capabilities and audio reset — 1.1

RSTA supports 16-, 24- and 28-byte payloads. All start with uint32 underruns,
buffer_ms, seconds and playing. The 24-byte form adds actual kbps and remote.
The 28-byte form appends capability bits: bit 0 supports AFLU; bit 1 supports
queue-selection tokens; bit 2 supports 1.3.1 paged search/progress. New receivers send 28 bytes immediately after connection,
then every five seconds. Unknown capability bits are ignored. Audio pacing uses
VAQ2 on the audio connection, not this lower-frequency diagnostic channel.

AFLU is an encrypted control frame with an 8-byte payload: nonzero uint32 reset
identifier and uint32 hold (0 or 1). A new tuple discards the active audio socket,
partial frame, decoder and buffered PCM. Hold 1 suspends audio-only reconnects;
hold 0 releases them after the real playback change. Metadata/control remain up.
A duplicate tuple is ignored. Hold release is bounded after loss/timeouts.
Restarting only audio discards stale app, capture, kernel and relay backlog;
old packets cannot be adopted from a pending socket after a hold/release.

Queue selections use CMND operation 12 and an opaque bounded token from QUEU's
third string field. Favorite selections keep operation 8 and a Spotify URI.
The host resolves a live queue token and serializes skip_next with confirmation;
stale/ambiguous tokens fail without a play(uri) fallback. QUEU's count/record
layout and STAT's 908-byte payload are unchanged. Tokens are used only after
RSTA capability bit 1. Legacy receivers get ordinary URI fields and no AFLU.

During a multi-step queue jump, intermediate full QUEU vectors and cover downloads
are suppressed. Final metadata is sent after selection completes, avoiding a burst
of 32-item snapshots competing with the reset/control traffic on a poor link.

Remote artwork remains around 8 KiB/s; Local around 80 KiB/s. The same TLS roles,
USB credential, rotating identity, SNI and discovery formats remain in use.

## Paged upcoming-song search — 1.3.1

The host requests all available Soloist entries with get_queue(limit=0), indexes
at most 10,000 entries and rejects upstream events over 16 MiB. This removes our
old 32-row display cap, not Spotify's documented up-to-80 upcoming window. The
host still emits legacy QUEU messages to clients without RSTA capability bit 2.
Favorites remain FAVS with the existing 32-row layout.

CMND remains 144 bytes including its tag/length header: 136-byte payload with
uint32 operation, int32 value and a zero-terminated 128-byte UTF-8 string. Added:

| Operation | Value | String | Meaning |
| --- | --- | --- | --- |
| 13 | Request ID 1..0x7fffffff | Query, up to 127 UTF-8 bytes | New search; empty query restores all available rows; starts at offset 0 |
| 14 | Filtered offset, 0..9995, multiple of 5 | Decimal current request ID | Request a result page; stale IDs ignored |
| 15 | 0 | Empty | Cancel future skips in the current jump |

New clients receive QPAG instead of QUEU. Payload is 156 + count*388 bytes:

| Offset | Type | Meaning |
| --- | --- | --- |
| 0 | uint32 | Current search request ID; 0 before the first submitted query |
| 4 | uint32 | Queue revision, wrapping modulo 2^32 |
| 8 | uint32 | Filtered result offset; multiple of 5 |
| 12 | uint32 | Total matching entries |
| 16 | uint32 | Valid searchable entries in current queue cache, at most 10,000 |
| 20 | uint32 | Flags: bit 0 upstream list truncated at PC safety cap; bit 1 waiting for initial queue |
| 24 | uint32 | Count, 0..5; exactly the remaining page size |
| 28 | UTF-8[128] | Current query, null terminated |
| 156 | Records | count records: uint32 original upcoming position (1-based), then title[128], artist[128], opaque selection token[128] |

Maximum QPAG payload is 2,096 bytes. Positions must be increasing and within
available; total must not exceed available. The receiver validates the entire
page before applying it and ignores stale query IDs, wrong pending-page offsets
and older queue revisions. A shorter changed queue can clamp to its final page.
Rows cannot be played while their replacement query/page is pending. Matching
and normalization run on the PC; typing on the Vita sends nothing until submit.

QPAG tokens still select via operation 12. The host revalidates against the live
cache, advances by confirmed skips and never substitutes play(uri). Jumps are
limited to 256 skips and 20–120 seconds overall, with six seconds per skip.
QJMP carries uint32 confirmed, uint32 total (8 bytes), with 0,0 ending progress.
Values must satisfy confirmed <= total <= 256. Only capable clients receive it.
During a longer jump, AFLU hold uses a fresh identifier every eight seconds so
the receiver's bounded hold timer stays active; completion/cancellation releases
audio with the current identifier. An already-dispatched skip cannot be undone.

No audio header, packet, pairing file, discovery or remote profile format changed.
See ../SEARCH.md for controls, source investigation and real-build measurement.
