# Publish the 1.3.2 prerelease

Repository: egalindo2167/vita-soloist-receiver. Version 1.3.1 has already been
published as a prerelease. Keep its tag and assets intact; publish these fixes
under **v1.3.2** (visible version 1.3.2, Vita APP_VER 01.19).

## Update the existing clone and record deletions

1. Extract the complete prepared ZIP. Copy the contents of its inner
   vita-audio-receiver folder into the existing Git clone, preserving .git.
   Copying/merging files cannot delete obsolete tracked files by itself.
2. Open PowerShell in that repository's root and run:

```powershell
py -3.14 tools/clean_source_checkout.py
py -3.14 tools/clean_source_checkout.py --apply
```

If Git is not available to PowerShell, install Git for Windows and reopen the
terminal before running these commands.

The first command previews the changes; the second records the ten guide
removals using git rm and untracks generated native outputs using git rm
--cached. Generated native files remain on disk for local testing, but the
updated .gitignore prevents committing them again. Missing replacement guides
or modified tracked originals stop cleanup rather than forcing deletion.
The command only operates when its project directory is the Git root.

| Removed root copy | Replacement |
| --- | --- |
| BUILDING.md | docs/dev/BUILDING.md |
| BUILD_VALIDATION.md | docs/dev/BUILD_VALIDATION.md |
| NETWORK_TUNING.md | docs/NETWORK_TUNING.md |
| PUBLISHING.md | docs/dev/PUBLISHING.md |
| REVIEW_1.1.md | docs/dev/REVIEW_1.1.md |
| SECURITY_REVIEW_0.13.md | docs/dev/SECURITY_REVIEW_0.13.md |
| SOLOIST_SETUP.md | docs/SOLOIST_SETUP.md |
| SUPPLY_CHAIN.md | docs/dev/SUPPLY_CHAIN.md |
| TUNNEL_SETUP.md | docs/advanced/NGROK_SETUP.md |
| USER_GUIDE.md | docs/REFERENCE.md |

The four generated files to untrack are pc/native/soloist-capture.exe,
pc/native/opus.dll, pc/native/SHA256SUMS.txt and pc/native_hashes.py. Their
sources, build recipes and licenses stay in Git. They still ship inside the
complete application release, generated/tested by that run.

3. Run `py -3.14 tools/source_policy.py --tracked`. It must pass. Review the
   staged deletions, moved guides and other changes in GitHub Desktop. Commit
   all intended changes and Push origin. Do not upload through the web file
   uploader as a substitute: it cannot record these deletions.
4. Let the branch workflow pass. CI checks source policy, rebuilds both Windows
   payloads, then downloads those outputs into both Windows/Linux test jobs.
   Only successful tests permit the SDK VPK build and versioned packaging.

## Tag and review the CI-built draft

In GitHub Desktop History, right-click the verified release commit, choose
Create tag, enter **v1.3.2**, and Push origin. Or use a Git terminal:

```powershell
git tag v1.3.2
git push origin v1.3.2
```

Do not move/delete v1.3.1. Tag/version mismatches fail before building. After the
new tag's windows_payloads, windows, native and build jobs pass, release_draft
prepares a draft with these exact four assets:

| File | Purpose |
| --- | --- |
| vita-audio-receiver-1.3.2.zip | Complete application built/packaged by this tag's CI |
| vita-audio-receiver.vpk | Same VPK also inside the ZIP |
| SHA256SUMS.txt | Hashes of this ZIP and standalone VPK |
| BUILD_INFO.txt | Version, tested source commit and public run URL |

Download the draft ZIP and verify its manifests. No obsolete root guides should
appear. Check the new setup/source-build guidance and test playback on Windows/
Vita. The draft helper checks tag/commit identity and asset hashes and refuses
to overwrite a public release. It never publishes automatically.

Select Pre-release, review the notes, then Publish release yourself. Share its
direct version URL (or the release list); /releases/latest targets stable
releases. Enable private vulnerability reporting and keep Issues available.

Use the CI-attached application assets for public distribution. The locally
prepared ZIP is for updating/reviewing source and is explicitly labelled local
preparation in BUILD_INFO. Do not replace CI assets with that package or a
renamed browser download. Source code archives contain no prebuilt VPK or
native runtime payloads; users need the named application ZIP.

## Source builds and failed runs

Source users must generate the native payloads before running the host/tests;
see [BUILDING.md](BUILDING.md). Release and loader hashes are generated from
those actual outputs, not copied by hand into guides. A hash difference across
machines is not by itself evidence of tampering or reproducibility; no such
cross-machine guarantee is made. See [SUPPLY_CHAIN.md](SUPPLY_CHAIN.md).

A source fix requires a new commit/push; rerunning an older workflow tests the
older commit. Temporary upstream failures can be retried after recovery. Keep
the pinned hashes, bounded retries and official fallback checks intact. Record
actual validation in [BUILD_VALIDATION.md](BUILD_VALIDATION.md).

## Remaining limitations

Native Windows files are unsigned; Smart App Control and physical hardware
checks remain necessary. No signing credential/service is configured. A CI
build record and checksums are not Authenticode signatures or a security audit.
Title ID VRXA00001 is retained; confirm availability before a separate VitaDB
submission. No UI/branding changes are part of this revision.
