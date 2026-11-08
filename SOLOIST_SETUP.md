# Spotify Soloist setup — 1.3

Use [HOST_SETUP.md](HOST_SETUP.md) for the persistent Windows host, saved Soloist
key, one-time USB Vita pairing and encrypted connections. `start_soloist.py`
and network `send_audio.py` manual mode are retired; no plaintext fallback exists.
Capture-only diagnostics remain available. Soloist runs on the PC; the Vita
receives the PC audio and controls its local API through the authenticated host.

Official downloads (Windows x86_64):
https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates

Personal Soloist key: https://developer.spotify.com/dashboard/soloist

Soloist WebSocket reference:
https://developer.spotify.com/documentation/soloist/reference/websocket-api

The Vita pairing file is separate from the Soloist key and Spotify account login.
Never put a Soloist API key in the Vita pairing file or distribute either secret.

Optional remote tunnel setup: [TUNNEL_SETUP.md](TUNNEL_SETUP.md). This uses a
separate provider token; it does not change the Soloist or Vita pairing keys.
