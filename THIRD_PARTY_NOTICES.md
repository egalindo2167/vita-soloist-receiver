# Third-party notices

`src/debugScreen.c`, `src/debugScreen.h`, `src/debugScreen_custom.h`, and
`src/debugScreenFont.c` were copied from the debug-screen component in
https://github.com/ohquebacan/vitaspotify/tree/main/third_party/debugscreen .
The source describes the screen implementation as Vita SDK debugScreen.
The source repository's MIT license is reproduced in `VitaSpotify-MIT-LICENSE.txt`.

The embedded debug font credits Marcus R. Brown, James Forshaw and John Kelley
(2005) and specifies the PSPSDK BSD license. That license is reproduced in
`PSPSDK-LICENSE.txt`, sourced from https://github.com/pspdev/pspsdk/blob/master/LICENSE .
Retain these notices with source and binary distributions.

The smooth UI raster font assets in `src/ui_font_data.c/.h` derive from DejaVu
Sans 2.37. Bitstream/DejaVu notices and modification/distribution conditions are
reproduced in `UI-FONT-LICENSE.txt` and the VPK's `licenses/ui-font.txt`. The
original font is from https://dejavu-fonts.github.io/ . Generated UI screenshots
use original fictional music/artwork fixtures, not Spotify catalogue cover art.

VitaSDK provides compiler/linker tools and system API stubs. Project information:
https://vitasdk.org/ . These are not bundled in this package.

The Python loopback option depends on SoundCard and NumPy, installed separately.
File decoding uses a separately installed FFmpeg executable. These dependencies
are not bundled. Spotify Soloist is not bundled or redistributed.

The optional Soloist controls helper depends on websocket-client and Pillow,
installed separately through requirements-soloist.txt. These Python packages
and Spotify Soloist itself are not bundled or redistributed.

The VPK statically links the fixed-point Opus 1.6.1 decoder (Xiph.Org and
contributors), from https://www.opus-codec.org/ . Its BSD-style copyright and
license text is reproduced in OPUS-LICENSE.txt. CMake verifies the official
source archive against its published SHA-256 before building.

The Windows Opus encoder ships pc/native/opus.dll built from the pinned upstream
Opus 1.6.1 source; it no longer uses an Opus-bundling Python wheel. Opus BSD,
Zig MIT and MinGW-w64 ZPL notices are included in pc/native/licenses. The native
Soloist process-capture helper uses the same toolchain and original project C
source under the project's MIT license. Windows API import libraries reference
OS-provided components. See [supply-chain inputs](docs/dev/SUPPLY_CHAIN.md) for both build recipes.

VB-CABLE is a separately installed third-party virtual audio driver. No driver
or vendor installer is bundled. Download and licensing: https://vb-audio.com/Cable/ .

The VPK statically links Mbed TLS 3.6.7 (https://github.com/Mbed-TLS/mbedtls),
including its cryptographic dependencies distributed under the release license.
The release's complete license is reproduced in MBEDTLS-LICENSE.txt and inside
the VPK. CMake pins and checks the release archive's SHA-256. TLS 1.3 uses the
PSK with ephemeral key exchange mode only; platform entropy comes from the
Vita kernel RNG. Native verification uses the same implementation with host OS
entropy/socket adapters. PC TLS uses the Python installation's OpenSSL.

Optional remote access uses the separately downloaded ngrok agent. The agent is
not bundled or redistributed. Its provider account, terms, quotas and software
license apply independently. Our helper adds no new Python package dependency.

Optional Tailscale Funnel uses a separately installed Tailscale client and account.
The client is not redistributed. Its license, terms and bandwidth limits apply.
