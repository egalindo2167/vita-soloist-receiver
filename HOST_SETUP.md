# Windows host setup

Start here for a new PC and Vita. Use **Windows 11 x64**, standard 64-bit
**Python 3.14**, your own official Soloist download/API key and a virtual cable.
The PC stays awake and signed in while listening. Native Windows ARM Python is
unsupported; Windows-on-ARM x64 emulation is untested.

## First setup on a new PC

1. Download the complete application ZIP from this repository's **Releases**,
   not the automatic Source code archive or just the VPK. If you trust this
   expected release, right-click the ZIP → **Properties → Unblock → Apply**
   when that option appears, then **Extract All** to a normal local folder.
   This removes the download flag; it does not code-sign the app. See
   [Windows troubleshooting](docs/WINDOWS_TROUBLESHOOTING.md) for security blocks.
2. Put the PC and Vita on the same trusted home network for initial setup.
   On that trusted network only, open **Settings → Network & internet → Wi-Fi →
   your connected network → Network profile type → Private**. For Ethernet,
   choose its connected network's properties. Keep shared/public Wi-Fi Public.
3. Install [VB-CABLE](https://vb-audio.com/Cable/) and restart Windows as its
   installer directs. Keep your headphones/speakers as the Windows default.
   Our scripts run as your normal user. [AUDIO_SETUP.md](AUDIO_SETUP.md) explains
   the dedicated cable and Windows Volume mixer routing in detail.
4. Install the **standard x64 Python 3.14 runtime** using the
   [python.org installer or Python install manager](https://www.python.org/downloads/windows/).
   The classic installer must include its Python launcher. With the install
   manager, `py install 3.14` installs the standard runtime. Do not choose
   **3.14t/free-threaded**, 32-bit or ARM64 Python. Confirm `py -3.14 --version`
   works. Setup also checks the ABI, architecture and TLS-PSK before pip runs.
5. Obtain your own [Soloist API key](https://developer.spotify.com/dashboard/soloist)
   and [official Windows x86_64 Soloist download](https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates).
   Follow Spotify's current account/access requirements. Extract Soloist into
   **pc/soloist/** in this package, keeping soloist.exe and its companion files
   together. One enclosing archive folder is supported.
6. Double-click **pc/Setup Host.cmd**. It checks Python, installs hash-locked
   packages, asks for your Soloist key at a hidden prompt, protects it with
   Windows DPAPI, installs the host and adds current-user sign-in startup.
   If Windows asks to allow Python through the firewall, allow **Private
   networks only**, not Public. If necessary use Windows Security → Firewall &
   network protection → Allow an app through firewall to check those scopes.
   Keep the firewall enabled. See the troubleshooting link above for blocks.
7. Complete the audio wizard: choose **CABLE Input (VB-Audio Virtual Cable)**,
   select **PS Vita (PC bridge)** in Spotify on your phone/PC and start a song
   so Soloist appears in Windows Volume mixer. Route **only Soloist** to that
   exact cable at 100%, unmuted. Leave other apps at Default. Return to the
   wizard and press Enter to verify. See AUDIO_SETUP.md if two cable inputs
   appear or the route check fails. **Setup Audio.cmd** reopens the wizard.
8. Install **dist/vita-audio-receiver.vpk** on the Vita with VitaShell. Open the
   app once; it creates **ux0:data/vita-audio-receiver/** and shows its pairing
   instructions. Close it, then open VitaShell for the USB copy below.
9. Double-click **pc/Pair Vita.cmd**. Its new per-device folder opens with a
   private **vita-pairing.bin**. Copy that file by trusted USB into the Vita's
   **ux0:data/vita-audio-receiver/** folder. From the PC, the USB drive is ux0:
   use `data/vita-audio-receiver/`, not an extra `ux0` folder within the drive.
10. Close VitaShell and open Vita Audio Receiver. It discovers the paired PC
    and establishes encrypted audio/control sessions. If needed, choose
    **PS Vita (PC bridge)** in Spotify's device picker again. Spotify remembers
    that account; USB transport pairing is a separate step.

After the first authenticated connection, the matching PC pairing export is
removed automatically; keep the Vita file and protected PC registry. Each Vita
needs its own generated credential. Never share keys, account folders or pairing
files. One Vita audio/control session is served at a time. Daily use is simply
opening the Vita app while the Windows host waits in the background.

## Updating to a newer release

Close the Vita app. Extract the new complete release ZIP, run **pc/Upgrade Host.cmd**,
then install its **dist/vita-audio-receiver.vpk** over the existing Vita app.
Keep saved data. The upgrade preserves your codec/bitrate, key/login, cable
route, pairing, favorites, sign-in startup and Funnel profile. Re-pair only a
new/replacement device or a lost/revoked credential. Run Setup Audio only if
routing/device verification is missing or has changed.

## Network exposure and quality

The default **Automatic** network setting uses loopback-only receiver listeners
when Funnel/ngrok is enabled. This prevents unnecessary access from a public
LAN. Keep the Vita in Remote, even at home, or explicitly choose:

- **Use Local and Remote.cmd**: listen on LAN and loopback; authenticated local
  discovery is enabled. Keep the existing private-network firewall scope.
- **Use Remote Only.cmd**: listen on 127.0.0.1, with receiver discovery disabled.
- **Use Automatic Network Mode.cmd**: loopback with a tunnel, LAN without one.

Host Status shows the effective bind. Soloist's unauthenticated local API is
always loopback, independent of this setting. These helpers restart the host.

Use **gear → Audio quality** on the Vita for live Local/Remote fixed rates or Auto. Preferences
are saved there; see [QUALITY.md](QUALITY.md). This changes the Opus link, not
Spotify's source quality. Saved USB pairing files remain valid during ordinary updates.

## Optional remote TCP tunnels

For access from another network without a VPN gateway, use Tailscale Funnel:
follow [FUNNEL_SETUP.md](FUNNEL_SETUP.md). Tailscale runs on the PC only; Setup
Funnel.cmd selects two managed raw TCP routes and preserves your Opus preferences.
Your Soloist key and private transport pairing stay unchanged. Triangle on the
Vita waiting screen switches Local/Remote; gear → PC connection shows Remote details. The
previous ngrok option remains in [advanced ngrok setup](docs/advanced/NGROK_SETUP.md). Select one
managed provider at a time; there is no automatic fallback.

## Revocation and replacing a device

Run **Manage Vitas.cmd**, choose the listed device number, and revoke it. Its
existing audio/control sessions disconnect on their next authorization/I/O check;
there may be a brief tail of buffered audio. The old pairing file cannot
reconnect. No host restart or change to your Soloist key is required.

To re-pair, run Pair Vita again and overwrite the Vita file by USB, then reopen
the app. Delete a pairing file from a Vita you are giving away. If a PC is lost
or compromised, create a fresh host registry and provision fresh files on your
Vitas; a stolen shared key allows impersonating either endpoint until replaced.
CLI alternatives (from pc):

```powershell
py -3.14 host.py --list-vitas
py -3.14 host.py --revoke-vita DEVICE_ID_FROM_THE_LIST
```

## Firewall and addresses

Allow this host's Python/pythonw only on the trusted **Private** LAN or a
restricted personal VPN interface. Audio uses TCP **48152**, controls TCP
**48153**, discovery UDP **48154**. Setup does not create broad firewall rules,
allow Public networks, enable UPnP or forward router ports.

If discovery fails, run **Host Status.cmd** to find the PC's LAN IPv4 address.
On the Vita open **gear → PC connection**, enter that **PC address**, then X
saves/connects. Left/Right selects a field, Up/Down changes it by one, L/R by ten.
Triangle restores automatic discovery; Circle cancels editing. Enter the PC's
address shown by Host Status, not the Vita's own address.

Manual IP still requires pairing and TLS. It helps when broadcasts are blocked
but cannot bypass firewall/client isolation. Remote routed VPNs normally require
a manual reachable PC/VPN IP. See SECURITY.md for VPN gateway planning; no VPN
app is bundled or installed on the Vita. The managed TCP tunnel option needs no VPN gateway.

## Daily use and controls

Launch the Vita app to connect. The host keeps waiting when the Vita disconnects.
Closing/reopening the Vita app reconnects without PC input. Soloist pauses and
releases its active device after a short control-disconnect grace period; a quick
reconnect does not deliberately pause it.

X play/pause, L/R previous/next, Left/Right Spotify volume, Up/Down seek ten
seconds, Square shuffle (Queue: search), SELECT Settings, Triangle cycles Now playing/Queue/
Favorites, Circle back/confirm disconnect, START exit. Repeat uses its icon. L/R skips
tracks in both browsers; D-pad Left/Right switches those tabs. Touch icons,
progress/volume sliders and sidebar tabs also work. Gear → PC connection edits
the PC address; Square tests speakers while disconnected. See UI_GUIDE.md.
Vita volume buttons adjust the local listening level.

By default the screen dims at 30 seconds and turns off at 60 seconds of no
input. Gear → Screen timeout changes this; Screen off in the sidebar is immediate. The first gesture wakes without changing playback. Keep the app open;
full suspend, game/background and offline Spotify playback remain unsupported.

## Manage the host and quality

**Start Host.cmd**, **Stop Host.cmd**, **Host Status.cmd** manage the background
application, installed at `%LOCALAPPDATA%\VitaAudioReceiver\app`. It starts under
your signed-in account, not before sign-in. To remove its startup shortcut:
`py -3.14 host.py --remove-startup`. Stop Host stops the current instance.

**Use PCM.cmd** switches to PCM. **Use Opus 320.cmd** restores Opus. Both are
still encrypted. Reopen the Vita app after a change. For another local Opus rate:
`py -3.14 host.py --audio-codec opus --bitrate 256` (96/128/160/192/256/320).
Spotify's source quality is separate; see README.md. Encryption adds a small
amount of overhead to the 40,100 B/sec framed Opus stream.

Favorites stay in `%LOCALAPPDATA%\VitaAudioReceiver\favorites.json`:

```powershell
py -3.14 favorites.py add "PASTE_SPOTIFY_LINK_HERE" --name "My playlist"
py -3.14 favorites.py list
py -3.14 favorites.py remove 1
```

Full Spotify catalogue/library browsing still uses Spotify on your phone/PC.
Queue's new search filters the available upcoming window, documented by Spotify
as up to 80 tracks. **Queue Availability.cmd** makes a read-only measurement of
your running Soloist build. See **SEARCH.md** for steps and limitations.

## Troubleshooting and diagnostics

- **Pairing screen:** copy the generated file to the exact Vita path and reopen
  the app. A missing/malformed credential prevents all network connection attempts.
- **Waiting for paired PC:** confirm Host Status, upgrade both ends, check Wi-Fi/
  firewall, and ensure this Vita's ID is still listed. An old host or revoked key
  cannot be used as a plaintext fallback.
- **Python/TLS-PSK error:** install/update Python 3.14. Keep using that same
  interpreter; `py -3.14 -c "import ssl; print(ssl.HAS_PSK)"` should print True.
- **Missing modules:** run Setup Host or install all three requirements files with
  `py -3.14 -m pip install -r requirements-loopback.txt -r requirements-soloist.txt -r requirements-opus.txt`.
- **Soloist key unlock failure:** run Setup Host under the normal Windows account
  and enter the key again. DPAPI credentials generally do not transfer to another PC.
- **Soloist expires/exits code 10:** get a newer official build and rerun Setup
  Host or restart the installed host. This app cannot bypass Soloist account/build
  restrictions. Close older manual launchers before starting the persistent host.
- **Capture output missing/mismatch:** run Setup Audio.cmd or Audio Status.cmd.
  Keep only Soloist routed to the saved virtual cable. Other PC audio stays on
  its normal outputs. This backend never falls back to the Windows default.

PC log: `%LOCALAPPDATA%\VitaAudioReceiver\host.log` (rotated, Soloist key redacted).
Vita log: `ux0:data/vita-audio-receiver/log.txt` (replaced on app launch).
Windows capture discontinuities, dropped capture blocks and Vita rebuffer counts
are distinct diagnostics; note which increases during a hitch. The capture worker
still uses audio scheduling, pacing, prefill and cover-art throttling. Buffering
can absorb delays, not restore samples lost by the audio driver.

Live source diagnosis: **Audio Status.cmd**. For an explicit whole-endpoint diagnostic,
use `py -3.14 send_audio.py --list-devices`, then `py -3.14 send_audio.py --capture-only capture-only.wav --device "EXACT OUTPUT ID" --seconds 15 --gain 0.5`.
That optional WAV can contain every app on that endpoint; the managed stream does not.
The old unencrypted sender and manual Soloist launcher are retired.

See tests/README.md for verification and physical Windows/Vita testing limits.

Favorites walkthrough: [FAVORITES.md](FAVORITES.md). Network diagnostics: [network tuning](docs/NETWORK_TUNING.md).
