# Grading session

Copy this folder outside the repository, for example to `~/seminarist-review/`.
It holds no student data. The pages the agent sees stay in the bot's container.

1. Rename `mcp.json.example` to `.mcp.json`.
2. Replace `/ABS/PATH/compose.yaml` with the absolute path of this repo's
   `compose.yaml`. The bot container must already be running
   (`docker compose up -d bot`).
3. Start Claude Code in the copied folder and say
   «проверь все непроверенные работы».
4. In Cursor, add the same server under MCP and turn on Privacy Mode.
   In Claude, turn off training on chats.

The server key is `seminarist-review`. Permissions allow
`mcp__seminarist-review__*` and deny the shell, edits and the web.
