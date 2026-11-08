# Audio transport and queue changes — version 1.3.1

Keep your existing paired Vita, Soloist login, cable routing and Funnel profile.
Update both host and VPK. Opus remains 320 kbps unless you select a different
Local/Remote rate or Auto. These changes do not alter Spotify's source quality.

## Receiver-driven recovery

The receiver's PCM capacity is **2.048 seconds** (384 KiB), replacing 683 ms.
Remote playback starts/rebuffers at **1.024 seconds**, with a sender target around
one second. Local startup stays at **256 ms**. This trades about another half
second of Remote start latency for more room to absorb Wi-Fi variability.

VAQ2 feedback is sent about four times per second, carrying the actual receiver
buffer and cumulative decoded PCM frames. The host accounts for audio accepted
by PC/Funnel TCP but not yet decoded on the Vita. It does not treat a fast local
Funnel connection as proof of a fast last-hop connection.

When the receiver cushion is low and captured backlog exists, the host can send
at up to **4× real-time delivery** until its bounded window reaches the target.
Playback remains 48 kHz at normal speed. No frames are stretched or recompressed.
The host cannot manufacture future live samples; a cold start still needs time
to capture its initial cushion. It returns to real-time pacing near the target.

Missing/old feedback grants no unlimited burst. Five seconds of stale modern
feedback causes a fresh audio connection. PC capture has a bounded reserve of
about **4.096 seconds**. If it overflows, the old stream is closed rather than
silently accumulating unlimited delay or playing across missing PCM samples.
This can produce a gap after a long outage; buffering cannot restore lost audio.

The explicit 16 KiB SO_SNDBUF setting is removed so Windows can use its normal
dynamic send buffering. Application pacing still bounds the end-to-end backlog.
No system-wide TCP, registry, Wi-Fi or router tuning is performed.

## Fewer writes, same codec frames

Three existing **20 ms Opus frames** are joined into each normal **60 ms write**.
Their packet lengths/payloads are unchanged. The final short batch is sent too.
Steady audio uses roughly 16.7 writes/TLS application records per second instead
of 50. Recovery bursts can temporarily use more writes per wall-clock second.

This is not a claim of 17 TCP or Wi-Fi packets per second. A 320 kbps three-frame
batch has 2,406 application bytes, so normal MTUs require multiple TCP segments.
TCP segmentation, retransmissions and Wi-Fi aggregation vary. At lower bitrates
a batch can fit in one segment. The main benefits are lower per-write/TLS overhead
and less tiny-write scheduling; batching alone is not a guarantee against stutter.
PCM is also batched, without changing its sample format or payload bitrate.

## Skip, seek, pause and context changes

Larger buffers must not keep playing the old selection. An authenticated **AFLU**
control marker discards the current audio connection and PCM buffers while keeping
the Spotify/control connection open. The host waits for the actual playback
change, then tells the Vita to reopen audio. A fresh native capture/encoder/TLS
stream discards old audio held in kernel/Funnel queues as well as the Vita queue.

The marker has a hold/release phase. Pending changes have bounded timeouts, and
a lost control connection cannot leave the Vita held forever. A short reset keeps
the last Auto rate for the same paired Vita/route for up to two minutes; a different
fixed preference still takes effect normally. No key/account re-entry is needed.

Far-ahead queue selection advances serially through the existing queue, waiting
for the current item and queue entry to move after each skip. It takes a moment
for distant selections. It never calls play(uri) for an Up Next selection, so it
does not intentionally replace the playlist/album context or the remaining queue.
If selection starts paused, it resumes with play without a URI after reaching
the target. Duplicate songs are identified by stable entry IDs. If IDs are unavailable for
an ambiguous duplicate queue, the app asks you to use Next rather than guessing.

Explicit actions and observed early external track/position jumps reset buffered
audio. Natural transitions near a track's end retain their ordered audio; blindly
flushing those transitions would cut the tail of each song. The title/progress
are live Soloist metadata and can lead audible playback by the buffer delay.
Vita system volume remains immediate; captured Spotify volume changes can take
the buffer delay to reach your ears.

## Queue snapshots

The 10-item broadcast prefix is merged with a matching cached tail by entry ID.
A requested short snapshot is debounced for 350 ms so a broadcast immediately
ahead of the full local reply cannot collapse the visible window. Actual short
queues and context changes replace/invalidate the cached tail. Version 1.3.1
requests all available entries and sends five-row searchable pages. Spotify
documents up to 80 upcoming tracks, not the whole playlist. Songs beyond the
returned window remain in Spotify's actual queue. See SEARCH.md. Repeated
playback changes wait for completion; the jump screen provides Cancel.

Soloist has no documented request IDs distinguishing a broadcast from a query
reply, so this is a bounded merge/debounce strategy, not a new upstream correlation
guarantee. Stale selection tokens are rejected instead of starting a new context.

## Physical checks after upgrade

1. Keep Remote at 320 (or your existing choice) and play over your usual network.
   The footer should show about one second of Remote cushion when healthy.
2. Check a brief Wi-Fi hiccup, then watch the buffer recover. A complete/long
   outage may still rebuffer or reconnect; lower quality/Auto remains useful.
3. Select several songs ahead in Up Next. Confirm the playlist stays selected
   in Spotify and the following songs remain queued. Check duplicate songs too.
4. Try previous, seek, play/pause, screen-off/wake and reconnect. The old selection
   should stop promptly; Remote refilling still takes about a second plus startup
   and network overhead. Natural song transitions should keep their tail.
5. Retest Soloist-only cable isolation and physical-output mute/dongle changes as
   described in AUDIO_SETUP.md. Source capture isolation is unchanged.

These checks need actual Windows/Vita hardware. Automated synthetic/TLS/native
tests are described in [build verification](dev/BUILD_VALIDATION.md) and do not guarantee radio performance.
