Vita Audio Host 1.3

Run Setup Host.cmd once, or Upgrade Host.cmd to update an existing installation.
Keep the native folder with the PC files. Setup installs the exact hash-locked
Windows 11 x64 Python 3.14 dependencies and copies the Opus DLL and process-capture EXE.
Install VB-CABLE and restart Windows before the first 1.0 upgrade. The audio wizard
chooses CABLE Input and verifies that only Soloist is routed to it in Volume mixer.
Leave normal Windows audio on your preferred speakers/headphones.

Setup Audio.cmd changes the dedicated cable; Audio Status.cmd checks the live route.
The managed stream includes only the owned Soloist process tree, never all PC sounds.
A missing cable or wrong Soloist route stops capture; there is no speaker fallback.
Leave cable/Windows Soloist mixer volume at 100%; use the Vita for normal loudness.
Full one-time instructions: AUDIO_SETUP.md in the ZIP root.

The background host waits for the paired Vita. Optional sign-in startup is
retained. Soloist login, key, favorites and transport pairing are preserved.
The Soloist key is protected by DPAPI at rest but its required upstream CLI
argument remains visible to processes/auditing with sufficient Windows access.

Pair Vita.cmd generates a per-device private export. Copy it by trusted USB to
ux0:data/vita-audio-receiver/vita-pairing.bin. Its matching PC export is deleted
on first authenticated use. Manage Vitas.cmd revokes a lost device.

Setup Funnel.cmd configures optional remote access. Keep the existing Remote
profile after upgrading. With a tunnel enabled, Automatic network mode binds
only to loopback. Use Local and Remote.cmd explicitly enables LAN too.

Open gear > Audio quality on Vita to set separate Local/Remote Opus preferences from 96 to
320 kbps, or opt into Auto. Both default to 320. Choices apply during playback;
Use Opus 320.cmd changes the PC codec/default, not saved Vita preferences.

Full instructions: HOST_SETUP.md, FUNNEL_SETUP.md and QUALITY.md in the ZIP root.
New Vita controls/settings: UI_GUIDE.md. SELECT opens Settings; L/R skips tracks
in Queue/Favorites; Left/Right switches those tabs; Triangle cycles music pages.
Current security: SECURITY.md. Review: REVIEW_1.1.md. Build inputs: SUPPLY_CHAIN.md.

1.3 adds upcoming-song search; update BOTH host and VPK for this revision.
Existing 1.0 cable, pairing, login, quality preferences and Funnel profile stay.
Up Next selection preserves the queue/context. Favorites commands are unchanged;
see FAVORITES.md for adding/listing/removing and opening the Vita tab.

In Queue, Square or the search bar opens a touch/controller keyboard. R searches;
results are paged with their original queue positions. Spotify documents up to
80 upcoming songs, not the whole playlist. Queue Availability.cmd checks the
current running build with a read-only request. See SEARCH.md in the ZIP root.
