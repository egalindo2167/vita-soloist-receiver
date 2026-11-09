# Changes

## 1.3.2 — distribution fixes

- Remove obsolete root guides from Git; reject stale/unapproved release-root files.
- Refer to generated release checksum manifests instead of local output hashes.
- Keep generated Windows binaries and loader hashes out of source control; CI passes fresh payloads to both test jobs.
- Add tested checkout cleanup and actionable source-build setup guidance.
- UI, controls and audio behavior are unchanged.

## 1.3.1 — first public prerelease

- Windows PC bridge with process-only Soloist capture, paired TLS, Opus/PCM,
  cover art and Spotify playback controls for a homebrew PS Vita.
- Queue/Favorites tabs, upcoming-song search, preserved playback context and
  cancellable long-jump progress; exact-black UI and screen-off listening.
- First-setup-first guides, Windows interpreter/network/security troubleshooting
  and advanced-only ngrok documentation.
- Upgrades retain the saved codec/bitrate. Circle from Now playing asks before
  disconnecting; browser/settings/search Back behavior is retained.
- Source-built Windows payloads tested on Windows, CI-built VPK and canonical
  versioned ZIP. Version tags prepare a draft with checksums and source/run
  metadata; publication remains a maintainer action.
- Standard x64 Python 3.14 preflight rejects unsupported ABI/architecture before
  installing wheels. Current native Windows components are unsigned.

Pre-public development records: [development history](docs/dev/DEVELOPMENT_HISTORY.md).
