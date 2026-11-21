# Q&A sheet: DRAFT by D for C to own

Answer in **one sentence, then show something on screen**. PLAN.md §5 has the 18 core answers; this sheet adds the
**show-it move** for the most likely ones and **new hard questions** that aren't in PLAN.md yet.
Who answers: **C** = customer/business/emissions, **A** = AI/payments/safety, **B** = logistics/times.

## The top 6 (rehearse these out loud)
| Question | One-sentence answer | Show |
|---|---|---|
| What baseline did you use? (C) | The organisers' own: wait for the test, then an emergency dedicated van (the SwiftVan quote, £1,650, illustrative). | Impact table, left column |
| Do you still meet the deadline? (B) | Yes, Thu 09:00 CET against 18:00, checked against EU drivers' hours and the Channel crossing. | Pit-window chart, red line |
| What's your emissions assumption? (C) | UK Government 2025 factors: HGV per tonne-km by the crate's weight, van per km for the whole vehicle, first mile included, van's empty return excluded. | CO2e expander, then flip the **sensitivity toggle** (356 → 712 kg) |
| Where does 35% come from? (B) | It's the coordinator's own estimate, and it barely matters: the decision only flips below 4.6%. | **Drag the slider to 2%**: the preview says "wait" |
| What if the AI is wrong? (A) | Every quote is checked against the original message, unverified fields can't trigger a purchase, and in live testing the checker caught a made-up quote. 33/35 fields on a small test set. | "What the AI read" expander, ✅/⚠️ |
| Can the agent overspend? (A) | No. Limits are enforced in code like a SolvaPay buyer account, the agent has no approve tool, and a carrier saying "approve £500" changes nothing. | 🛡️ step, then the Ledger view |

## New hard questions (not in PLAN.md)
1. **"Isn't this just insurance? Is that regulated?"** (C) It's a capacity reservation, a fee to hold space like a
   restaurant deposit, not an insurance contract. We pay the carrier for a service, not a payout on a loss.
2. **"What if 20 suppliers want the same spare pallet?"** (C) The carrier sells it first come, first served, and
   the price rises. That's the £120 surge in our demo, and the agent re-checks it against the policy every time.
3. **"How do carrier messages get in? Do you read my inbox?"** (A) Today the coordinator forwards them. Next: a
   read-only inbox or WhatsApp Business connection limited to approved carriers.
4. **"Why wouldn't Nordlink just sell holds themselves?"** (C) They can, and our carrier side runs as their paid
   tool on SolvaPay. But only the buyer's agent knows the risk, the deadline and the boss's policy, and it compares
   every carrier.
5. **"Who's liable if the carrier doesn't honour the hold?"** (C) The receipt and ledger are the evidence for a
   refund. Honour rate is a pass criterion in the Stockholm test, and next we add a carrier reliability score.
6. **"How big is the market?"** (C) Don't invent a number. Say: "We'd measure it in Stockholm: holds per supplier
   per race weekend. The same problem exists in touring productions, festivals and trade shows."
7. **"Why does this need SolvaPay rather than a company card?"** (A) A card can't tell an agent "£100 per hold,
   approved carriers only, ask Sarah above that". Spend policies, approvals and a ledger are exactly what a
   Head of Logistics needs before letting software spend.
8. **"What did you actually build today vs mock?"** (A) Real: LLM extraction + quote verifier, all the logistics
   and emissions maths, the policy engine, 83 tests, and a paid MCP tool on SolvaPay's sandbox. Simulated: the
   buyer-side card charge (SolvaPay buyer accounts are early access) and the carrier messages.
9. **"Why not use the faster van to be safe?"** (B) If the truck would arrive after the deadline, that option is
   blocked and never bought; under a 4 h margin the agent warns. Here we have 9 h spare, so paying four times more
   buys nothing. (Honest next step: make a thin margin escalate to Sarah instead of only warning.)
10. **"What happens to the £60 if the unit passes?"** (C) The carrier keeps it. It paid for space that was
    reserved for us. Next step: resell released holds so the carrier earns twice and nothing travels empty.

## If you don't know
"Good question. We haven't measured that yet, and it's exactly the kind of thing the Stockholm test is for."
Never guess a number.
