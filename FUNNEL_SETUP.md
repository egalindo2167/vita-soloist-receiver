# Remote access with Tailscale Funnel — receiver 1.3

Keep **Opus 320 kbps**, or choose a lower fixed rate/Auto on the Vita, and use it from a different
network. Tailscale runs on the Windows PC only. The Vita uses the public Funnel
hostname, so it needs no Tailscale client, VPN gateway or Raspberry Pi. Keep the
PC awake, connected to the internet and signed into Windows.

Funnel forwards two raw TCP connections. The app still authenticates both ends
with the existing USB pairing secret and encrypts audio, controls, titles and
artwork with TLS 1.3 PSK-DHE. Receiver 1.1 retains the TLS hostname (SNI) required
for Funnel routing. Install the new VPK and host together; rotating identities require the new host. A browser HTTPS
test is not a valid playback/authentication test for these PSK endpoints.

## 1. Update the two apps

1. Close Vita Audio Receiver and extract the 1.3 ZIP into a new PC folder.
2. Run **pc/Upgrade Host.cmd**. It updates/restarts the installed Windows host,
   installs required Opus dependencies and selects Opus **320 kbps**. It keeps
   your Soloist login/key, transport pairing, favorites and existing sign-in startup.
3. Transfer **dist/vita-audio-receiver.vpk** to the Vita and install it with
   VitaShell over the current app. Do not delete the app or its data first.
4. Keep your existing **ux0:data/vita-audio-receiver/vita-pairing.bin**.
   Existing users of 0.10 or later do not need to run Pair Vita again. For a
   first-time host or missing pairing file, complete [HOST_SETUP.md](HOST_SETUP.md).

## 2. Install and connect Tailscale on the PC

1. Get the current official Windows installer:
   <https://tailscale.com/download/windows>.
2. Install it, open Tailscale from the Windows tray and sign in. Use your own
   Tailscale account/tailnet. The app does not need a Tailscale API key.
3. Check that this PC shows connected in Tailscale. Leave its Windows service
   installed; copying just tailscale.exe into the receiver folder is insufficient.
4. Funnel requires MagicDNS, HTTPS and permission to use Funnel in your
   tailnet. The first Funnel command normally supplies an approval URL to enable
   the required features. If this is a managed tailnet, its administrator must
   permit it. This is separate from your Spotify/Soloist account.

Official requirements: <https://tailscale.com/docs/features/tailscale-funnel>.
The helper requires the current CLI syntax (Tailscale 1.52 or newer).

## 3. Enable Funnel once

1. Double-click **pc/Setup Funnel.cmd** in the extracted 1.3 folder.
2. Read its console output. If it prints a Tailscale authorization URL, open
   that URL on your PC, sign in if asked, and approve enabling Funnel/HTTPS.
   Setup allows up to ten minutes for this first approval. Do not close the
   setup window while approving. No Spotify, Soloist or pairing key is requested.
   If the CLI finishes after printing the URL, approve it and rerun Setup
   Funnel.cmd; some tailnets do not keep the first command waiting.
3. Setup checks that Tailscale ports **443** and **8443** are free. If another
   Serve/Funnel route uses either port, setup stops and names the conflict.
   Decide how to stop that route yourself before retrying; this helper never
   resets or replaces someone else's Tailscale configuration.
4. Once both routes are configured, setup saves the installed CLI path,
   selects Funnel instead of ngrok, and restarts the background host. It does
   not change audio quality. Future host starts recreate the same two routes.
5. The profile folder opens when the background host reports both routes.
   It contains **remote-host.txt**. **pc/Export Remote Profile.cmd** opens it
   again for the currently selected provider.

If a folder did not open, run **pc/Funnel Status.cmd**. See also **pc/Host
Status.cmd** and `%LOCALAPPDATA%\VitaAudioReceiver\host.log`. Enabling a route
does not prove public DNS or end-to-end connectivity yet; do step 5 below.

Equivalent setup from a PowerShell window opened in `pc`:

