# Publish the project on GitHub

These instructions use the owner/repository from the maintainer's new-repository
form: **egalindo2167/vita-soloist-receiver**. If either changes, update the GitHub
links in README.md, BUILDING.md and `.github/ISSUE_TEMPLATE/config.yml` too.
No repository has been created or uploaded by preparing this package.

## 1. Create the empty repository

On [GitHub's New repository page](https://github.com/new), use:

| Field | Value |
| --- | --- |
| Owner | egalindo2167 |
| Repository name | vita-soloist-receiver |
| Description | Stream Spotify Soloist from a Windows PC to a homebrew PS Vita, with playback controls, cover art, queue search, Opus audio and optional Tailscale Funnel remote access. |
| Visibility | Public |
| Add README | **Off** — the prepared project already has one |
| Add .gitignore | No .gitignore — the prepared project supplies it |
| Add license | No license — the prepared project already contains MIT LICENSE and third-party notices |

Click **Create repository**. The license choice above avoids creating a duplicate;
it does not remove the existing MIT license you will upload. GitHub recommends
not prepopulating these files when importing an existing project.

If you already created a README, keep it for now. Clone normally in the next
step and replace it with the prepared project README when copying files.

## 2. Clone with GitHub Desktop

1. Install [GitHub Desktop](https://desktop.github.com/) and sign in to your
   GitHub account. Use **File → Clone repository → URL**.
2. Enter `https://github.com/egalindo2167/vita-soloist-receiver.git`.
3. Choose a local development location, for example `C:\GitHub\vita-soloist-receiver`,
   and click **Clone**. An empty repository message is normal before its first
   commit. This folder is for source; keep it separate from the installed host.
4. In Desktop choose **Repository → Show in Explorer** to open the cloned folder.

Desktop handles Git authentication. Do not put any GitHub token, Soloist key or
transport pairing file in the source folder.

## 3. Copy the prepared project and push

1. Download the updated, pristine **vita-audio-receiver-1.3.zip** application ZIP
   and use **Extract All**. Keep the original ZIP unchanged for the Release.
2. Open its inner **vita-audio-receiver** folder. Copy **everything inside it**
   into the cloned **vita-soloist-receiver** folder. Copy `.github`, `.gitignore`
   and `.gitattributes` too. Do not place the entire inner folder one level down.
   At the repository's top level you should see README.md, LICENSE, CMakeLists.txt,
   pc, src, tests, tools, assets, sce_sys, docs and .github.
3. Return to Desktop. Inspect Changes. The source, PC native helper/Opus DLL,
   licenses, docs and workflow should be listed. Build output, dist/VPKs, release
   ZIPs and installed runtime files are ignored intentionally. Native DLL/EXE
   files under **pc/native** are intentional, hash-checked distribution files;
   **soloist.exe must not be listed**.
4. Enter summary **Initial public release 1.3** and click **Commit to main**.
   If Desktop uses a different initial branch name, use **Branch → Rename** to
   rename it to **main** before pushing, so prepared links match.
5. Click **Publish branch** or **Push origin**, whichever Desktop shows. The
   origin is the existing public repository; do not create a second repository.
6. Refresh the GitHub repository page. Confirm README renders, screenshots load,
   and src/pc/.github are at the top level. Do not upload only the ZIP as a source
   file: people need browseable source and GitHub must see the workflow/templates.

Always copy from the pristine release/source checkout, not
`%LOCALAPPDATA%\VitaAudioReceiver` or a used Soloist data folder. Ignore rules
are a backstop, not a complete secret scanner. Favorites in the source remain
an empty template. All real keys, pairing and personal favorites stay private.

## 4. Run repository checks and enable private reports

1. Open **Actions → Verify and build Vita Receiver**. The first push starts
   Windows Python/native-helper checks, Linux native/TLS/Python checks and a
   VitaSDK VPK/package build. Wait for all three jobs to succeed before publishing
   the release. A first GitHub-hosted run has not been performed by preparing
   this ZIP; inspect any red job's first failing step rather than assuming success.
2. In **Settings → Actions → General**, keep read-only workflow permissions.
   If your account restricts Actions, allow the pinned official GitHub actions
   used by the included workflow. No Spotify/provider/GitHub deployment secret
   needs to be added. This workflow uploads build artifacts, not public releases.
3. Under **Settings → Advanced Security** (the Security and quality sidebar),
   enable **Private vulnerability reporting**. Verify **Security → Advisories**
   offers **Report a vulnerability** so SECURITY.md's route actually works.
4. Keep Issues enabled. The prepared bug/feature forms and pull-request template
   appear automatically from .github after the push. No issue labels need to be
   created for those forms to work.

## 5. Create the first downloadable release

1. On the repository page click **Releases → Create a new release** or **Draft a
   new release**. Choose tag **v1.3**, create the tag if it does not exist, and
   choose target **main** at the verified source commit.
2. Title: **Vita Audio Receiver 1.3 — First public release**.
3. Paste the contents of **RELEASE_NOTES.md** into the release description.
4. Attach these three files by dragging them into the release assets box:

| Asset | Where to find it |
| --- | --- |
| vita-audio-receiver-1.3.zip | The original updated ZIP downloaded for this publication; do not re-zip an installed folder |
| vita-audio-receiver.vpk | dist/vita-audio-receiver.vpk inside the extracted ZIP |
| SHA256SUMS.txt | dist/SHA256SUMS.txt inside the extracted ZIP; checks the standalone VPK |

5. Save as **Draft** first. Confirm all three uploads have finished, tag/branch
   are correct, and the ZIP really includes the complete PC folder plus VPK.
6. Select **Set as the latest release** if offered, then **Publish release**.
   v1.3 is the first public release of the existing 1.3 application; the
   distribution-preparation pass does not change its app/host version or VPK.
7. Open the repository's **Releases/latest** link and download its application
   ZIP to a new folder. Confirm it extracts with pc and dist inside, and the
   README points to the setup instructions. GitHub also generates Source code
   archives automatically; those are for developers and lack a prebuilt VPK.

The standalone VPK checksum can be checked in PowerShell:

```powershell
Get-FileHash .\vita-audio-receiver.vpk -Algorithm SHA256
```

Compare it with SHA256SUMS.txt. A checksum checks file identity, not authorship
or a professional security audit. For future releases, use the packager's new
ZIP and its matching generated VPK/checksums, not an old build from this folder.

## 6. Finish the repository page

Use the **About** gear to add the description above and topics such as
`ps-vita`, `homebrew`, `spotify`, `soloist`, `opus` and `audio-streaming`.
Check the public README/setup/download links in a signed-out window. Keep the
project's MIT LICENSE and all third-party notices in source and distributions.
Future changes should be committed and pushed through this source checkout,
with new app versions/tags when application binaries change.

## Official GitHub references

- [Create a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [Clone using Desktop](https://docs.github.com/en/desktop/adding-and-cloning-repositories/cloning-and-forking-repositories-from-github-desktop)
- [Create a release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository?tool=webui)
- [Enable private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)
