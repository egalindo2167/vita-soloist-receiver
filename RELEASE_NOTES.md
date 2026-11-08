# Vita Audio Receiver 1.3 — First public release

Stream Spotify Soloist from a Windows PC to a homebrew PS Vita, with a
desktop-inspired interface, cover art, Spotify controls and upcoming-song search.
This is an unofficial community homebrew project, not a standalone Vita Spotify
client or an app endorsed by Spotify/Sony.

## Download and setup

Download **vita-audio-receiver-1.3.zip** from the assets below and **extract it**.
It includes the Windows host, required native helper/Opus DLL, prebuilt Vita VPK,
source, licenses and step-by-step guides. GitHub's automatic Source code archives
are for developers; they do not contain the prebuilt VPK.

Start with **HOST_SETUP.md → First setup on a new PC** and **AUDIO_SETUP.md**.
Use **Setup Host.cmd** for a new PC, **Upgrade Host.cmd** for an existing host.
Install **dist/vita-audio-receiver.vpk** using VitaShell. Existing users keep
their data; version 1.3 search needs both host and VPK updated.

Requires a homebrew Vita, Windows 11 x64 PC kept awake/signed in, 64-bit Python
3.14, a separately installed virtual cable, and your own official Soloist
download/API key. No Soloist binary, driver installer, account/key, pairing file
or personal configuration is included. Each user creates their own pairing.

## Included features

- Now playing, Queue and Favorites; cover art and track/artist/album metadata.
- Play/pause, previous/next, seek, Spotify volume, shuffle and repeat.
- Upcoming-song title/artist search with touch/controller keyboard, case/accent
  folding, paged results and original queue positions. Distant selections use
  confirmed skips to preserve the playlist and show cancellable progress.
- Opus 96–320 kbps with separate Local/Remote preferences and opt-in Auto, plus
  PCM. Audio batching, receiver feedback and larger Remote buffers help jitter.
- Persistent Windows host, dedicated-cable/process-only Soloist capture and
  optional current-user sign-in startup.
- Mandatory paired TLS 1.3, USB pairing/revocation and optional Tailscale Funnel
  remote access. Funnel is optional; local setup is a separate first step.
- Original LiveArea icon, exact-black UI, dimming and screen-off listening.

## Known limits and verification

The PC must stay awake/signed in and the Vita app must remain open. Screen-off
listening is supported; full suspend, audio over games/other apps and offline
Spotify downloads are not. Spotify documents up to **80 upcoming tracks** from
Soloist; search is not whole-playlist/catalogue browsing. **SEARCH.md** explains
the limit and includes a read-only Queue Availability helper.

Opus link quality is separate from Spotify source quality and is lossy. Network
buffers cannot restore Windows driver capture gaps. Soloist is obtained/updated
separately; its account requirements, API and build expiry remain upstream limits.

See **BUILD_VALIDATION.md** for actual automated results and unverified hardware
behaviors. Encrypted fixtures use synthetic queues/audio, not a live Spotify
account. The maintainer reports a second user's local setup took about 15
minutes with relatively straightforward instructions; that is individual
feedback, not a timing guarantee or full remote/hardware certification.

## Reporting problems

Read **SUPPORT.md**, then use the repository's bug-report form. Include versions,
route, exact steps and relevant redacted logs. Never upload keys, pairing files,
host.json, Soloist account data or private recordings. Report vulnerabilities
privately using **Security → Advisories → Report a vulnerability**.

Project code is MIT-licensed; third-party components retain their own licenses.
See **THIRD_PARTY_NOTICES.md** and **SUPPLY_CHAIN.md**. This public packaging pass
adds distribution/support files and retains the tested 1.3 application binaries.
