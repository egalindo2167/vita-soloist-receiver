# Release 1.3.2 verification

## Scope

This revision corrects distribution/source hygiene after the public v1.3.1
prerelease. The app/host display version is 1.3.2, Vita APP_VER is 01.19 and the
LiveArea revision is 19. Title ID VRXA00001, UI design, controls, transport,
codec behavior and saved settings remain unchanged. A new tag is required;
published v1.3.1 assets and its tag must not be replaced.

## Checks for this revision

The cleanup regression creates a real temporary Git repository with all ten
obsolete guides and the four generated native outputs tracked. It verifies a
preview makes no changes, applying cleanup records the guide deletions and
untracks generated files while preserving their local bytes, repeated cleanup
is safe, and a missing replacement prevents deletion. CI separately rejects
tracked native outputs and obsolete guides before building.

Archive tests reject every stale guide and any unknown root document, allowing
current files and their relocated guides. Packaging rejects these cases before
overwriting a previous archive. A tampered/stale native checksum manifest also
fails even when the binaries and generated loader hashes otherwise match.
Setup preflight gives source users an actionable missing-build message.

The full native/Python wrapper is run with Python 3.14.9 / OpenSSL 3.5.9,
hash-locked dependencies and optional native TLS/profile/Opus plus offline
provider CLI adapters. See the verification result at the end of this document.
The Vita VPK is cross-built with official VitaSDK master-linux-v2.540 / GCC 15.2.
The source archive's upstream SDK digest is recorded in prior development
history; no fixed output-binary digest is copied into this guide.

## Verify files from the release you downloaded

| Files | Authoritative generated checksum record |
| --- | --- |
| Application ZIP and standalone VPK | SHA256SUMS.txt attached to that GitHub Release |
| VPK inside the application ZIP | dist/SHA256SUMS.txt inside that ZIP |
| Windows capture helper and Opus DLL | pc/native/SHA256SUMS.txt inside that ZIP |

`pc/native_hashes.py` must agree with the native manifest and actual files.
`BUILD_INFO.txt` identifies the version, exact CI source commit and run URL;
CI-generated native metadata binds to that commit. Locally prepared packages
are explicitly labelled local preparation. A binary rebuilt on another machine
may have different bytes; checksums are neither signatures nor a claim of
reproducible builds. No handwritten local output hashes are verification targets.

## CI and hardware limits

The official GitHub API confirmed that v1.3.1 is a published prerelease, and that
main still tracks the ten obsolete root guides. The fix's Git cleanup must be
committed in that repository; extracting a ZIP alone cannot record deletions.
The 1.3.2 workflow has not yet been run on GitHub. Its source-built Windows
payloads must pass the Windows tests, Linux tests, SDK build and draft checks
before publication. [PUBLISHING.md](PUBLISHING.md) gives the exact procedure.

This environment cannot exercise physical Windows audio routing, Smart App
Control or Vita firmware/touch/screen-off/Wi-Fi behavior. Windows binaries are
unsigned. Passing automated checks is not an independent security audit.
Title-ID availability still needs confirmation before a separate VitaDB
submission. Install new VPKs over the existing title without deleting data.

Check playback, queue/search, favorites, quality preferences, reconnect and
screen-off listening using the host and VPK from the same CI-created release.
For first setup follow [HOST_SETUP.md](../../HOST_SETUP.md) and
[AUDIO_SETUP.md](../../AUDIO_SETUP.md). [SEARCH.md](../../SEARCH.md) documents
Soloist's returned-queue limits; synthetic large-queue tests do not demonstrate
whole-playlist availability. Branding and dialog wording are unchanged.

## Local verification result

The full native wrapper completed successfully: **200 Python tests passed with
no skips**, ResourceWarning treated as error, plus **15 native C programs** with
address/undefined-behavior sanitizers. Both official provider CLI offline checks
and native TLS/profile/Opus adapters were enabled. The 1.3.2 / 01.19 VPK SDK
build completed successfully. No live provider account, remote release write,
GitHub push or physical Windows/Vita execution was performed.

Final packaging checks cover generated manifests, matching VPK contents,
allowlisted root files, absence of private data, complete licenses and source
staging with generated files ignored. Renderer previews were regenerated for
the version label only; no layout, color, icon or disconnect wording changed.