```powershell
py -3.14 funnel.py --setup
```

The helper manages these commands internally, without `--bg`:

```text
tailscale funnel --yes --tcp=443 tcp://127.0.0.1:48152
tailscale funnel --yes --tcp=8443 tcp://127.0.0.1:48153
```

Do not run duplicate copies alongside the managed host. Do not substitute
`--tls-terminated-tcp`, HTTPS mode or PROXY protocol: the receiver needs the
app's TLS session to reach the PC unchanged. Only audio/control listeners are
published. Soloist's local API, discovery, desktop and file services are not.

## 4. Copy the public profile using VitaShell USB

1. On the Vita, open VitaShell and connect it to the PC in **USB** mode.
2. Copy the exported **remote-host.txt** to
   **ux0:data/vita-audio-receiver/remote-host.txt**, replacing the old tunnel profile.
3. The mounted USB drive is ux0. On Windows, its destination is
   `data/vita-audio-receiver/remote-host.txt`, without an extra ux0 folder.
4. Leave **vita-pairing.bin** in the same folder. The public .txt profile does
   not replace that private credential.
5. Close VitaShell and reopen Vita Audio Receiver.

PC export location:
`%LOCALAPPDATA%\VitaAudioReceiver\remote\remote-host.txt`.

Example only (use your generated file):

```text
VART1
audio_host=desktop.example-tailnet.ts.net
audio_port=443
control_host=desktop.example-tailnet.ts.net
control_port=8443
```

The public hostname normally survives PC/host restarts. If you rename/remove
the Tailscale device or change tailnets, export/copy the updated profile again.
Use its DNS hostname, not a 100.x Tailscale address or a resolved Funnel IP.
SNI must contain the hostname for Funnel to route the connection.

## 5. Connect and verify from another network

1. Keep the PC host and Tailscale connected at home.
2. Connect the Vita to a different Wi-Fi network or a phone hotspot using
   mobile data. A Vita Tailscale app is not required.
3. In the receiver's waiting screen press **Triangle** until **REMOTE** is
   selected. If it connected locally, press **Circle** to disconnect first.
4. Press **X** to connect if you previously disabled connection attempts.
   **Gear → PC connection** shows the saved hostname and ports. The selected mode is saved.
5. Verify sound, title/artwork, play/pause, browsing and volume. The receiver's
   sidebar shows its actual rate. Both saved preferences initially use 320; tap
   gear → Audio quality to choose 128 or Auto for Remote.
6. Close/reopen the Vita app, test screen-off listening, then test **Stop
   Funnel.cmd**: remote access should stop and Local mode should still work.
   Run **Start Funnel.cmd** to re-enable remote access.

Initial public DNS can take up to ten minutes after Funnel is enabled.
The hostname and pairing must both be correct; a working time counter alone
does not establish that audio is arriving.

## Listener exposure and public naming

Automatic network mode now binds receiver audio/controls to **127.0.0.1** whenever
Funnel/ngrok is enabled, and disables receiver LAN discovery. Use REMOTE on the
Vita, including at home, unless you explicitly run **Use Local and Remote.cmd**.
The public profile and pairing file stay unchanged. Soloist's local API is not
published. **Use Automatic Network Mode.cmd** restores this policy.

The Funnel DNS hostname/SNI is public routing metadata, not a password. Public
certificate names may also appear in Certificate Transparency if certificates
are issued for that name. Do not rely on a secret hostname for security. The
app requires the pairing proof, but public flooding can still disrupt service.
The 0.13 bounded concurrent handshake path mitigates simple serial blocking and
shared-loopback rate starvation; it is not a DDoS-protection service.

## Daily use and controls

| PC helper | Effect |
| --- | --- |
| Setup Funnel.cmd | First approval/check, save installed CLI path, select Funnel |
| Start Funnel.cmd | Select and enable the saved Funnel setup, restart host if needed |
| Stop Funnel.cmd | Disable this app's Funnel routes; keep the local host running |
| Funnel Status.cmd | Show recent route status and exported profile location |
| Export Remote Profile.cmd | Open the active provider's profile folder |
| Stop Host.cmd | Stop Soloist/audio/controls and their managed public routes |
| Start Host.cmd | Start the host and its saved remote provider |

