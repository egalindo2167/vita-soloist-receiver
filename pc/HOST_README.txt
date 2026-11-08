Vita Audio Receiver — Windows host

FIRST SETUP
Use Windows 11 x64 and standard x64 Python 3.14 (not 3.14t/free-threaded).
Extract the complete application ZIP; keep native/ with these scripts.
Install VB-CABLE and restart Windows. Keep normal speakers/headphones as default.
Obtain your own official Soloist download/key; extract its files into soloist/.
Run Setup Host.cmd, then finish its dedicated-cable/Volume mixer wizard.
Allow the host's Python on Private networks only for trusted home-LAN use.
See HOST_SETUP.md and AUDIO_SETUP.md in the ZIP root for every step.
Windows security/launcher blocks: docs/WINDOWS_TROUBLESHOOTING.md.

VITA PAIRING
Install the VPK from dist/. Open it once to create its data folder, then close.
Run Pair Vita.cmd and copy the generated private vita-pairing.bin by USB to
ux0:data/vita-audio-receiver/. Reopen the Vita app. Select PS Vita (PC bridge)
in Spotify's device picker. Each user supplies their own key/account/pairing.
Never share a pairing file or an installed host/Spotify account data folder.

DAILY USE
The signed-in Windows host waits for the Vita. Open the Vita app to connect.
Setup Audio.cmd changes/checks routing; Audio Status.cmd checks the live route.
Only the owned Soloist process tree is captured. A missing cable/wrong route
stops capture; there is no speaker fallback. Leave the cable and Windows Soloist
mixer volume at 100%; use Vita/Spotify controls for normal loudness.
Quality, screen timeout and connection settings are under the Vita gear icon.

OPTIONAL REMOTE ACCESS
First get Local working. Setup Funnel.cmd enables Tailscale Funnel on the PC;
follow FUNNEL_SETUP.md. No Tailscale app is needed on Vita. Automatic mode binds
only to loopback when a tunnel is enabled. Use Local and Remote.cmd explicitly
if you also want LAN access. Ngrok is an advanced alternative, not first setup.

UPDATING
Close the Vita app. From the new release, run Upgrade Host.cmd, then install
its VPK over the current Vita title. Keep data. Existing codec/bitrate, key,
login, route, pairing, favorites, startup and Funnel profile are preserved.
Use Pair Vita only for a new/replacement device or lost/revoked credential.

CONTROLS AND HELP
UI_GUIDE.md: controls/settings. SEARCH.md: upcoming-song search and its scope.
FAVORITES.md: add/list/remove song or playlist shortcuts on the PC.
SUPPORT.md: troubleshooting and redacted bug reports. SECURITY.md: private
vulnerability reporting. Sign-in startup is optional. Keep the PC awake/signed in.
