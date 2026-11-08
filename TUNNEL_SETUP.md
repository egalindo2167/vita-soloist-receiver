# Remote access with ngrok — receiver 1.3

For the preferred Tailscale Funnel setup at unchanged Opus 320 kbps, see
[FUNNEL_SETUP.md](FUNNEL_SETUP.md). This document keeps the optional ngrok path.
Selecting either provider disables the other managed helper.

This option needs your Windows PC and the Vita, not a VPN gateway, Raspberry Pi
or travel router. One ngrok agent creates two raw TCP endpoints for audio and
Spotify controls. Titles, controls, artwork and audio stay inside the existing
paired TLS 1.3 sessions between Vita and PC. The provider forwards encrypted
bytes; it does not receive the pairing key. This is an optional feature.

## Before starting

You need Python 3.14, your existing working Soloist host, a paired receiver, and
an ngrok account with access to TCP endpoints. ngrok currently requires a valid
payment method/account verification for TCP, including free-plan access. Its
published free plan allows three online endpoints and 1 GB/month of data transfer
out. This app uses two endpoints. At Opus 320 kbps, about 148 MB/hour of audio
including TLS framing is expected before TCP/IP, cover art and other overhead;
1 GB is only a few hours of testing/listening, not unlimited streaming. Check
your own plan and dashboard before use. No plan is purchased by our scripts. These are **TCP** endpoints carrying our
app TLS internally; you do not need to select ngrok's separate raw TLS endpoint type.

Official account: https://dashboard.ngrok.com/signup
Windows download: https://ngrok.com/downloads/windows
Your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
Limits: https://ngrok.com/docs/pricing-limits/free-plan-limits

## 1. Update the PC and Vita applications

1. Close the Vita app and extract this ZIP on your PC.
2. Run **pc/Upgrade Host.cmd**. It updates/restarts the installed host and keeps
   your Soloist key/account, favorites, transport pairing and sign-in startup.
3. Install **dist/vita-audio-receiver.vpk** over the existing Vita app using
   VitaShell. Do not delete the old app to upgrade it.
