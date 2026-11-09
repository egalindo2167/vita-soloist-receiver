# Vita Audio Receiver 1.3.2 — Prerelease packaging fixes

Stream Spotify Soloist from a Windows PC to a homebrew PS Vita, with a
desktop-inspired interface, cover art, Spotify controls and upcoming-song search.
This is an unofficial community homebrew project, not a standalone Vita Spotify
client or an app endorsed by Spotify/Sony.

## Changes from 1.3.1

- Removed obsolete root guides; packaging now rejects stale or unapproved root
  files and CI checks source hygiene before rebuilding.
- Documentation points to each release's generated checksum manifests.
- Git contains native source/recipes instead of generated Windows binaries and
  loader hashes; CI builds, tests and packages the matching outputs.
- Clear source-build guidance and missing-payload setup errors.
- UI design, controls, audio quality, pairing and saved settings are unchanged.

## Download and setup

Download **vita-audio-receiver-1.3.2.zip** from the assets below and **extract it**.
It includes the Windows host, required native helper/Opus DLL, prebuilt Vita VPK,
source, licenses and step-by-step guides. GitHub's automatic Source code archives
are for developers; they do not contain the prebuilt VPK.

Start with **HOST_SETUP.md → First setup on a new PC** and **AUDIO_SETUP.md**.
Use **Setup Host.cmd** for a new PC, **Upgrade Host.cmd** for an existing host.
Install **dist/vita-audio-receiver.vpk** using VitaShell. Existing users keep
their data; use the host and VPK from this same release.

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
- Circle confirms before disconnecting from Now playing; ordinary Back behavior
  remains in the queue/settings. Updates retain the saved codec and bitrate.

## Known limits and verification

The PC must stay awake/signed in and the Vita app must remain open. Screen-off
listening is supported; full suspend, audio over games/other apps and offline
Spotify downloads are not. Spotify documents up to **80 upcoming tracks** from
Soloist; search is not whole-playlist/catalogue browsing. **SEARCH.md** explains
the limit and includes a read-only Queue Availability helper.

Opus link quality is separate from Spotify source quality and is lossy. Network
buffers cannot restore Windows driver capture gaps. Soloist is obtained/updated
separately; its account requirements, API and build expiry remain upstream limits.

Automated verification and its hardware limits are recorded in
**docs/dev/BUILD_VALIDATION.md**. Windows security can block unsigned native
components; see **docs/WINDOWS_TROUBLESHOOTING.md** before setup.

## Reporting problems

Read **SUPPORT.md**, then use the repository's bug-report form. Include versions,
route, exact steps and relevant redacted logs. Never upload keys, pairing files,
host.json, Soloist account data or private recordings. Report vulnerabilities
privately using **Security → Advisories → Report a vulnerability**.

Project code is MIT-licensed; third-party components retain their own licenses.
See **THIRD_PARTY_NOTICES.md** and **docs/dev/SUPPLY_CHAIN.md**. 
