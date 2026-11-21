# Safety Car: Hack for Impact kit

**There's no code in this kit, on purpose.** Your Claude Code writes it all from 11:35, following CLAUDE.md.

| File | What it's for | Who reads it |
|---|---|---|
| CLAUDE.md | The full spec. Claude Code reads it automatically. | Every Claude Code session |
| PLAN.md | The battle plan: judging map, demo script, Q&A, timeline, SolvaPay call, next test, risks | The whole team |
| PROMPTS.md | Prompts to paste into Claude Code, in order, with time boxes | A and B (C: the last two) |
| TASKS.md | Who does what, and when. Pitch numbers. Requests between people. | Everyone |
| data/ | The scenario, carrier messages, emission factors with sources, and hand-checked answers | Claude Code + Person C |

## Start (before 11:35)
1. One person creates a GitHub repo, copies this kit into it, and pushes. Everyone clones it.
2. A and B: install Python 3.10+, then
   `pip install streamlit pydantic rapidfuzz pandas python-dotenv pytest mcp` plus your LLM SDK.
3. Make a `.env` with `LLM_PROVIDER=anthropic|openai|gemini`, the matching API key, and optionally `LLM_MODEL`.
   Never commit it.
4. At 11:35, Person A opens Claude Code in the repo and pastes PROMPT 0.

## Once the code exists
- Run the app: `streamlit run app.py` (to open it on a phone: `streamlit run app.py --server.address 0.0.0.0`)
- Run the tests: `pytest -q`
- Check extraction accuracy: `python offers.py --eval`

## Stretch: Claude Desktop as the agent (after the 14:00 gate)
Add this to the Claude Desktop config (Settings → Developer → Edit config):
```json
{"mcpServers": {"safety-car": {"command": "/ABSOLUTE/PATH/.venv/bin/python",
                               "args": ["/ABSOLUTE/PATH/safety-car/mcp_server.py"]}}}
```
Restart Claude Desktop. Tools: `get_shipment`, `check_options` (preview, no payment), `run_safety_car`
(acts within the spend policy; shares data/state.json with the app, so approvals appear on Sarah's phone view)
and `ledger`. There is deliberately no approve tool. Try: "Check the timing unit's options at 35%, then run
Safety Car." Test it without Claude Desktop: `npx @modelcontextprotocol/inspector` with command
`.venv/bin/python mcp_server.py`.
