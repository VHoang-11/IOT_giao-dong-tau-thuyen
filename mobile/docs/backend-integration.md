# Backend TV3 Integration – Pending Contracts

The app currently uses `MockDataService` only. It has no network credentials or API keys.

When Backend TV3 is ready, agree on:
1. Authentication/token/session response and authorization for Operator / Supervisor / Admin.
2. REST API for alarms (ACK/mute/review), commands and voyages.
3. WebSocket payload (`device_id`, `seq`, `boot_id`, simulation time versus wall time, `roll_deg`, `pitch_deg`, RF and baseline labels, MAI, sensor state).
4. MQTT-to-backend command lifecycle and `cmd_id`, TTL, authorization, acknowledgment.
5. Report PDF/CSV streaming and historical replay time-range semantics.
6. The exact alarm lifecycle: RAISED, ACKED, CLEARED; ACK must not clear events.

`src/data/service.ts` provides the frontend-only abstraction. `LiveDataService` intentionally fails with `NOT_CONFIGURED` until a real contract is received. In the production implementation, asynchronous auth, WebSocket freshness, reconnect handling and role checks MUST be implemented on the backend side; do not silently fall back to mock.
