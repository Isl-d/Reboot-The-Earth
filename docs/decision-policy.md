# When ColdGuard decides, and when it asks

ColdGuard never acts on its own: a person approves every action. But there is a
difference between *"here is the answer, please confirm it"* and *"this one is
not mine to call"*. Collapsing the two is how automated systems teach people to
click Approve without reading. This document is the line between them.

## The four verbs

Every decision comes down to one of four things a dispatcher can do, plus
leaving the shipment alone:

| Verb | What it means | What it costs |
| --- | --- | --- |
| **Reroute** | Send the load somewhere it can still be sold at full value: the nearest cold store, or straight to a supermarket, skipping the hub | Extra kilometres |
| **Sell** | Move it today at a markdown, off the truck | Part of the margin |
| **Donate** | Hand it to a food bank while it is still safe to eat | The revenue, not the food |
| **Hold** | Park it in a cold room and decide once the fault is understood | Today's delivery slot |
| *Continue* | Do nothing; the load is fine | Nothing |

Six options map onto these five verbs, because there are two sensible ways to
reroute. The dashboard groups them by verb so the choice is a choice between
*actions*, not between letters.

## When the system recommends

When the numbers are decisive, the planner scores every option with

```
score = kg_saved × value_per_kg − extra_km × cost_per_km − markdown_loss
```

and puts the best one forward with all six rows visible, so the recommendation
can be checked rather than trusted. Two guards sit on top of the arithmetic:

- **A healthy shipment is never moved.** Another option must beat "continue as
  planned" by a real margin before it is recommended.
- **Holding earns nothing once a load is out of specification.** Selling and
  donating genuinely rescue food below the store's bar, because those channels
  have no bar. Holding only delays the loss, so it is not credited with kilos
  it cannot save.

## When the system refuses to decide

Four conditions send a decision to a person with **no recommendation at all**.
The dashboard shows the four verbs, the reasons, and waits.

### 1. The sensor cannot be trusted

A reading of −127, a board that has gone silent, an impossible jump. Every
freshness number downstream is built on that reading, so the honest answer is
that we do not know. The freshness clock pauses; it does not guess.

*Why it matters:* a system that keeps producing confident numbers from a broken
sensor is worse than one that produces none. This is the failure mode that
loses people's trust permanently.

### 2. Nothing meets the store's minimum

When every option leaves the load below what the retailer accepts, the question
stops being arithmetic. Sell at a markdown, give it to a food bank, or hold it
and renegotiate? That depends on the contract, the relationship with the buyer,
and what the charity can actually take today — none of which the system knows.

### 3. Two genuinely different actions are worth the same

Two ways to reroute are one decision. But when *selling* and *rerouting* come
out within a margin of each other, the tie is broken by things outside the
model: whether the receiving store has space, whether the driver's hours are
nearly up, whether this customer has already had a late delivery this month.

### 4. The best action is irreversible and large

Selling off or donating a full load cannot be undone. Above a value threshold
this always goes to a person, even when the numbers are clear. Rerouting is
reversible; writing off twenty thousand riyals of stock is not.

## Why this shape

Three properties, in order of importance.

**Escalation is a feature of the model, not of the interface.** The planner sets
`needs_human_review` and the reasons; the dashboard renders them. A new client —
a driver's phone, a WhatsApp message, a warehouse screen — inherits the same
behaviour without reimplementing the judgement.

**The reasons are written down.** "Needs review" on its own is a shrug. Each
condition produces a sentence naming what the system could not resolve, and that
sentence is what the agent is given to explain.

**The language model is downstream of all of it.** It receives a JSON of facts
that already says whether this is a recommendation or a question, and it writes
prose accordingly. It never decides *that* something needs review, and it never
produces a number — a guard re-reads its output and rejects any figure that is
not in the facts.

## Where else this applies

The same escalation policy fits anywhere a cheap sensor drives an expensive,
irreversible decision:

- **Pharmaceutical cold chain.** A vaccine excursion has a regulatory answer, not
  a commercial one; the "hold" verb becomes "quarantine pending QA".
- **Blood and tissue logistics.** Everything is irreversible and everything is
  escalated; the value of the system is the evidence trail, not the recommendation.
- **Frozen and ambient storage.** Same detector, different thresholds: a freezer
  door left open is the same shape of event as a truck door.
- **Produce at the farm gate.** Sell, donate, hold and reroute are already the
  four things a farmer does with a surplus crate.
- **Retail markdown timing.** The freshness projection is the same calculation
  run against shelf stock instead of a truck.

In each case the deterministic part — detector, shelf-life model, options,
scoring, escalation rules, audit chain — is the same code. What changes is the
product table and the thresholds, both of which are data.

## Tuning

Everything in this document is a number in `backend/config.py`, overridable with
a `COLDGUARD_*` environment variable:

| Setting | Default | Meaning |
| --- | --- | --- |
| `REVIEW_MARGIN_QAR` | 1500 | Two different actions closer than this are a tie |
| `REVIEW_VALUE_QAR` | 15000 | Above this, an irreversible action always goes to a person |
| `REROUTE_MIN_GAIN_QAR` | 500 | How much better than "continue" an option must be |
| `HOLD_PENALTY_FRACTION` | 0.15 | What a missed delivery slot costs |
| `MARKDOWN_FRACTION` | 0.5 | The discount on a same-day sale |
| `DONATION_VALUE_FRACTION` | 0.3 | Value recovered by donating |

They are demo figures. Calibrate them with real contracts before anyone relies
on the output.
