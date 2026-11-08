# Supply-chain inputs — receiver 1.3.1

The managed Windows Setup/Upgrade helpers install only wheel files with exact
versions and SHA-256 hashes from **pc/requirements-windows-x64.lock**, using
`pip --require-hashes --only-binary=:all:`. The analogous Linux lock is for
native CI/tests. Their downloaded wheel hashes were checked against the
corresponding PyPI release metadata. Runtime installs do not use version ranges.
Compatibility requirements .txt files forward to the Windows lock.

## Opus on Windows

The third-party `opuslib-next-bundled` dependency is removed. The receiver uses
a small ctypes binding to the upstream C ABI and ships **pc/native/opus.dll**.
It is built from the upstream **Opus 1.6.1** archive, checked against the source
hash also used for the Vita decoder:

`6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1`

Source: https://downloads.xiph.org/releases/opus/opus-1.6.1.tar.gz

Windows DLL SHA-256:
`bedfd641d5bf47bef9af4c7bcb47da6f509c3c012809d6b87e283fdadfb94b17`

This hash identifies the locally prepared 1.3.1 DLL. CI builds can have different
hashes; each package generates `pc/native_hashes.py` from its actual build and
the loader checks that expected hash before loading the full installed path. Windows
uses safe DLL search flags; it does not select an Opus DLL from PATH or the
working directory. The PE is x86-64 and imports only Windows Kernel32/UCRT
components, with no third-party runtime DLL dependency. Its native Windows ABI
still needs the Windows tests/device pass; Linux cannot execute this DLL.

Built on Linux using official Zig 0.15.2, target `x86_64-windows-gnu`, CMake Release,
shared Opus, DRED/OSCE off, and GNU objcopy --strip-debug. Zig archive:
https://ziglang.org/download/0.15.2/zig-x86_64-linux-0.15.2.tar.xz

Zig archive SHA-256:
`02aa270f183da276e5b5920b1dac44a63f1a49e55050ebde3aecc9eb82f93239`

Rebuild on Linux with Python 3.14, CMake, GNU ar/ranlib/objcopy:

```sh
python tools/build_windows_opus.py /tmp/windows-opus /tmp/windows-opus/opus.dll
```