4. If you already paired receiver 0.10, keep its `vita-pairing.bin` and skip to
   step 2 below. If not, run **pc/Pair Vita.cmd** and copy its private generated
   file with VitaShell USB into **ux0:data/vita-audio-receiver/**. See HOST_SETUP.md.

## 2. Obtain the official ngrok Windows agent

1. Create/sign into your ngrok account. Complete the TCP-access verification
   required by your account; this is done on ngrok's website, not in our app.
2. Download the current Windows x64 ngrok agent from its official download page.
3. Extract **ngrok.exe** into the new ZIP's **pc** folder, beside **Setup Tunnel.cmd**.
   An ngrok installation already on PATH is supported too.
4. Open the dashboard's **Your Authtoken** page. Copy the authtoken. This is
   different from an ngrok API key, your Soloist key and the Vita pairing key.

Do not paste your token into ChatGPT, a shared screenshot, the public endpoint
profile or a source file. The setup prompt below keeps it hidden.

## 3. Start the tunnels on your computer

1. Double-click **pc/Setup Tunnel.cmd**.
2. Paste your **ngrok authtoken** into its hidden prompt and press Enter.
3. Setup validates the ngrok configuration, stores the token with Windows DPAPI,
   copies a portable agent into the installed app, and enables the optional
   tunnel helper in the background host. It then restarts the host.
4. Wait for two available TCP addresses, one labeled Audio and one Controls.
   Setup waits up to about 20 seconds for the first status update. If the provider
   is still connecting, use **Tunnel Status.cmd** and check host.log.
5. On success a folder opens containing **remote-host.txt**. You can reopen it
   later using **pc/Export Remote Profile.cmd**.

The scripts use ngrok's version-3 configuration and current loopback
`/api/endpoints` API. Both upstreams are fixed to 127.0.0.1:48152/48153. Soloist's
local WebSocket, UDP discovery, desktop access and other PC services are not
published. No router port forwarding, UPnP or Public firewall exception is needed.

If you prefer PowerShell, open it in pc and run:

```powershell
py -3.14 tunnel.py --setup
```

This does the same setup. Do not run a second manual agent for these endpoints
while the host already manages one.

## 4. Copy the public endpoint profile to the Vita

1. Open VitaShell on the Vita and connect using **USB**.
2. Copy **remote-host.txt** from the folder opened by setup into:
   **ux0:data/vita-audio-receiver/remote-host.txt**.
3. The mounted USB drive is ux0. On the PC, the destination folder is its
   `data/vita-audio-receiver/` directory, not an extra ux0 folder inside the drive.
4. Leave the existing **vita-pairing.bin** there too. The .txt file contains
   public addresses/ports only; it does not replace the private pairing file.
5. Close VitaShell and reopen Vita Audio Receiver.

The exported PC profile is stored at:
`%LOCALAPPDATA%\VitaAudioReceiver\remote\remote-host.txt`.

## 5. Connect using Remote mode

1. On the Vita waiting screen, press **Triangle** to switch from Local to Remote.
   If already connected locally, press Circle to disconnect first.
2. The app resolves the two hostnames and connects using the saved ports. It
   authenticates with your existing pairing key before any audio/commands.
3. Open **gear → PC connection** in Remote mode to inspect both endpoints.
   X retries/connects; Circle returns from details; Triangle returns to Local.
4. During playback the sidebar identifies **REMOTE**, **TLS 1.3** and the codec.
5. Remote/Local selection is remembered. After setup, launch the Vita app as
   usual while the PC and its tunnels remain running.

First try Remote mode while still at home. Then switch the Vita to a phone
hotspot using mobile data or another Wi-Fi network, leaving the PC on home
internet. No VPN app or gateway device is required on that other network.
Some guest networks block ngrok or its assigned TCP ports; use an allowed
network if that happens. Automatic LAN discovery is disabled in Remote mode.

## Normal PC operation

| Script | Action |
| --- | --- |
| Setup Tunnel.cmd | First setup or replace the provider token/agent. Blank token retains an existing one. |
| Start Tunnel.cmd | Enable/restart background tunnels using the saved token; no repeated token prompt. |
| Stop Tunnel.cmd | Disable tunnels and restart the host in local-only mode. Pairing/settings are retained. |
| Tunnel Status.cmd | Show recent agent status and available addresses. |
| Export Remote Profile.cmd | Open the exported public profile folder. |
| Host Status.cmd | Show the host's codec, local addresses and whether tunnels are enabled. |

The existing host sign-in shortcut starts the enabled tunnel helper too. Once
setup finishes you can close the setup window; the background host owns ngrok.
The PC must remain awake, signed in and online. Stop Host stops its tunnel
helper too. On Windows the manager puts its ngrok child in a kill-on-close job
so terminating that manager also terminates the agent it owns. Other ngrok
processes are not stopped or reconfigured.

Close/disconnect the Vita when finished: the app's CBR audio stream continues
using bandwidth while connected, even if Spotify is paused or the source is
silent. Screen-off listening continues to stream normally.

## Address changes and stable addresses

Unreserved TCP addresses **can change when the agent restarts**, including
restarts after sign-in or failures. The helper updates the exported file when
it sees new addresses and records that in host.log. The Vita cannot fetch new
addresses after the old ones stop working: copy the updated remote-host.txt
by USB and reopen the app. There is no remote profile editor in this version.
Check addresses before leaving home; keeping the PC/agent running avoids
unnecessary restarts. Exporting the file does not itself update the Vita.

If you independently obtain **two reserved TCP addresses** on a suitable ngrok
plan, you can configure them explicitly (replace these examples with your own):

```powershell
py -3.14 tunnel.py --setup --audio-url tcp://YOUR_AUDIO_HOST:YOUR_AUDIO_PORT --control-url tcp://YOUR_CONTROL_HOST:YOUR_CONTROL_PORT
```

The script does not reserve or purchase addresses. Both must belong to your
account and be different. Use `--audio-url tcp:// --control-url tcp://` with
--setup to return to unreserved addresses. Fixed addresses are optional, and
provider plan/pricing restrictions apply. Our helper preserves your choice
on later setup/upgrade. Existing unrelated ngrok configuration is not overwritten.

## Troubleshooting

- **No ngrok.exe:** download/extract the official Windows agent beside Setup
  Tunnel.cmd, or enter its full path when prompted. Use the current v3 release.
- **No TCP access / authentication error:** check the ngrok account's verification,
  authtoken and plan limits. Run Setup Tunnel again to replace the token.
- **Account/session/endpoint limit:** stop unrelated agents yourself or use a plan
  allowing the required resources. Our helper uses one agent/two endpoints and
  never kills someone else's agent to free a slot.
- **Waiting for both endpoints:** check the rotated host.log for ngrok errors.
  The host retries failed tunnel helpers with backoff. A stale saved profile
  does not establish that either tunnel is currently running.
- **Vita says Remote profile needed:** copy the exact generated file to the
  correct ux0 directory and reopen. Invalid files are rejected; there is no
  automatic plaintext or Local-mode fallback.
- **DNS failed:** verify Vita Wi-Fi/internet and the hostnames in Settings → PC connection.
- **Tunnel unavailable:** check PC host/tunnel status, changed addresses, network
  restrictions, and that the same Vita ID remains paired. Both audio and controls
  must be reachable. Manage Vitas revocation still blocks remote connections.
- **Hitches:** inspect the separate capture-discontinuity, capture-drop and Vita
  rebuffer counters. A relay can add delay/jitter; compression does not repair
  lost capture samples. Try a lower Opus bitrate through the existing host controls.

Log: `%LOCALAPPDATA%\VitaAudioReceiver\host.log`.
Protected provider settings: `%LOCALAPPDATA%\VitaAudioReceiver\tunnel.json`.
Do not share that settings file or the private pairing file in reports.

The release is tested with local opaque TCP forwarding, native receiver TLS and
profile code, and the official agent's config checker. Account-specific live
ngrok forwarding, Windows capture/DPAPI/process jobs and physical Vita DNS/Wi-Fi
still require your device/account test. No ngrok credentials, executable, VPN
client or public hosted relay are bundled in this ZIP.

Official references:
- https://ngrok.com/docs/gateway/agent/config/v3
- https://ngrok.com/docs/gateway/agent/api
- https://ngrok.com/docs/gateway/endpoints/tcp
- https://ngrok.com/docs/gateway/domains/tcp-addresses
- https://ngrok.com/docs/pricing-limits/free-plan-limits
