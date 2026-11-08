# Support and troubleshooting

Start with [HOST_SETUP.md](HOST_SETUP.md) and [AUDIO_SETUP.md](AUDIO_SETUP.md).
The [user guide](docs/REFERENCE.md) covers daily use and limitations. Use the latest
complete application ZIP from Releases, updating both host and Vita when asked.

## Check before opening an issue

1. Run **pc/Host Status.cmd**. Confirm the host is running under your normal
   Windows account, not waiting for a new Soloist key or an expired Soloist build.
2. Run **pc/Audio Status.cmd**. The saved virtual playback cable must be present;
   only Soloist should be routed to it. No silent fallback to speakers exists.
3. Confirm the Vita's pairing file is in the path in HOST_SETUP.md. Missing/
   revoked pairing is separate from Spotify account pairing through Connect.
4. If using Funnel, follow [FUNNEL_SETUP.md](FUNNEL_SETUP.md), checking both raw
   TCP routes and the saved public profile. First test Local if your host is
   intentionally configured to allow LAN access; Remote-only is not a LAN mode.
5. For hitches, note whether Windows capture discontinuities or Vita rebuffer
   counts increase. See [NETWORK_TUNING.md](docs/NETWORK_TUNING.md) and [QUALITY.md](QUALITY.md).
6. For search, check [SEARCH.md](SEARCH.md) and **Queue Availability.cmd**.
   Soloist's available queue window is not the full playlist.

## What to include in a bug report

Use the repository's **Issues → New issue → Bug report** form. Include app/host
versions, Windows version, Vita model/firmware, Local/Funnel/ngrok route, codec/
bitrate/Auto, exact steps and expected versus actual behavior. For connection
issues, say whether local playback works. For search, include the returned
entry count, not your private playlist or listening history.

Useful logs:

- PC: `%LOCALAPPDATA%\VitaAudioReceiver\host.log` (rotated).
- Vita: `ux0:data/vita-audio-receiver/log.txt` (replaced on launch).

Attach only the relevant **redacted** excerpt. Inspect every attachment first;
automatic redaction cannot guarantee all private information is removed. Never
attach API/provider tokens, pairing files, paired-vitas.json, host.json, Soloist
account/session data, private recordings or an installed application/data folder.
Remove personal usernames, public tunnel hostnames and track/playlist details
when they are not needed to reproduce the problem.

Use [private vulnerability reporting](SECURITY.md#reporting-a-vulnerability)
for security problems. Public issue comments are not a private support channel.
This is a community homebrew project; there is no guaranteed response time or
promise that every Windows driver, firmware, network or Soloist build is supported.