Use fresh or trusted build caches. To rebuild both binaries and generate the
expected-hash module/manifest together, run `python tools/build_release_payloads.py
/tmp/windows-payloads` from the repository root. CI also binds that module to
the tested source commit. Do not replace a binary without updating its verified
metadata through that recipe. Build tool
paths/versions can change binary layout; this is a source/build recipe, not a
claim of byte-identical output on every machine. DLL notices are included in
**pc/native/licenses/** (Opus BSD, Zig MIT, MinGW-w64 ZPL). The source archives
are not bundled; no Spotify/Soloist executable is redistributed.

## Native Windows Soloist capture

The release also ships **pc/native/soloist-capture.exe**, original source in
**pc/native_src/soloist_capture.c** and **capture_policy.h**. It uses Microsoft's
public COM/WASAPI process-loopback API, includes only the named process tree,
and uses the exact saved cable endpoint for route checks. No driver or Microsoft
sample binary is bundled. VB-CABLE is installed separately under its vendor terms.

The helper is x86-64, built with the same hash-pinned official Zig 0.15.2 toolchain:
`-std=c11 -O2 -Wall -Wextra -Werror -municode`, Windows GNU/UCRT target, linking
only Windows OLE32, MMDevAPI, AVRT, Propsys and UUID API import libraries. Runtime
imports are Windows components. MinGW-w64/Zig runtime notices remain in
pc/native/licenses. The helper source is covered by this project's MIT LICENSE.

Rebuild on Linux: `python tools/build_windows_capture.py /tmp/windows-capture /tmp/windows-capture/soloist-capture.exe`.
The locally prepared 1.3.1 helper SHA-256 is
`edb76237cb796b12d7c9258ba82e7a090c9c68409f40002583b843a475f8bd35`.
The combined recipe generates `HELPER_SHA256` in `pc/native_hashes.py`;
the loader verifies the shipped helper's hash before running
it from the full application path. Both native binaries are listed in
pc/native/SHA256SUMS.txt. The CLI accepts a PID/start-time/path identity and a
render endpoint, never a Spotify API key or pairing credential. Process-tree
capture requires Windows build 20348+ and has not been executed on actual
Windows audio hardware in this build environment.

## Vita and CI

The smooth UI raster glyphs are derived from DejaVu Sans 2.37, with the original
font license/copyright in **UI-FONT-LICENSE.txt** and inside the VPK. The named
raster asset is Vita UI Sans. **tools/build_ui_font.py** records the exact input
TTF hashes and uses Pillow's BASIC layout engine; generated **src/ui_font_data.c**
and .h are shipped, so building/using the app does not download fonts or run a
font generator. Typography changes can be regenerated with the pinned inputs
and Pillow from the existing platform lock. Icons are original code-drawn shapes;
no Spotify logo, music catalogue images or third-party icon package is bundled.


Mbed TLS remains 3.6.7, source SHA-256:
`a7e8bcbec0e6f761b4af24f25677626b35f762f68eef79c08677a363212d11f6`.
Opus/Mbed TLS fetches in CMakeLists.txt and tools/fetch_build_sources.py both
verify their archive hashes. Review both when updating them.

The native source helper makes at most four attempts after temporary HTTP/network
errors, waiting 2/4/8 seconds between attempts, with a 30-second socket timeout.
It publishes only a complete hash-verified temporary download, replaces invalid
cached archives, and extracts into a staging directory before publishing source.
Checksum failures, certificate errors and permanent HTTP errors are not bypassed.
Retry diagnostics go to stderr so the CLI's stdout remains a usable source path.

If Mbed TLS's standard release URL times out, both the helper and CMake can use
the **official GitHub API for the same public release asset**:
https://api.github.com/repos/Mbed-TLS/mbedtls/releases/assets/464469768 .
The request specifies `Accept: application/octet-stream`; no GitHub/Spotify key
is used. The returned 5,473,689 bytes were independently SHA-256 checked against
the unchanged a7e8bcb... pin above. This is not a third-party mirror or a
GitHub-generated source snapshot. A persistent upstream outage/rate limit can
still stop a build after bounded retries; no error is treated as a passing check.

The build workflow now pins these external actions/image:

- actions/checkout (v6.0.3): `df4cb1c069e1874edd31b4311f1884172cec0e10`
- actions/setup-python (v6.0.0): `e797f83bcb11b83ae66e0230d6156d7c80228e7c`
- actions/download-artifact (v8.0.2): `9000827ccba6bdab643e8b6fd33ac0654aef8333`
- actions/upload-artifact (v6.0.0): `b7c566a772e6b6bfb58ed0dc250532a479d7789f`
- VitaSDK: `vitasdk/vitasdk@sha256:acd15285e1ae473e925c6f83fa41e2de45eb8b9e8ba89be7df03e194c35c11d3`

Each action's tag-to-commit mapping was checked against its official GitHub API
reference, and action.yml at that exact commit declares Node 24. The selected
download action supports the name/path inputs used here and treats an artifact
digest mismatch as an error by default. Checkout credentials are not persisted.

CI first rebuilds the Windows EXE/DLL from this checkout using the pinned
Zig/Opus sources, then generates native hashes and source-commit metadata. The
Windows test job downloads and exercises those exact outputs. Linux native/TLS/
protocol tests must also pass before the SDK job builds the VPK and packages
the same tested Windows payloads. Artifact downloads select this workflow run,
not a similarly named artifact from another run or repository.

`tools/package_release.py --release-dir` emits the canonical versioned ZIP,
standalone VPK, SHA256SUMS.txt and BUILD_INFO.txt. The ZIP includes the same VPK,
its dist checksum and native hash manifest. BUILD_INFO records the exact source
commit and public run URL; local preparation is explicitly marked as local.

Only a matching version-tag push can run the draft-release job. Other jobs have
contents:read; that final job alone has contents:write. It validates asset
hashes/version/source and the remote tag before attaching this run's files to
a draft. It refuses an already published release. A maintainer reviews and
publishes the draft; the workflow never auto-publishes or announces it.

These EXE/DLL files are currently **unsigned**. Public source, hashes and a CI
record are not Authenticode signatures. Signing would require a separately
configured trusted certificate/provider and signing after build but before
hash generation/testing/packaging. No signing credential/service is configured.
Smart App Control enforcement has not been tested; see
[Windows troubleshooting](../WINDOWS_TROUBLESHOOTING.md). Checks actually run
here are recorded in [BUILD_VALIDATION.md](BUILD_VALIDATION.md). No completed
remote run of the revised workflow is claimed by preparing these files.

The SDK container and Python/runtime dependency contents are upstream trust
inputs. Exact pins make changes reviewable; they are not a full supply-chain
security audit. Treat any real Soloist data, pairing files or provider tokens
as private inputs and keep them out of release packages.
