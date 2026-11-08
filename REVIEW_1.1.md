# Assessment of the supplied 1.0 review

The previous 0.13 security assessment remains a historical record linked from
CHANGELOG.md. The current model is SECURITY.md. This pass focuses on audio and
queue behavior; it is not a new independent security audit.

| Suggestion | Assessment and action |
| --- | --- |
| Stall catch-up | Good. The old sender could not rebuild much cushion while playing. “Never refills” was too absolute: stopping to rebuffer did refill it. Added bounded 4× delivery from captured backlog using actual receiver receipt/buffer feedback. |
| SO_SNDBUF | Correct for Windows dynamic send buffering. Removed the explicit cap; receiver-driven pacing prevents simply replacing it with a much larger uncontrolled backlog. |
| Larger receiver buffer | Good tradeoff for Remote. Capacity is 2.048 s, Remote prebuffer 1.024 s/target around 1 s; Local remains 256 ms. |
| Flush after changes | Good, with a control-channel hold/release and fresh audio stream so kernel/tunnel buffers are discarded too. Natural track-end transitions are retained to avoid cutting off song tails. |
| Three frames per write | Good. Uses 60 ms writes with the original frames/quality. It reduces writes/records, not necessarily the physical packet count by three. |
| Queue 32/10 flicker | Correct. Uses ID-based prefix merging and a bounded short-snapshot debounce. There are no documented request IDs to identify replies perfectly. |
| Agile callback | The original helper already aggregated a free-threaded marshaler, as Microsoft's documentation describes. It was not simply a non-agile callback. Explicit IID_IAgileObject support is added as a small compatibility improvement. |
| Old doc headings | Correct. Current guides are marked 1.1; old security findings remain in their historical file. |

The separately reported Up Next bug is fixed by using serial, confirmed skips
within the existing queue. Selecting a favorite intentionally remains play(uri),
which can start that favorite's context. Artist extraction already joins all
creator names in 1.0; that item did not need a new implementation.

One additional useful item is included: Soloist's confirmed **exit code 10** now
produces an expired-build message on the Vita. A warning inferred from installation
date is not added: installation date is not build date, and the documented version
output has no guaranteed machine-readable expiry field.

Favorites adding/editing controls are intentionally deferred as requested. The
existing PC workflow is documented in FAVORITES.md. Save current/highlighted song
on the Vita is feasible without an extra login for this app-local shortcut list.

Diagnostics/history graphs, a separate 30-second test UI, sleep/resume preferences
and queue-add shortcuts remain future UI work. “Remaining hotspot/Funnel data”
cannot be known from this app's payload byte counter alone; quotas, other traffic,
cycle dates and provider/account information would be needed. We do not display
a misleading remaining allowance. A hard-coded initial volume of 100 is not
introduced: it would override the user's source-volume preference. The dedicated
cable setup and Vita volume controls remain as documented.

## Primary references checked

- Soloist commands, queue events and asynchronous result semantics:
  https://developer.spotify.com/documentation/soloist/reference/websocket-api
- Soloist command-line options and expired-build exit code:
  https://developer.spotify.com/documentation/soloist/reference/command-line
- Windows dynamic send buffering:
  https://learn.microsoft.com/en-us/windows/win32/winsock/sio-ideal-send-backlog-query
- Audio activation callback/FTM guidance:
  https://learn.microsoft.com/en-us/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-activateaudiointerfaceasync
