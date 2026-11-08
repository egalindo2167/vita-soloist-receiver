# Maintainer release procedure

Repository: **egalindo2167/vita-soloist-receiver**. The public repository was
checked and exists with default branch main. If moving/forking it, update the
README, issue-template/support/security links. No repository or release is
created remotely by preparing a local package.

## Prepare and push source

1. Copy the prepared project contents into the cloned repository, retaining
   .git. When copying over an older checkout, merging folders does not remove
   old files: after confirming each replacement below exists, remove its old
   root copy so GitHub Desktop records the moves/deletions. Do not remove .git
   or your installed host/Vita data. Review all changes, commit to main and
   Push origin.
2. Let the branch workflow finish. It builds both Windows binaries from the
   checkout using pinned upstream inputs/toolchain, tests those exact outputs
   on Windows, runs Linux native/Python checks, then builds the Vita VPK.
3. The final packager uses pc/version.py to name the application ZIP, validates
   the native payload hashes/source commit and writes BUILD_INFO.txt plus
   SHA256SUMS.txt. Its release artifact includes that ZIP, VPK and both metadata
   files. No Soloist binary/key or private pairing/account data is included.

### Documents moved in this revision

| Old root document | New location |
| --- | --- |
| BUILDING.md | docs/dev/BUILDING.md |
| BUILD_VALIDATION.md | docs/dev/BUILD_VALIDATION.md |
| PUBLISHING.md | docs/dev/PUBLISHING.md |
| SUPPLY_CHAIN.md | docs/dev/SUPPLY_CHAIN.md |
| REVIEW_1.1.md | docs/dev/REVIEW_1.1.md |
| SECURITY_REVIEW_0.13.md | docs/dev/SECURITY_REVIEW_0.13.md |
| USER_GUIDE.md | docs/REFERENCE.md |
| SOLOIST_SETUP.md | docs/SOLOIST_SETUP.md |
| NETWORK_TUNING.md | docs/NETWORK_TUNING.md |
| TUNNEL_SETUP.md | docs/advanced/NGROK_SETUP.md |

## Create the version tag

The first public candidate in this preparation is **1.3.1**, Vita APP_VER 01.18.
The version tag must exactly match pc/version.py: **v1.3.1**. There were no public
releases/tags at the time of this review. Do not reuse a published version tag.

In GitHub Desktop, select **History**, right-click the verified release commit,
choose **Create tag**, enter **v1.3.1** and create it, then **Push origin** to push
it. Alternatively, from a Git-enabled terminal in the repository:

```powershell
git tag v1.3.1
git push origin v1.3.1
```

Do not create/publish a release manually to create the tag. The tag push starts
a fresh workflow from that tagged commit. A tag/version mismatch fails before
building. Branch/PR builds have read-only permissions and do not create releases.

## Review the CI-created draft

1. Wait for windows_payloads, windows, native and build to succeed on the tag run.
   The release_draft job then downloads that run's exact release artifact.
2. It verifies checksums, BUILD_INFO source commit/version, and that the remote
   tag still resolves to the tested commit. Only this tag-only job receives
   contents:write. It creates/updates a **draft**, never a published release.
3. Open GitHub → Releases and open that draft. Verify the tag, source commit,
   release notes and these four attached files:

| File | Purpose |
| --- | --- |
| vita-audio-receiver-1.3.1.zip | Complete application package from this tag's CI build |
| vita-audio-receiver.vpk | Same CI-built VPK also contained in that ZIP |
| SHA256SUMS.txt | ZIP and VPK hashes for these assets |
| BUILD_INFO.txt | Version, exact source commit and public CI run URL |

4. Download the draft ZIP and inspect/extract it. Confirm pc/native payloads,
   generated pc/native_hashes.py, VPK, licenses and first-time guides are present.
   Run the documented Windows/Vita acceptance checks. In particular, unsigned
   native components/Smart App Control remain an unverified compatibility limit.
5. Edit the public notes if needed, mark latest when offered, then **Publish
   release** yourself. No workflow step publishes automatically or sends a
   release announcement. The helper refuses to overwrite a public release.

**Do not replace these assets with the locally prepared ZIP**, a renamed browser
copy such as `... 3.zip`, or a locally rebuilt VPK. Local preparation is marked
as such in BUILD_INFO and is for reviewing/updating source. The public download
comes from CI. If a browser adds a suffix to a downloaded copy, that does not
change the canonical asset name produced/attached by CI.

GitHub automatically adds Source code archives; those omit the prebuilt VPK
because dist is ignored. Tell users to download the named application ZIP.
A checksum and public CI record bind files to this run, but are not Authenticode
signatures or a professional security/reproducibility audit. Native expected
hashes are generated from the actual source-built binaries; original source,
upstream/toolchain pins and public run metadata remain reviewable.

## Fix a failed run

For source fixes, update files in the clone, commit and push; Re-run jobs on an
old run still tests its old commit. For a temporary upstream outage, retry the
failed jobs after recovery. The dependency helper already has bounded retries
and a same-hash official Mbed TLS fallback. Do not bypass checks to get green.
If fixing a tagged candidate, use a new version/tag rather than moving a published
one. The existing draft can be discarded; a published release is never clobbered.

Enable Settings → Advanced Security → **Private vulnerability reporting**, keep
Issues enabled, and preserve the included MIT/upstream licenses. Code signing
is a separate certificate/provider integration; no signing credentials have
been configured or requested by this package. Pin/update CI dependencies with
[SUPPLY_CHAIN.md](SUPPLY_CHAIN.md), and record actual validation in
[BUILD_VALIDATION.md](BUILD_VALIDATION.md).

References: [GitHub tags in Desktop](https://docs.github.com/en/desktop/managing-commits/managing-tags-in-github-desktop),
[release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
and [workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

## VitaDB submission is separate

The existing title ID **VRXA00001** is retained so updates keep the same app/data.
Before a VitaDB submission, check the current catalog or ask its maintainer to
confirm that ID is available. The catalog lookup in this review was inconclusive;
GitHub publication is not a VitaDB registration or a global title-ID reservation.
Do not change an installed app's ID casually, since that creates a separate title.
