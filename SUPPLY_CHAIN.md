# Supply-chain inputs — receiver 1.3

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
`b60905db3ed1a2b9f33be9d5c74ceb233d53f1dab5ababe27f683604e52389ff`

The loader checks that hash before loading the full installed path. Windows
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

Use fresh or trusted build caches. Review the output and update the pinned hash
in pc/opus_audio.py only when deliberately replacing the release DLL. Build tool
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
Check the new executable before deliberately updating `HELPER_SHA256` in
pc/audio_source.py. The loader verifies the shipped helper's hash before running
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

The build workflow now pins these external actions/image:

- actions/checkout (v4): `11d5960a326750d5838078e36cf38b85af677262`
- actions/setup-python (v5): `a26af69be951a213d495a4c3e4e4022e16d87065`
- actions/upload-artifact (v4): `ea165f8d65b6e75b540449e92b4886f43607fa02`
- VitaSDK: `vitasdk/vitasdk@sha256:acd15285e1ae473e925c6f83fa41e2de45eb8b9e8ba89be7df03e194c35c11d3`

CI runs Windows Python/encoder tests and Linux native/TLS/protocol tests before
building the VPK. The release packager emits the ZIP/VPK SHA-256 sidecar and
**dist/SHA256SUMS.txt**; the bundled DLL has its own checksum file. The local
checks actually executed are in BUILD_VALIDATION.md. Merely adding this workflow
does not mean a remote CI job has run or an artifact is cryptographically signed.

The SDK container and Python/runtime dependency contents are upstream trust
inputs. Exact pins make changes reviewable; they are not a full supply-chain
security audit. Treat any real Soloist data, pairing files or provider tokens
as private inputs and keep them out of release packages.
