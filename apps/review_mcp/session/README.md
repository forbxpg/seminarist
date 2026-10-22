# Grading session

Create the folder outside the repository. It holds no student data. The pages
the agent sees stay in the bot's container.

```sh
uv run smr-review-session ~/seminarist-review
```

The command writes `CLAUDE.md`, `.claude/settings.json` and `.mcp.json`.
The compose file path in `.mcp.json` is already the absolute path of this
repo's `compose.yaml`. A folder inside the repository is refused, so a
student's pages cannot land in the checkout.

The bot container must already be running (`docker compose up -d bot`).
Start Claude Code in the created folder and say
«проверь все непроверенные работы».
In Cursor, add the same server under MCP and turn on Privacy Mode.
In Claude, turn off training on chats.

The server key is `seminarist-review`. Permissions allow
`mcp__seminarist-review__*` and deny the shell, edits and the web.
