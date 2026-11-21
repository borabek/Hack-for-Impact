# TASKS.md: tick [x] when done and add your initials

Team of 3:
- **A = [name]**: backend, Claude Code
- **B = [name]**: logistics + UI, Claude Code. Drives the demo on stage.
- **C = [name]**: data, evidence, customer and pitch, using the claude.ai chat. Writes no code.

On stage: C opens (0:00–0:30) and closes (2:00–3:00), B clicks, A narrates the demo.

## Before 11:35
- [ ] Create a GitHub repo `safety-car`, add this kit and push. Everyone clones it.
- [ ] A and B: install Python 3.10+ and run `pip install streamlit pydantic rapidfuzz pandas python-dotenv pytest mcp`
      plus your LLM SDK. Put the API key in `.env` (never commit it).
- [ ] Choose the demo laptop (B's, since B drives).
- [ ] C: SolvaPay call notes, word for word (PLAN.md section 7).

## Person A: backend (Claude Code)
- [x] 11:35 PROMPT 0: scaffold + models.py (A)
- [x] 11:45 PROMPT A1: payments.py + tests (A)
- [x] 12:30 PROMPT A2: llm.py + offers.py + `--eval` (A). Accuracy line still needs an LLM key in `.env`.
- [ ] 13:00 take C's final data and update any expected numbers in the tests
- [x] 13:15 PROMPT A3: agent.py + tests (A). tests/test_agent.py auto-skips until logistics.py lands, then must pass.
- [ ] 14:00 gate (with B)
- [ ] After the gate, PROMPT A4: Track S first (SolvaPay sandbox MCP, hard stop 15:00) → MCP server → injection test
- [ ] 15:45 freeze

## Person B: logistics + UI (Claude Code)
- [ ] 11:45 PROMPT B1: logistics.py + tests (expected-results table)
- [ ] 12:40 PROMPT B2: app.py v1 on fake_run()
- [ ] 13:45 PROMPT B3: wire in agent.run, buttons and phone panel
- [ ] 14:00 gate (with A)
- [ ] After the gate, PROMPT B4: polish + Pitch view
- [ ] 15:45 freeze; practise the clicks until they're automatic

## Person C: data, evidence, customer, pitch (claude.ai chat, no code)
- [ ] 11:35 Ask the organisers how and where to submit, by when, and what's required
- [ ] By 13:00 Sign up at app.solvapay.com, copy a sandbox key (Console → Developers → API Keys) and send it to A
      privately (never in the repo). Skim the MCP quick start in their docs.
- [ ] 11:45 Real distances (Google Maps, via Dover–Calais) → factors.json, verified=true + source
- [ ] 11:45 Real indicative prices: dedicated van UK→Monza, on-board courier UK→Milan, groupage pallet UK→Italy (save sources)
- [ ] 11:45 Flight factor from the 2025/2026 UK Government set
- [ ] **13:00 DATA FREEZE**: hand the final data/ to A. If prices changed, update the carrier message AND expected_offers.json together.
- [ ] 13:00 Fetch lunch for the team
- [ ] 13:15 2–3 customer interviews (PLAN.md section 8), ideally with someone who has booked race or event freight:
      quote, name, role (label anything else as proxy feedback)
- [ ] 13:30 Script v1 + Q&A sheet (PLAN.md sections 4–5) → pitch/
- [ ] 14:15 Show the prototype to an organiser and get feedback
- [ ] 14:30 Build the slides from the final numbers + quotes
- [ ] 15:00 Check that every number on the impact card has a source or an "illustrative" label
- [ ] 15:15 Dress rehearsal · 15:45 backup video · 2 timed rehearsals · submit
- [ ] 16:15 Open the Buyer phone view on your own phone and test one approval (you tap Approve on stage)

## Pitch numbers (fill in from the app after 14:00)
- Extraction accuracy (`python offers.py --eval`):
- Cost if late, usual plan vs ours:
- Arrival and spare hours:
- CO2e, usual plan vs ours:
- Break-even probability (£60 and £120):
- £120 scenario, cost if late and expected cost:
- Customer quote:
- SolvaPay quote:

## Requests (changes needed in files you don't own)
- A → B (agent API for app.py, PROMPT B3):
  - `agent.run(scn, factors, payments, p_miss=, fee_rise=, use_llm=)` returns an `AgentRun`: `steps` (icon/title/detail),
    `options`, `offers`, `checks` (offer_id → QuoteChecks), `messages`, `files`, `sources`, `extraction`
    ("replayed"/"llm"), `recommended`, `baseline`, `breakeven`, `decision` ("hold"/"wait"/"needs_human"),
    `explanation`, `payment` {status, hold_id, receipt_id, approval_id}, `scenario_label` ("£60 hold"/"£120 hold"),
    and `impact` (usual vs ours: cost if late/not late, arrival, margin, dedicated km, CO2e, headline, hours later).
  - `agent.load_scenario()`, `agent.load_factors()`, `agent.confirm_slot(scn, factors, payments, paperwork_done=)`,
    `agent.release_hold(scn, payments)`, `agent.confirmation_card(scn, factors, payments)` → {ref, collection, eta, ...}.
  - Payments: `pending_approval()`, `decide(id, approve, by=scn.policy.owner)`, `last_receipt()`, `latest_hold()`,
    `active_hold(offer_id)`, `receipts`/`holds`/`ledger`/`approvals`, `reset()`, and `preview_policy(...)` (no ledger
    write) for the slider preview. Receipts have `kind` ("hold"/"transport").
  - My tests expect logistics to reproduce CLAUDE.md section 8 exactly (status, arrival, margin, costs, CO2e).
