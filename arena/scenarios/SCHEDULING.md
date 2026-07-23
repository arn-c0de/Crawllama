# External scheduling for longitudinal arena runs (plan §16)

Scheduling is **external** — the arena does not own a scheduler. Re-run a
`domain_history` scenario on a cadence and store an immutable snapshot per date;
`arena` then builds the timeline and attributes drift (behaviour vs acquisition).

## cron

```cron
# Analyse one domain every day at 03:00 and snapshot the result.
0 3 * * *  cd /path/to/crawllama && \
  .venv/bin/python -m arena run --suite live --profile mock >> logs/arena-history.log 2>&1
```

## systemd timer

```ini
# /etc/systemd/system/arena-history.timer
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/arena-history.service
[Service]
Type=oneshot
WorkingDirectory=/path/to/crawllama
ExecStart=/path/to/crawllama/.venv/bin/python -m arena run --suite live --profile mock
```

## GitHub Actions (deterministic gate only)

```yaml
name: arena-gate
on: [pull_request]
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uv sync --extra testing
      - run: uv run python -m arena run --suite smoke --profile mock   # exits non-zero on failure
      - run: uv run python -m arena coverage --gate                    # exits non-zero on coverage gaps
```

Only the deterministic `smoke` suite and `coverage` gate belong in CI. Live and
history runs are network-bound and must run on a schedule/host you control.
