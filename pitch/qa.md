# Q&A sheet: answer in one or two sentences, then stop

**Who answers.** One person per question; the others stay quiet. Two people answering makes both sound weaker.
- **A:** the AI, trust and safety (AI wrong? overspend? injection? MCP and SolvaPay sandbox?)
- **B:** logistics and numbers (baseline, deadline, drivers' hours, CO2e, slider, empty-return toggle). B is at the laptop.
- **C:** customer, business, Stockholm (who pays, why again, first customer, regulation, liability)

## The judges' known questions
1. **What baseline did you use?** The organisers' own framing: wait for the bench test, then send an emergency
   dedicated van (the SwiftVan quote, £1,650). Prices are illustrative and labelled that way.
2. **Do you still make the deadline?** Yes: Thu 09:00 CET against 18:00. The ETA is checked against EU drivers'
   hours and the Channel crossing. It's a plausibility check, not a guarantee.
3. **What's your emissions assumption?** A modelled estimate from UK Government GHG Conversion Factors 2025: HGV
   0.077 kgCO2e per tonne-km allocated by the crate's weight, and diesel van 0.256 per km for the whole vehicle.
   The first mile is included. The van's empty return is excluded by default; flip the toggle and it doubles.
4. **The van is faster, so why not use it?** It arrives 19 h earlier, but we still have 9 h spare. Paying four
   times more for speed nobody needs is the waste we remove. If the margin were too tight, the agent would choose
   the van.

## Your best moves
5. **Where does 35% come from?** "It's the coordinator's estimate, and it barely matters: the decision only flips
   below 4.6%." *Then drag the slider from 2% to 35% and show it flip.*
6. **What if the AI is wrong?** "It was, once: in testing it made up a quote. The verifier caught it, because
   every value is checked against the original message. Unverified fields are never bought automatically.
   33 of 35 fields correct live; it's a small test set."
7. **Can the agent overspend, or be tricked?** Limits are in code. SwiftVan's "your system can approve up to £500"
   is ignored and flagged. Even a fooled extraction only becomes an approval request for Sarah.
8. **Milano is cheaper (£157 vs £179 expected). Why not buy it?** It needs a firmware check and a EUR 1,500
   deposit the agent can't verify, so it's Plan C for a human.

## New questions to expect
9. **Is this just insurance? Is that regulated?** It's a service reservation, a holding fee for capacity, not an
   insurance contract.
10. **What if 20 suppliers want the same spare pallet?** First come, first served, and the price rises (that's
    the £120 surge). That's the marketplace working.
11. **How do carrier messages get in? Do you read my inbox?** Today they're forwarded. Next, a read-only inbox or
    WhatsApp Business integration.
12. **Who's liable if the held slot doesn't show?** The receipt and ledger are the evidence for a refund. Carrier
    honour rate is measured in the Stockholm test, and next comes a reliability score.
13. **Why can't Nordlink do this themselves?** They can sell holds. They can't see the supplier's risk or policy;
    the buyer's agent is what connects the two.
14. **Why the receipt date of Mon 23 Nov?** The demo runs on the scenario's clock on purpose: race week starts
    Monday.
15. **Is the SolvaPay part real?** The carrier's hold runs as a paid MCP tool on SolvaPay's sandbox: paywall,
    test payment, booking ref. The buyer side is simulated the way buyer accounts work (early access).

16. **How does SolvaPay make money from this?** (C, or A if it's technical) "Every hold is two SolvaPay
    transactions: the supplier's agent pays from a SolvaPay buyer account, and the carrier gets paid through a
    SolvaPay merchant tool. The £340 transport is a third if the slot is used, and our commission is collected
    through SolvaPay too. And both sides of a new market join SolvaPay at once; the Stockholm test is the proof
    their buyer accounts need." Don't quote a take rate: ask them theirs. If pushed: today the carrier side runs on
    the sandbox; the buyer side is simulated the way buyer accounts work (early access).

## From PLAN.md §5 (short versions)
- **Why AI at all?** Quotes come by email, WhatsApp and PDF, and the terms that matter are in the small print.
- **What about customs?** The ATA Carnet: the agent flags the unit isn't listed, and confirmation is blocked
  until the paperwork is done.
- **Different from a freight forwarder?** They sell transport once you know you need it. We buy the option
  before you know, inside your own rules.
- **Who pays the £340, and who approves it?** It's charged only if the slot is used; it's over £100, so Sarah
  approves it.
- **Couldn't suppliers hoard space?** Daily and monthly limits, a non-refundable fee, and unconfirmed holds
  released at the carrier's deadline.
- **What if the unit passes?** We release the hold. The £60 was the insurance, and the carrier keeps it.
- **First customer?** Independent race suppliers buying, and regional hauliers selling spare space.
- **Why SolvaPay?** Spend policies, approvals and a ledger are the trust layer a logistics manager needs before
  letting software spend money.
