# Build and verify

End users should download the complete application ZIP from
[Releases](https://github.com/egalindo2167/vita-soloist-receiver/releases), not
build from source. Official Soloist, Python and a virtual cable are installed
separately. Source archives do not include a prebuilt Vita VPK.

## Source checkout: build Windows payloads first

Git tracks the C source/recipes and licenses, not `pc/native/soloist-capture.exe`,
`pc/native/opus.dll`, `pc/native_hashes.py` or the native checksum manifest.
Do not run Setup Host directly from an unbuilt clone. Use the complete release
application ZIP, or build these outputs on Linux with Python 3.14, CMake, GNU
ar/ranlib/objcopy and a C compiler:

```sh
python3.14 tools/build_release_payloads.py /tmp/windows-payloads
```

This fetches the pinned Zig/Opus archives, builds both Windows payloads and
writes matching loader hashes/manifests. The generated files remain ignored by
Git. CI rebuilds them and passes those exact files to both test jobs and the
packaging job. The Linux test job needs these generated files too, because it
verifies the release payload integrity even though it cannot execute Windows
binaries. Install the hash-locked test requirements before the full test suite.

## Vita VPK

Use Linux or a suitable Linux build environment with VitaSDK installed. The
verified SDK/version and hashes are recorded in [BUILD_VALIDATION.md](BUILD_VALIDATION.md).
The exact container image used by CI is pinned in `.github/workflows/build.yml` at the repository root.

From the repository root:

```sh
export VITASDK=/absolute/path/to/vitasdk
export PATH="$VITASDK/bin:$PATH"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
python3 tools/package_release.py /tmp/release/vita-audio-receiver-1.3.2.zip
```

CMake downloads/hash-checks pinned Opus and Mbed TLS sources, so the first build
needs network access unless cached. Outputs are `build/vita-audio-receiver.vpk`
and a distributable ZIP plus `.zip.sha256`. The ZIP includes `dist/` with the VPK
and its checksum, PC scripts/native payloads, assets, licenses, source and guides.
Generated `build/`, `dist/` and release ZIPs are not committed to Git.
Use the generated checksum manifests belonging to the exact release you downloaded.
A rebuild can differ by environment/path; use its generated checksums rather
than assuming byte-identical output or an automated reproducibility attestation.

The native dependency helper retries temporary download failures up to four
times and safely discards partial downloads/extractions. Mbed TLS also has an
official release-asset API fallback in both that helper and CMake; the archive
and required SHA-256 are identical. See SUPPLY_CHAIN.md. Persistent upstream
outages can still require retrying a failed job after the service recovers.

The packager refuses a populated `pc/favorites.json`: that file must stay an
empty template. It omits private runtime files and independently downloaded
Soloist/provider/driver binaries. Use a clean checkout and inspect the output
before publication through the tagged CI draft. No ignore rule can detect every secret pasted into source.

## Python/native checks

Use Python 3.14 with TLS-PSK-capable OpenSSL. On Linux x64:

```sh
python3.14 -m pip install --only-binary=:all: --require-hashes -r pc/requirements-linux-x64.lock
python3.14 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py' -v
```

The full native/TLS/Opus check builds pinned upstream libraries and runs both
suites. Ensure `python` on PATH is that same 3.14 interpreter, plus CMake and a
native C compiler:

```sh
bash tools/build_native_checks.sh /tmp/vita-native
```

See [tests/README.md](../../tests/README.md) for optional official CLI checks and exact
native adapter setup. Without those optional programs/adapters, related tests
are reported as skipped. On Windows x64 use `pc/requirements-windows-x64.lock`
and `py -3.14` for the Python suite. Native receiver sanitizer tests run on Linux.

The bundled Windows capture helper/Opus DLL have original source/build recipes,
toolchain pins and expected hashes in [SUPPLY_CHAIN.md](SUPPLY_CHAIN.md).
CI rebuilds both from every tested checkout and generates `pc/native_hashes.py`
from those exact outputs. For a local source rebuild, use:

```sh
python tools/build_release_payloads.py /tmp/windows-payloads
```

Use trusted/fresh caches and review the results; do not weaken the loader checks. No CI credential or Spotify account is required for fake API/
synthetic-audio tests.

## UI assets

The raster font data and LiveArea PNGs are committed, so ordinary builds need
no font/image generation. `assets/mark.svg` is the editable original icon source.
Optional regeneration uses `python assets/build_assets.py` with Pillow and
DejaVu Sans available. See `tools/build_ui_font.py` for font inputs/pins and
`tests/ui_preview.c` / tests/README.md for renderer previews.

Automated tests do not replace Windows driver/Vita hardware checks. Keep claims
in release notes consistent with the tests and devices actually exercised.
