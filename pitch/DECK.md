# Twelve slides

Non-technical. Two slides on the hardware. One number per slide where possible.

**1. A photo of the box.**
"There is a real temperature sensor in this box. In four minutes I am going to
break its cold chain in front of you."

**2. The problem.**
13 % of food is lost between harvest and retail; another 19 % is wasted after.
Food loss and waste cause 8–10 % of global emissions. *(FAO/UNEP 2024.)*

**3. Why here.**
Qatar imports most of its fresh food across a summer that passes 45 °C. A truck
fridge that fails at noon can spoil a load in hours. The National Food Security
Strategy 2030 targets −50 % food waste and −30 % food loss.

**4. What actually goes wrong.**
Nobody finds out until the load is rejected at the gate. By then the food is
already gone, and so is the chance to do anything else with it.

**5. ColdGuard in one line.**
A live freshness score for every pallet, and one recommended action a person
approves with one tap.

**6. The hardware.** *(photo: NodeMCU, DHT11, cooler box, ice packs)*
About forty riyals of parts per pallet. Any sensor that can send a temperature
works; this happens to be the cheapest one we could buy.

**7. Telling a door from a disaster.** *(the chart: blue air, amber cargo)*
The air spikes when you open a door. Two tonnes of lettuce do not. We track the
cargo temperature, not the sensor reading, and only alert on a real failure —
because an alert nobody reads is worse than no alert.

**8. Predicting the outcome, not the temperature.**
The question is not "how hot is it" but "will this still be accepted when it
arrives". Q10 shelf-life model, per product, against the store's minimum.

**9. Four things you can do.**
Reroute, sell, donate, hold — each with its kilometres and its money, so the
recommendation can be checked instead of trusted.

**10. And when it should not decide.**
Broken sensor, nothing within specification, a genuine tie, or an irreversible
write-off: no recommendation, four buttons, and the reason. *This is the slide
that separates us from a dashboard with a magic button.*

**11. Where the AI is, and is not.**
Every number is deterministic Python. A local model — no cloud, no API key —
writes two sentences in Arabic and English from those numbers, and a guard
rejects any figure it invents. Every decision is hash-chained to the one before.

**12. The ask.**
One cold-chain operator, one month, twenty pallets. We can tell you on day one
how much of your loss is refrigeration and how much is scheduling.

---

### Backup slides

- **Real vs simulated.** Real: TRK-07's readings, the physical events, all the
  logic, the local model, the open road and weather data. Simulated: eleven
  trucks, their movement, store stock, and carrying out the actions.
- **Heat-aware dispatch.** Leaving at 05:00 instead of 14:00 saves 1.7 hours of
  shelf life before the truck has moved a metre.
- **The freshness passport.** The QR code on the box. Scan it and the shipment's
  whole history is on your phone — the beginnings of a GS1 EPCIS record.
- **Roadmap.** Phone-camera quality check on arrival, predictive maintenance of
  cooling units, driver voice alerts in five languages, sell-first warehouse
  lists, a national food-loss and CO2 dashboard, a cold-chain gap map.
- **Architecture.** One Python process, Postgres, MQTT, a local LLM, a React
  dashboard. Nothing that cannot run on a laptop in a warehouse office.
