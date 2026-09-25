# The four-minute demo

One presenter drives, one person handles the box. Nobody types a terminal
command on stage. Rehearse three times.

## Fifteen minutes before

```bash
make demo           # broker, database, backend, simulator, dashboard
make model          # only if ollama has not pulled qwen2.5:7b yet
```

- [ ] Phone hotspot on **2.4 GHz**, laptop IP fixed, same network as the NodeMCU.
- [ ] `make watch` shows `coldguard/TRK-07/telemetry` arriving. Close it.
- [ ] Box closed with two ice packs; resting air temperature **below 6 °C**.
- [ ] Dashboard open, TRK-07 selected, `LIVE sensor` tag showing, `live` pill green.
- [ ] QR code taped to the lid; open it once on your own phone.
- [ ] Press **D**, press **Reset demo**, press **D** again to hide the panel.
- [ ] Browser zoom so the fleet list and the options table are both readable.

## On stage

| Time | You do | They see | You say |
| --- | --- | --- | --- |
| 0:00 | Box closed on the table | Twelve trucks moving on Doha; TRK-07 tagged **LIVE sensor**; heat layer on the roads | "Every one of these is a pallet of food. Eleven are simulated. This one is a real sensor, in this box." |
| 0:40 | Lift the lid for five seconds | A bump on the blue line; the amber cargo line barely moves; the log says **door opening — no action** | "A door opening is not a failure. The air spikes; two tonnes of lettuce do not. If we alerted on this, nobody would read our alerts." |
| 1:10 | Take the sensor out and hold it in your hand | Blue line climbs past 8 °C and stays; amber line follows slowly | "Now the cooling has actually failed." |
| 1:50 | — | **Alert.** Freshness on arrival falls under six days, the truck turns amber | "Thirty-five seconds above the limit, door closed, temperature not coming down. That is a failure, not a door." |
| 2:00 | — | Six options with numbers; recommendation in Arabic and English | "Continue as planned and it arrives below what the store accepts — rejected at the gate. Deliver it straight to the nearest supermarket instead and it arrives inside the window. Every number here was computed in Python. The model only wrote the sentence." |
| 2:45 | Tap **Approve** | Route redraws to the supermarket; freshness on arrival back above six days; audit entry with its hash | "A person approved that. Nothing moves until someone does." |
| 3:20 | — | Comparison screen | "Without ColdGuard: two tonnes rejected and landfilled. With it: two tonnes sold, about twenty thousand riyals, five tonnes of CO2e avoided." |
| 3:45 | Put the sensor back in the box | Temperature falls; the cargo line follows slowly | "Scan the code on the box — the whole history of this shipment is on your phone." |

## The questions judges ask

**"How do you know the sensor is not lying?"** Minus 127, a silent board or an
impossible jump are all treated as a sensor fault: the freshness clock pauses
and the decision is escalated to a person. We would rather say *we don't know*
than produce a confident number from a broken sensor.

**"Does the AI invent the numbers?"** No. Every figure comes from deterministic
Python. The model receives a JSON of facts and writes two sentences. A guard
re-reads its output and rejects any number that is not in the facts, in Arabic
digits as well. If the model is slow or missing, a fixed template writes the
same sentences. *(If asked to prove it: press D, turn on backup mode, or just
point out that the card says `template` when ollama is not running.)*

**"What if it cannot decide?"** It says so. Press **D**, trigger a sensor fault,
and the card comes back with no recommendation and four buttons: sell, donate,
hold, reroute — plus the reason it will not choose.

**"Is this real data?"** Roads from OSRM, places from OpenStreetMap, weather from
Open-Meteo. Every file carries a `source` column. The product shelf-life
parameters are literature-based assumptions and are labelled as such.

**"What runs in the cloud?"** Nothing. This laptop, offline, no API keys.

## If something goes wrong

| Problem | Fix, in five seconds |
| --- | --- |
| Board will not connect | **D** → **Backup mode** — the simulator takes over TRK-07 and the demo carries on |
| No alert after 45 s | **D** → pick TRK-07 → **Cooling failure** |
| The local model is slow | Nothing to do; the card already says `template` and the numbers are identical |
| Something looks wrong | **D** → **Reset demo** — back to the start, same seed, no restart |
| Everything is on fire | Play the backup video |

Have the backup video cued before you walk up.
