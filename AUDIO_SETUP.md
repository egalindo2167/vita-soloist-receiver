# Dedicated Soloist audio — version 1.3.1

The managed host uses a virtual cable to keep Soloist away from physical speakers,
plus Windows **process loopback** to capture only the host-owned Soloist process
and its child processes. Other applications are excluded even if they are
accidentally sent to the same cable. The Windows default output is never selected
as a capture fallback or changed by this app.

Requires **Windows 11 x64**, standard Python 3.14, and your
own official Soloist installation/key. Native Windows ARM Python is unsupported;
x64 emulation on Windows ARM is untested.
No driver, Soloist executable, account key or remote service account is bundled.

## First audio setup

1. Close the Vita app. Download VB-CABLE from the official
   **https://vb-audio.com/Cable/** page. Extract the driver package, run its
   appropriate Windows installer as administrator, and restart Windows as the
   vendor instructs. The receiver's own scripts run as your normal Windows user.
2. In Windows **Settings → System → Sound**, keep your preferred **headphones
   or speakers** as the default output. If installing the cable changed that
   default, put it back. The cable should not be the system-wide default.
3. Extract the complete application ZIP. Keep **pc/native/** with the scripts.
   Run **pc/Setup Host.cmd** and follow its prompts. An existing installation
   uses **Upgrade Host.cmd**, keeping its saved settings.
4. The audio wizard runs during first setup. You can
   reopen it with **pc/Setup Audio.cmd**. Choose the numbered virtual **playback**
   device, normally **CABLE Input (VB-Audio Virtual Cable)**. The wizard only
   offers cable candidates, saves the exact endpoint ID, and sets that cable's
   master volume to 100% and unmuted. It does not change physical-output volume.
5. The wizard opens Windows Volume mixer. On a phone or PC, open Spotify and
   select your Soloist device, normally **PS Vita (PC bridge)**. Start/resume a
   song so Windows creates Soloist's audio session. First-time Spotify account
   pairing happens through that device picker, independently of Vita USB pairing.
6. In **Settings → System → Sound → Volume mixer → Apps**, find **Soloist**
   (often `soloist.exe`). Expand its row if necessary, set **Output device** to
   the exact **CABLE Input** chosen in the wizard, and set its Windows app volume
   to **100%, unmuted**. Leave other apps at **Default**, or their own preferred
   physical output. Do this for **Soloist**, not the normal Spotify desktop app
   or the Python host. If Soloist is absent, resume its song in Spotify and
   reopen the Volume mixer. The guard may pause it once while setup is incomplete;
   resume from Spotify when needed to create the session.
7. Keep **CABLE Output → Listen to this device** disabled in the classic Windows
   recording-device properties. No program needs to monitor CABLE Output on the
   PC. Despite their names, **CABLE Input is the playback device**; CABLE Output
   is the recording side. The receiver captures the process directly and does
   not mix everything on the recording side.
8. Return to the wizard and press **Enter**. It checks the owned Soloist process,
   its start time/executable, cable availability, and live audio-session routing.
   A missing session or wrong output does not count as a successful check. Fix
   the route and retry, or Q leaves streaming blocked for later setup.
9. Install **dist/vita-audio-receiver.vpk** in VitaShell, then open the app once
   to create `ux0:data/vita-audio-receiver/`. Complete the USB pairing steps in
   [HOST_SETUP.md](HOST_SETUP.md), then reopen the app and connect in **Local**
   mode for the first test. When updating, install over the existing app and
   keep its saved data and pairing.

Windows normally retains per-app routing. If a later Soloist update changes
the executable path, Windows resets its route, or the cable is reinstalled,
run Setup Audio again. We deliberately use Windows' visible per-app setting;
Soloist's documented device flag is PipeWire-only, not a Windows output selector.

## Normal use

Keep the PC awake and signed in. The background host still starts at sign-in,
waits for the paired Vita, starts capture on an authenticated audio connection,
and releases the capture helper on disconnect. No terminal or repeated output
selection is needed for each session once Windows retains the route.

Use the Vita's Spotify slider for Soloist volume and the Vita's system buttons
for headphone/speaker loudness. The host gain remains 0.5 unless you change it.
Leave the virtual cable and Soloist's Windows mixer row at 100% and unmuted.
Your normal physical-output master volume may be low or muted; it is not the
capture source. Unplugging a physical dongle should not change the saved source.
If Soloist itself is paused, muted, or set to zero volume, its capture is silent.

Opus and the separate Local/Remote Settings → Audio quality selections, including Auto, are
unchanged. There is no forced reduction to 128 kbps. The process helper supplies
48 kHz stereo signed 16-bit PCM; the existing Opus encoder and receiver buffers
handle the link. The native backend uses Windows event-driven audio buffers,
rather than SoundCard's old `capture_blocksize` setting.

## Check the separation

1. Run **pc/Audio Status.cmd** while Soloist has an audio session. It prints the
   exact dedicated endpoint, process-only mode, and live route result. **Host
   Status.cmd** shows the saved capture choice and any last reported error.
2. With a song playing on the Vita, lower or mute the **physical** headphones/
   speakers in Windows. The Vita should continue. Do not mute the virtual cable
   or Soloist's own Windows app row during this check.
3. Play a browser video or Windows test sound through your normal default output.
   It should be audible there and absent from the Vita. Soloist should be absent
   from your physical speakers. There is no system-wide monitor path to enable.
4. Close and reopen the Vita app, then restart the host once to confirm Windows
   retained Soloist's per-app route. Test your usual dongle unplug/replug too.

These are the physical Windows/Vita acceptance checks; they cannot be performed
by the Linux build/test environment used to produce this release.

## When setup changes or fails

The helper periodically checks cable state and Soloist sessions (about every
250 ms) on a separate worker, outside the audio capture thread. A route worker
that stops responding for three seconds also ends capture. A missing cable,
stopped/replaced process, unsupported OS, or active
Soloist session on another endpoint ends capture. Unrelated applications are
excluded by the OS process filter, not just by the routing check. A missing
configured device never causes a fallback to the current default speakers.
Until the selected route exists, unverified live sessions supply silence rather
than audio from another endpoint.

The Vita shows **AUDIO SETUP NEEDED** with a specific reason, keeps OLED dim/
screen-off behavior, and retries automatically. Setup and live route errors
block Vita play/activate commands; the control bridge asks Soloist to pause
when it sees a new capture error. Normal playback is re-armed after a successful
retry or route check. An external Spotify app can still control Soloist, and
Windows may render a brief sound before a changed route is detected; this app
cannot guarantee that Windows will never emit a first sample on a wrong output.

| Message | What to do on the PC |
| --- | --- |
| Choose a virtual cable / routing not verified | Run Setup Audio and complete its live check. |
| Virtual cable device is missing | Enable/install the saved cable; rerun Setup Audio if it was reinstalled with a new ID. |
| Soloist is not running | Check Host Status/log and the official Soloist build/key; allow the supervisor to restart it. |
| Soloist output mismatch | Set only Soloist's Volume mixer output back to the selected cable; rerun Audio Status or let the Vita retry. |
| Process capture needs Windows 11 | Use supported Windows 11 x64; this backend never falls back to system capture. |
| Could not start capture | Run Audio Status and inspect `host.log` for the Windows error code; keep the full `pc/native` folder installed. |

The native helper's hash is checked before execution. A missing/modified helper
blocks capture. Re-extract the complete release and rerun Upgrade Host rather
than substituting an unrelated EXE. Logs are in
`%LOCALAPPDATA%\VitaAudioReceiver\host.log`; do not share host.json, API keys,
pairing credentials or Soloist's private data directory.

The old `send_audio.py --capture-only` command is a separate **whole-endpoint
diagnostic**, not the managed process-only stream. It now requires an explicit,
exact `--device` ID/name from `--list-devices` and will not choose a default or
fuzzy match. Its WAV may contain all apps on that chosen endpoint. For normal
use, use the managed host and Audio Status instead.

## References

- VB-CABLE installation and signal direction: https://vb-audio.com/Cable/
- Microsoft process/child inclusion, endpoint independence, silence and minimum build:
  https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/
- Spotify Soloist's documented command-line audio options:
  https://developer.spotify.com/documentation/soloist/reference/command-line

Network/queue details: [network tuning](docs/NETWORK_TUNING.md).
A confirmed Soloist expired-build exit code now displays an update message on Vita;
install a newer official Soloist build and run Upgrade Host.cmd.
