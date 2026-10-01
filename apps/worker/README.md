# smr-worker

The taskiq worker and its scheduler, one image:

- `taskiq worker smr.worker.broker:broker`
- `taskiq scheduler smr.worker.broker:scheduler`

Tasks: deliver the outbox (every 10 s), queue deadline reminders (every 5 min),
back up (03:00 Moscow), purge old notices, exports and expired groups (04:00).
