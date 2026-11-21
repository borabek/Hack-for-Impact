# Final-hour checklist (in order)

## Now → 15:15: evidence and risk
- [ ] Customer quote, word for word, with name and role ("proxy feedback" if they don't book freight).
      Put it in `pitch/script.md` and on slide 1 of the deck.
- [ ] SolvaPay quote: show them the live link on a phone and ask "Is this how you'd want buyer spend policies used?"
- [ ] Ask the organisers: submission deadline, format (repo / link / video / slides) and where to submit.
- [ ] Phone test NOW on the venue Wi-Fi: phone opens the laptop's Network URL → Buyer phone → Approve.
      Plan B if the Wi-Fi blocks it: laptop AND phone both open https://safety-car-race.streamlit.app (they share
      one state; press Reset first, press R on the laptop after the tap). Plan C: approve on the laptop's phone panel.
- [ ] SolvaPay clip: paywall → test card → booking. Then OPEN THE FILE and check it plays.

## 15:15 → 15:45: rehearse
- [ ] Dress rehearsal 1 with a phone timer. Over 1:30 in the demo segment → skip the £60 run.
- [ ] The closer starts the Stockholm slide by 2:30 at the latest, even mid-sentence.
- [ ] Q&A roles (see `qa.md`). Practise the slider (2% → 35%) and the empty-return toggle.

## 15:45: freeze (on the demo laptop)
```bash
git pull
```
```bash
pytest -q
```
- [ ] Restart Streamlit (`streamlit run app.py --server.address 0.0.0.0`), press Reset, live AI off, zoom 125%.
      **Always restart after a pull:** a running app keeps old code in memory and can crash on Run (seen on the
      public site at 15:40; a reboot fixed it). Then click Run once to check, and Reset.
- [ ] If anyone ran the Claude Desktop demo on this laptop, press Reset again (it shares data/state.json).
- [ ] Record the 2:30 backup video, then check it plays.
```bash
git tag pitch && git push --tags
```

## 15:45 → 16:25: deliver
- [ ] Rehearsal 2 with the timer, then a 10-minute hostile Q&A drill from `qa.md`.
- [ ] Submit by 16:20: repo link, https://safety-car-race.streamlit.app, video, slides. Open the live link first so
      it's awake, and press Reset.
- [ ] Laptop: Focus mode on, charger, venue screen tested, hotspot ready, other apps closed.

## On stage
- First line: "£60 on Monday beats £1,650 on Wednesday." Last line: what Stockholm proves for SolvaPay.
- Pause one second on the £500 injection line and on the Approve tap.
- Optional, only if rehearsed: hand a judge the phone: "You're Sarah. Approve or decline?"
- Show the public link only on the closing slide (the demo runs on the laptop's own copy); never say a number
  that isn't on screen.

## After the pitches
- [ ] Talk to the SolvaPay judges; send the follow-up in `followup.md` (a person sends it, after the pitch).
