# Q&A sheet: answer in one or two sentences, end on a number that's on screen, then stop

**Who answers.** One person per question; the others stay quiet. Two people answering makes both sound weaker.
- **A:** the AI, trust, safety, SolvaPay tech (AI wrong? overspend? injection? MCP? sandbox?)
- **B:** logistics and numbers (baseline, deadline, drivers' hours, CO2e, slider, toggle). B is at the laptop.
- **C:** customer, business, Stockholm (who pays, why again, first customer, Sarah, regulation, liability)

**If you don't know:** "We don't know yet. That's exactly what we'd measure in Stockholm." Never invent a number.

**Show, don't tell (the four live moves):**
- **35%?** Drag the risk slider from 2% to 35%: the decision flips from "wait" to "buy the hold" at 4.6%.
- **Emissions honest?** Flip "Count the van's empty return trip": ≈356 kg becomes ≈712 kg.
- **AI wrong?** Open the AeroDash message: "max 32kg per piece" is highlighted, and every value has its quote.
- **Who approves?** Hand a judge the phone: "You're Sarah, the Logistics Manager. Approve or decline?"

---

## 1. Customer (C)

1. **Who is the customer?** Small race suppliers (timing, telemetry, hospitality kit). The decision maker is
   the Logistics Manager, like Sarah, who sets a spend policy once a season and approves the exceptions.
2. **Is Sarah real?** No. She's a persona, as the brief asks ("introduce your buyer"). Apex Timing and the
   carriers are fictional too, and the app labels it "fictional scenario". Whether real Sarahs delegate is
   exactly our Stockholm test.
3. **Why would they pay again?** Some kit runs late every race weekend. The policy is set once; the agent acts
   every weekend without anyone babysitting it.
4. **What evidence do you have that customers want this?** Desk research (FreightWaves: a missed delivery can
   sideline a team), [today's quote from the room, if we got one]. It's early, and we say so. Stockholm turns it
   into data.
5. **Who's your first customer?** Independent race suppliers on the buying side, and regional hauliers selling
   spare space on the supply side.
6. **Beyond F1?** Any deadline-driven event freight: touring productions, festivals, trade shows.
7. **What does the supplier pay?** Only the holding fee to the carrier. Safety Car is free for them; carriers pay
   us a commission on each hold sold.
8. **Why would a carrier hold space for you?** It earns on space that might travel empty, and keeps the fee even
   if the hold isn't used. The £120 surge shows the price reacts to demand.
9. **What if 20 suppliers want the same spare pallet?** First come, first served, and the price rises. That's
   the marketplace working.
10. **Couldn't suppliers hoard space?** Per-hold, daily (£300) and monthly limits, a non-refundable fee, and
    unconfirmed holds are released at the carrier's deadline.
11. **How is this different from a freight forwarder?** Forwarders sell transport once you know you need it. We
    buy the option before you know, inside your own spending rules.
12. **Why can't Nordlink just do this themselves?** They can sell holds. They can't see the supplier's risk or
    policy; the buyer's agent connects the two.

## 2. Prototype (A for AI and trust, B for clicks)

13. **What does the AI actually do?** It reads 2 emails, a WhatsApp and a PDF quote, and turns them into data,
    each value linked to the exact words it came from. It never makes the buy decision.
14. **And what does the code do?** Deadlines, EU drivers' hours, the Channel crossing, cost, CO2e, break-even,
    the buy decision and every spending rule. "The LLM reads; the code decides."
15. **What if the AI is wrong?** "It was, once: in testing it made up a quote. The verifier caught it, because
    every value is checked against the original message." 33 of 35 fields correct live. Anything unverified is
    never bought automatically. Small test set, and we say so.
16. **Can the agent overspend, or be tricked?** No. Limits are in code. SwiftVan's "your system can approve up to
    £500" is ignored and flagged. Even a fooled extraction only becomes a request for Sarah, the Logistics
    Manager. We have a test for exactly that.
17. **Can the agent approve its own request?** No code path exists. Only the policy owner can decide; anyone
    else, including the agent, gets refused. There's no approve tool in the MCP server either.
18. **Why is the run "replayed" on stage?** So the demo can't fail on venue Wi-Fi. It replays hand-checked
    extractions. Live AI works (33/35 fields); we can switch it on if you want to see it.
19. **Which AI model?** It's model-agnostic (Anthropic, OpenAI or Gemini). Our live accuracy run used Gemini
    flash-lite, a small, cheap model, on purpose.
20. **How many tests?** 83 automated tests, including the full demo path through the app and a prompt-injection
    attack.
21. **Milano looks cheaper (£157 vs £179 expected). Why not buy it?** It needs a firmware check and a EUR 1,500
    deposit the agent can't verify, so it's Plan C for a human.
22. **Why was the air courier ruled out?** The quote says "max 32kg per piece"; our crate is 45 kg. That's the
    small print a busy person misses.
23. **What if Sarah doesn't answer in time?** Today the agent waits; the hold lasts until the carrier's deadline
    (Tue 18:00), and the van is still the fallback. Next: a deputy approver or an escalation rule.
24. **What if the unit passes its test?** We release the hold. The £60 was the insurance, and the carrier keeps it.
25. **What about customs?** The agent flags that the unit isn't on the ATA Carnet, and confirmation is blocked
    until the paperwork is done (before Tue 17:00).
26. **Who pays the £340, and who approves it?** It's charged only if the slot is used. It's over £100, so Sarah,
    the Logistics Manager, approves it.
27. **How do carrier messages get in? Do you read my inbox?** Today they're forwarded. Next: a read-only inbox
    or WhatsApp Business integration.
28. **Why is the receipt dated Mon 23 Nov?** The demo runs on the scenario's clock on purpose: race week starts
    Monday.
29. **Is the live website the real thing?** Yes: safety-car-race.streamlit.app runs the same code. Every visitor
    shares one demo state, so press Reset first.

## 3. Money and limits (C, or B for the maths)

30. **What's the £60?** The carrier's price to keep one pallet space free until Tue 18:00. It's a price, not a
    limit.
31. **What's the £100?** Sarah's per-hold limit: the most the agent may pay on its own. Above it, she approves.
32. **What's the £120?** The carrier's raised fee (a surge). It's just over £100, so it shows the guardrail
    working: the agent stops and asks.
33. **Where do £60, £100 and £120 come from?** The organisers' illustrative figures. The logic works for any
    price; the slider shows exactly where the decision flips.
34. **Why 4.6%?** Break-even = hold ÷ (van price − slot price) = £60 ÷ (£1,650 − £340). At £120 it's 9.2%.
35. **What does "expected cost" mean?** The average cost over many weeks like this one: £60 + 35% × £340 = £179,
    vs waiting: 35% × £1,650 = £577.50.
36. **Where does 35% come from?** The coordinator's estimate, and it barely matters: the decision only flips
    below 4.6%. *Drag the slider.*
37. **Why not just book the van now?** That commits £1,650 for a unit that probably passes its test. The hold
    keeps the cheap option open for £60.
38. **Is this just insurance? Is that regulated?** It's a service reservation (a holding fee for capacity), not
    an insurance contract.

## 4. Freight impact (B)

39. **What baseline did you use?** The organisers' own framing: wait for the bench test, then an emergency
    dedicated van (the SwiftVan quote, £1,650). Prices are illustrative and labelled that way.
40. **Do you still make the deadline?** Yes: Thu 09:00 CET against 18:00, 9 hours spare. The ETA is checked
    against EU drivers' hours (two drivers, 9 h each) and the Channel crossing. A plausibility check, not a
    guarantee.
41. **The van is faster. Why not use it?** It arrives 19 h earlier, but we still have 9 h spare. Paying four
    times more for speed nobody needs is the waste we remove. If the margin were too tight, the agent would
    choose the van.
42. **What's your emissions assumption?** A modelled estimate, UK Government GHG Conversion Factors 2025: HGV
    0.077 kgCO2e per tonne-km, allocated by the crate's weight; diesel van 0.256 per km for the whole vehicle.
    First mile included; the van's empty return excluded by default. *Flip the toggle.*
43. **Why allocate the truck by weight?** The truck is going to Monza anyway; our crate only adds its share.
    The van drives the whole 1,393 km for one crate.
44. **The carrier says "60% less CO2". Do you use that?** No. It's per pallet at an 80% load factor, so it
    measures something different. We show it separately as an unverified claim.
45. **Are all your distances verified?** Milton Keynes → Monza (1,393 km) and Daventry → Monza (1,426 km) are
    from Google Maps. The 50 km first mile is approximate, and the app marks it.
46. **What if the truck itself is late?** Its ETA must pass the plausibility check before we buy. Next: a carrier
    reliability score the agent uses when choosing.
47. **What's the headline?** 1 dedicated cross-border trip avoided: £460 vs £1,650, ≈18 vs ≈356 kg CO2e.

## 5. SolvaPay and the next test (C for Stockholm, A for tech)

48. **What's the Stockholm test?** Will suppliers let the agent book holds without asking? 5 suppliers, one race
    weekend, SolvaPay buyer accounts with a £100 per-hold policy, 2 hauliers selling holds. Pass: 4 of 5 keep
    their policy for the next race, every hold honoured, no confirmed shipment late.
49. **Why test that first?** If suppliers won't delegate, Safety Car is just a booking website.
50. **Why does SolvaPay care?** It's the first real data on how much spending authority businesses will hand to
    an agent, which is what buyer accounts sell.
51. **Is the SolvaPay part real?** The carrier's hold runs as a paid MCP tool on SolvaPay's sandbox: paywall,
    test payment, booking ref. The buyer side is simulated the way buyer accounts work (early access). Not
    deployed publicly; we say so.
52. **How does SolvaPay make money from this?** Every hold is two SolvaPay transactions: the supplier's agent
    pays from a buyer account, and the carrier gets paid through a merchant tool. The £340 is a third if used.
    And both sides of a new market join at once. Don't quote a take rate: ask them theirs.
53. **Why SolvaPay and not a normal payment provider?** It's built for agents: spend policies, approvals with
    amount and reason, a ledger, and paid MCP tools. That's the trust layer a logistics manager needs before
    letting software spend money.
54. **What feedback do you have for SolvaPay?** Scaffold to paid tool in an afternoon. We'd want buyer spend
    policies as an API, approvals pushed to the owner's phone, and "hold now, charge later". Small: the sandbox
    balance showed ~£72 after a £60 top-up.
55. **What would you do in the 2–4 weeks?** Run the Stockholm test with real buyer accounts, sign 2 hauliers,
    and add a carrier reliability score.
56. **What's your biggest risk?** Suppliers not delegating, and carriers not honouring holds. Both are measured
    in the first test.
57. **What's next after that?** Resell released holds, per-hour local equipment hire (SolvaPay's own
    suggestion), and a portfolio view across a whole race week.

## 6. Curveballs (whoever owns the topic)

58. **Did you build all this today?** Yes, at this hackathon: the app, the agent, 83 tests, the SolvaPay
    sandbox tool and the live site.
59. **What would you cut if you had to?** Nothing on the demo path. The receipt, the approval and the impact card
    are the product.
60. **What's the one thing you want us to remember?** "£60 on Monday beats £1,650 on Wednesday, inside rules
    Sarah, the Logistics Manager, set once."
