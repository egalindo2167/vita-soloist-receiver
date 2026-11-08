# Spotify Soloist setup — 1.3.1

Use [HOST_SETUP.md](../HOST_SETUP.md) for the persistent Windows host, saved Soloist
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

For optional remote access, complete Local setup first, then follow
[Tailscale Funnel](../FUNNEL_SETUP.md). [Ngrok](advanced/NGROK_SETUP.md) is an
advanced alternative. Provider access does not change the Soloist or Vita keys.