The existing sign-in startup shortcut also starts enabled Funnel routes.
If you did not enable automatic startup previously, **Setup Host.cmd** enables
current-user sign-in startup; leave its key prompt blank to keep the existing
Soloist key. After one-time setup, launch the Vita app to connect; there is no
per-session PC command or token prompt. Fully sleeping/shutting down the PC
still stops listening. Tailscale's own service must remain connected too.

Each route is tied to its foreground CLI watch session. Graceful stop or
termination removes that session's route; no persistent `--bg` route is left.
Windows uses a kill-on-close job for only these spawned CLI processes, never
the global Tailscale service. Unrelated Serve/Funnel routes remain intact.

ngrok remains an optional explicit alternative in [TUNNEL_SETUP.md](TUNNEL_SETUP.md).
Only one managed provider is selected at a time. There is no automatic fallback.

## Quality and limits

Both preferences initially remain at **320 kbps**. Receiver includes **gear → Audio quality**
on Vita: choose Local/Remote and a fixed 96–320 kbps or Auto. See QUALITY.md.
Auto starts at 192 remote and reacts to the Vita's buffer/rebuffer feedback;
fixed 128 is a predictable choice on a poor link. No PC setting change is needed.
These settings affect the bridge link, not Soloist's Spotify source quality.

At **320 kbps CBR**: 40,100 audio-protocol bytes/sec, roughly 148 MB/hour
including typical TLS records, before TCP/IP, artwork and other overhead. Funnel
does not transcode audio. The Vita preference sets the effective Opus rate;
Host Status shows the PC initial/default codec and bitrate.

Funnel has provider-controlled, non-configurable bandwidth limits. Tailscale
does not publish a specific rate guarantee in its Funnel documentation. Keeping
320 kbps is supported by this app, but sustained throughput/stutter must be
tested on your connection; this release cannot guarantee unlimited transfer or
eliminate capture/Wi-Fi interruptions. No Tailscale subscription is purchased.

## If it does not connect

- **CLI not found / not connected:** install the full Tailscale Windows app,
  connect from its tray icon, then rerun Setup Funnel.cmd. No manual executable
  download is bundled with this app.
- **Authorization required:** rerun Setup Funnel.cmd in a visible console and
  follow the printed approval URL. Check MagicDNS, HTTPS and Funnel permissions
  with your tailnet administrator.
- **Port conflict:** another Tailscale Serve/Funnel configuration owns 443 or
  8443. The helper leaves it intact. Stop that specific configuration yourself
  if appropriate, then retry; do not use a global reset as a routine fix.
- **Routes configured, Vita cannot connect:** install the current VPK, recopy the
  exported hostname profile, confirm REMOTE and retain the matching pairing
  file. Wait for initial public DNS. Verify that the Vita's network permits
  outbound TCP 8443 as well as 443; some networks block nonstandard ports.
- **Only controls work:** check that audio is directed to the paired Soloist
  device and that the PC audio helper is running. Use the existing local tone
  and capture diagnostics to distinguish capture faults from remote transport.
- **Stale profile after PC rename/account change:** restart the host, export
  and copy the regenerated profile. Do not manually replace its hostname with
  the relay's IP.

The automated checks cover the exact Vita TLS client behind an SNI-routing
test relay, PSK rejection, real audio/control transport, the official CLI flags,
and helper lifecycle/config conflicts with a local CLI fixture. A live
Tailscale account, Windows audio capture and physical Vita are still needed
for the end-to-end checks above. See [BUILD_VALIDATION.md](BUILD_VALIDATION.md).

Version 1.1 network recovery/batching/buffering details: NETWORK_TUNING.md.
The existing Funnel routes and profile need no changes for this update.
