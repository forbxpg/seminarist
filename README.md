# seminarist

A Telegram bot I use to run my university seminars: groups and rosters, attendance,
board calls with a fair randomizer, homework intake and grading, a 50-point gradebook
with a rating, seminar PDFs and reminders.

It runs on my own machine in Docker: student data never leaves it, and none of it is
in this repository.

## Run

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy its token.
2. Find your Telegram user id, e.g. with [@userinfobot](https://t.me/userinfobot).
3. `cp .env.example .env` and fill in `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_IDS`
   (comma-separated ids of the teachers), `POSTGRES_PASSWORD` (the same one inside
   `DATABASE_URL`) and `REDIS_PASSWORD`.
4. `docker compose up -d --build`. The migrator applies the schema and exits; then the
   bot, the worker and the scheduler start. Nothing listens on a host port.

Then in Telegram: `/admin` → create a group → paste the roster → send the students the
group's invite link. Each student picks their name; you approve the request.

The machine has to be awake for the bot to answer; notices queued while it slept go
out when it wakes.

## Data

Everything lives in `./data` (homework files, seminar PDFs, exports, backups) and in
the `pgdata` volume. A backup runs daily at 03:00 and on "Бэкап сейчас" in `/admin`:
`data/backups/backup-<time>/` holds `database.dump` (for `pg_restore`) and
`files.tar.gz`; the newest 14 are kept. Point `STORAGE_BACKUP_DIR` at a synced folder
to keep a copy off this machine.

Restore the database:

```bash
docker compose exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < data/backups/<backup>/database.dump
```

Students can see and delete what the bot keeps about them ("Мои данные",
"Удалить мои данные"). Logs carry ids, never names or message texts.

## БДЗ и проверка агентом

A teacher publishes a big homework (БДЗ) from the group menu: a statement PDF, a
solutions PDF the students never receive, a point scheme (`1:3, 2:5`) and a deadline.
It has to sit on a proportional work type. A student sends one PDF; a later PDF
replaces it and voids the current verdict, including after the deadline and after a
teacher's final grade. The journal keeps the last published total until the next
published or final verdict.

Grading runs in a session outside this repository. Copy
`apps/review_mcp/session/` (see its README), point it at the running bot and say
«проверь все непроверенные работы». The agent reads page images through
`smr-review-mcp` and never sees a name. A clean verdict is published to the student;
an unreadable page or a low-confidence grade waits for the teacher. The student can
appeal a published grade once, within seven days. Accept the current privacy notice
before sending: it says an assistant checks the pages.

## Develop

```bash
uv sync --all-packages
uv run pre-commit install
uv run ruff check . && uv run ruff format --check . && uv run basedpyright && uv run lint-imports
uv run pytest                    # unit tests
uv run pytest -m integration     # needs Docker: PostgreSQL via testcontainers
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

## Layout

| Path | What |
|---|---|
| `packages/core` | settings, database kit, audit log, file storage, clock, access, backup |
| `packages/roster` | groups, students, binding a Telegram account to a name |
| `packages/gradebook` | work types, the points ledger, totals, rank, board priority |
| `packages/sessions` | seminars, attendance, board calls |
| `packages/homework` | assignments, submissions with files, grading, export |
| `packages/notifications` | the outbox of notices, reminder preferences |
| `packages/materials` | seminar cards with files, publishing |
| `packages/review` | agent verdicts, the teacher's queue, appeals |
| `packages/bdz` | big homework: a PDF, a point scheme, the review source |
| `apps/migrator` | Alembic over every package's revisions |
| `apps/bot` | the Telegram interface: students' and teachers' dialogs |
| `apps/worker` | taskiq worker and scheduler: delivery, reminders, backup, purge |
| `apps/review_mcp` | the MCP server the grading agent uses |

Each package keeps its own PostgreSQL schema and is split into `domain`,
`application` (use cases, ports, contracts) and `infrastructure`; import-linter keeps
the boundaries (`pyproject.toml`).

## License

MIT
