# Windows host setup — 1.3

The PC waits in the background. The paired Vita initiates encrypted audio and
Spotify controls. This requires Windows 11 x64 (build 20348+) and Python **3.14** with TLS-PSK
support (introduced in Python 3.13). The scripts explicitly select 3.14. An older
Python fails with instructions instead of falling back to unencrypted transport.

## Existing working host

For 1.3, update both the Windows host and VPK to enable upcoming-song search.
Extract the complete new ZIP and run Upgrade Host; keep existing saved data.

For an existing 1.0 host, your cable and route verification are already saved.
Upgrade Host retains them; audio setup does not need repeating unless the device
or Soloist output route changes. Install the new VPK too. See NETWORK_TUNING.md.

1. Install VB-CABLE from https://vb-audio.com/Cable/ and restart Windows. Keep your
   physical speakers/headphones as the Windows default. See AUDIO_SETUP.md.
   Close the Vita application and extract this ZIP.
2. Run **pc/Upgrade Host.cmd**. Your protected Soloist key, account/session,
   favorites, quality/network settings and installed sign-in shortcut stay in place.
   No Soloist key prompt. The audio wizard then asks for a virtual cable and opens
   Windows Volume mixer: route only Soloist to CABLE Input and verify it. Use
   **Setup Audio.cmd** to reopen this wizard. See **AUDIO_SETUP.md** for every step.
3. Install **dist/vita-audio-receiver.vpk** over the existing Vita app.
4. If upgrading from before 0.10 or the pairing file is missing, run
   **pc/Pair Vita.cmd** once and complete the USB pairing below. Transport
   pairing is separate from Spotify Connect account pairing.

For upgrades from 0.10 or newer, keep the existing pairing file and registry; do not
repeat Pair Vita unless adding a device or replacing a revoked/lost credential.

## First setup on a new PC

1. Install VB-CABLE and restart Windows, then install 64-bit Python 3.14 from the official Python distribution. Use
   `py -3.14 --version` to confirm the interpreter.
2. Obtain your own Soloist API key and official Windows x86_64 Soloist download:
   https://developer.spotify.com/dashboard/soloist
   https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates
3. Extract the Soloist archive inside **pc/soloist/**. Keep soloist.exe and its
   companion files together; one enclosing archive directory is supported.
4. Double-click **pc/Setup Host.cmd**. It installs the PC audio/control/Opus
   dependencies, asks for your personal Soloist key once at a hidden prompt,
   protects it with Windows DPAPI, installs the host and adds current-user
   sign-in startup. Blank key input on subsequent setup keeps the saved key. It
   then opens the dedicated-cable wizard. Route only Soloist to CABLE Input in
   Windows Volume mixer and complete its live verification (AUDIO_SETUP.md).
5. Install the VPK and complete the following one-time device pairing.

## Pair a Vita once using USB

1. Double-click **Pair Vita.cmd**. A new random per-device credential is saved as
   `%LOCALAPPDATA%\VitaAudioReceiver\pairing\DEVICE_ID\vita-pairing.bin` and its folder opens.
2. On the Vita, open VitaShell and enable USB. Copy **vita-pairing.bin** into
   **ux0:data/vita-audio-receiver/**. Create that directory if it does not exist.
   From the PC, the USB drive is ux0, so copy into its `data/vita-audio-receiver/`
   folder, not an extra `ux0` folder inside the drive.
3. Close and reopen Vita Audio Receiver. It automatically finds its paired host
   on the same network and establishes TLS 1.3 connections.
4. The first authenticated connection automatically deletes the matching PC
   export. Keep the Vita's copy and protected PC registry. Do not share/upload them.
5. If Soloist has never signed into Spotify, open Spotify on phone/PC and select
   **PS Vita (PC bridge)** in the device picker. The account is remembered.

The file is a secret like a password, not a Soloist API key or Spotify token.
Use trusted USB provisioning, not unauthenticated public-network FTP. Each Vita
needs a different generated file. Re-running Pair Vita creates another device;
it does not revoke earlier ones automatically. One audio/control session is
served at a time. Keep your PC awake and signed in; the host cannot wake it.

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
Spotify's source quality. Existing 0.10–0.12 USB pairing files remain valid.

## Optional remote TCP tunnels

For access from another network without a VPN gateway, use Tailscale Funnel:
follow [FUNNEL_SETUP.md](FUNNEL_SETUP.md). Tailscale runs on the PC only; Setup
Funnel.cmd selects two managed raw TCP routes and preserves your Opus preferences.
Your Soloist key and private transport pairing stay unchanged. Triangle on the
Vita waiting screen switches Local/Remote; gear → PC connection shows Remote details. The
previous ngrok option remains in [TUNNEL_SETUP.md](TUNNEL_SETUP.md). Select one
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
Favorites, Circle back/disconnect, START exit. Repeat uses its icon. L/R skips
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

Favorites walkthrough: FAVORITES.md. Review and network changes: REVIEW_1.1.md.
