# seminarist

A Telegram bot I use to run my university seminars: groups and rosters, attendance,
board calls with a fair randomizer, homework intake and grading, a 50-point gradebook
with a rating, seminar PDFs and reminders.

It runs on my own machine in Docker: student data never leaves it, and none of it is
in this repository.

## Run

```bash
cp .env.example .env   # fill in the token, the admin ids and the passwords
docker compose up -d --build
```

## Develop

```bash
uv sync --all-packages
uv run pre-commit install
uv run ruff check . && uv run ruff format --check . && uv run basedpyright && uv run lint-imports
uv run pytest                    # unit tests
uv run pytest -m integration     # needs Docker: PostgreSQL via testcontainers
```

## Layout

| Path | What |
|---|---|
| `packages/core` | settings, database kit, audit log, file storage, clock |
| `apps/migrator` | Alembic over every package's revisions |
