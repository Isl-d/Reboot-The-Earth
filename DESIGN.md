---
version: alpha
name: Cold Chain Command Center
description: Strategic Ops visual system for an AI-powered cold-chain management dashboard. Dense, precise, authoritative — built for operators managing food safety at scale.
colors:
  base: "#0c1825"
  surface: "#162338"
  elevated: "#1e3048"
  primary: "#00c8e0"
  primary-dim: "#0090a8"
  text-primary: "#c9d6e8"
  text-secondary: "#8fa8c8"
  risk-low: "#22d4b0"
  risk-medium: "#fbbf24"
  risk-high: "#fb923c"
  risk-critical: "#f87171"
typography:
  display:
    fontFamily: IBM Plex Sans
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: -0.02em
  h1:
    fontFamily: IBM Plex Sans
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.01em
  h2:
    fontFamily: IBM Plex Sans
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: -0.01em
  h3:
    fontFamily: IBM Plex Sans
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.3
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: IBM Plex Sans
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: 0.06em
  mono-lg:
    fontFamily: IBM Plex Mono
    fontSize: 20px
    fontWeight: 500
    lineHeight: 1
  mono-md:
    fontFamily: IBM Plex Mono
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1
  mono-sm:
    fontFamily: IBM Plex Mono
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1
rounded:
  sm: 2px
  md: 4px
  lg: 6px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  2xl: 64px
  gutter: 16px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.base}"
    rounded: "{rounded.sm}"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.primary-dim}"
    textColor: "{colors.base}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    typography: "{typography.label}"
  button-danger:
    backgroundColor: "{colors.risk-critical}"
    textColor: "{colors.base}"
    rounded: "{rounded.sm}"
    typography: "{typography.label}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    typography: "{typography.body-md}"
  input-error:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.risk-critical}"
    rounded: "{rounded.sm}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
  card-elevated:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
  modal:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    typography: "{typography.body-md}"
  badge-low:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.risk-low}"
    rounded: "{rounded.sm}"
    typography: "{typography.label}"
  badge-medium:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.risk-medium}"
    rounded: "{rounded.sm}"
    typography: "{typography.label}"
  badge-high:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.risk-high}"
    rounded: "{rounded.sm}"
    typography: "{typography.label}"
  badge-critical:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.risk-critical}"
    rounded: "{rounded.sm}"
    typography: "{typography.label}"
  sidebar:
    backgroundColor: "{colors.base}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.body-sm}"
  chip:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.sm}"
  tooltip:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    typography: "{typography.body-sm}"
  incident-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
  page-header:
    backgroundColor: "{colors.base}"
    textColor: "{colors.text-primary}"
    typography: "{typography.display}"
  section-heading:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.h2}"
  card-title:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.h3}"
  stat-value:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.h1}"
  sensor-reading-lg:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.mono-lg}"
  sensor-reading-md:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.mono-md}"
  sensor-reading-sm:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.mono-sm}"
---

# Cold Chain Command Center

## Overview

The Cold Chain Command Center is an operational dashboard for food-safety engineers monitoring a network of refrigerated trucks in real time. It sits at the intersection of military operations software and medical monitoring equipment — two domains where information must be instantly readable, urgency must be visually unambiguous, and nothing can be decorative for its own sake.

The aesthetic direction is **Strategic Ops**: deep command-room darkness, electric cyan as the single interaction signal, and risk severity communicated by color alone. The reference is the visual language of Palantir Foundry and Anduril Lattice — classified-document information hierarchy, tight density, cold authority.

Everything decorative has been traded for precision. The palette is two steps from pure black, the accent has one job, and the typeface family (IBM Plex) was purpose-built for information-dense interfaces.

## Colors

The palette is rooted in the visual signature of a dimmed command room — cool blue-slate backgrounds, a single electric cyan signal, and risk colors derived from OKLCH perceptual ramps rather than dropped in from a stock palette.

- **Tactical Slate (`base`, #0c1825):** The deepest background, named for the blue-black of a darkened cockpit glass. Used only for structural chrome: sidebar, topbar, the absolute outer shell.
- **Operational Navy (`surface`, #162338):** The primary card and panel surface. One perceptual lightness step above base, keeping depth without going flat.
- **Command Blue (`elevated`, #1e3048):** Modals, tooltips, badge backgrounds, and panels that float above the primary surface. The three-level tonal system (base → surface → elevated) replaces drop shadows entirely.
- **Signal Cyan (`primary`, #00c8e0):** The single interaction color, named for the bright return of a radar sweep. Exactly one job — interactive elements and live-connection indicators. Never decorative.
- **Deep Signal (`primary-dim`, #0090a8):** Dimmed Signal Cyan for hover and pressed states.
- **Arctic Haze (`text-primary`, #c9d6e8):** Primary readable text, blue-shifted near-white derived from the same OKLCH hue family as the backgrounds. It belongs to the palette rather than being neutral white dropped in from outside.
- **Slate Blue (`text-secondary`, #8fa8c8):** Secondary information — labels, metadata, sidebar navigation items.
- **Safe Teal (`risk-low`, #22d4b0):** Risk-free state. A teal-shifted green derived from the Signal Cyan chromatic family — it reads as "go" while belonging to the same visual world as the UI.
- **Amber Watch (`risk-medium`, #fbbf24):** Caution state. The highest luminosity token in the palette, ensuring it reads immediately in peripheral vision.
- **Alert Orange (`risk-high`, #fb923c):** High-risk state. Sits perceptually between amber and red, making the severity progression explicit without guessing.
- **Critical Rose (`risk-critical`, #f87171):** Emergency state. A lightened red — not the stock `#ef4444` — chosen to maintain 4.5:1 contrast against dark backgrounds while reading as undeniably urgent.

## Typography

Two typefaces, both from IBM's Plex family, differing by classification:

**IBM Plex Sans** — all UI labels, headings, and narrative text. Designed at IBM with the explicit brief of "confidence and precision." Its slightly mechanical stroke construction carries authority without coldness. Used in two weights: 400 for body, 600 for headings. The 700 weight appears only at display scale, for the page-level `COLD CHAIN COMMAND CENTER` heading.

**IBM Plex Mono** — every numeric reading in the system: temperatures, risk scores, humidity values, GPS coordinates, timestamps, percentages. The monospace construction ensures numeric columns align without layout hacks. It signals to the reader that these values are machine-measured, not human-authored.

The scale uses a 1.25 modular ratio for UI density. Body text runs at 14px — one pixel below the generic default — to tighten information density without crossing the legibility threshold at typical monitor distances. Optical tracking follows convention: negative at display sizes (−0.02em), positive on the uppercase `label` style (0.06em).

## Layout & Spacing

A strict 4px base grid (8px for rhythm, 4px for micro-adjustments). The layout is asymmetric: a fixed 56px sidebar holds navigation; the main content area is unconstrained and expands with viewport width.

The Command Center view uses a fixed 60/40 horizontal split — map left, incident panel right. This is not a responsive breakpoint; it is an ops-room layout decision. Wider screens reveal more map detail and more incidents simultaneously.

No max-width constraint on any view. Centering white space is a landing-page convention; this is a tool.

## Elevation & Depth

Depth is communicated through tonal stepping only — no box shadows anywhere in the application:

1. **Base** (`#0c1825`) — absolute floor: sidebar, outer chrome
2. **Surface** (`#162338`) — primary content plane: cards, tables, main panels
3. **Elevated** (`#1e3048`) — raised elements: modals, tooltips, badge backgrounds

The boundary between levels uses a 1px structural border at `#2d4160`. This border is used to mark panel edges, not to decorate them. Drop shadows are banned: they blur the tonal clarity that makes depth legible in this dark environment.

## Shapes

**Architectural Sharpness.** The radius scale is deliberately conservative: 2px for interactive atoms (buttons, inputs, chips, badges), 4px for containers (cards, panels), 6px for large floating elements (modals). Nothing exceeds 6px.

Data panels — sensor readout grids, telemetry tables, the map container — use zero radius. They are data containers, not UI cards, and the sharp edge reinforces that distinction.

The `rounded-2xl` Tailwind default is the clearest signal that no designer touched a UI. This system gives it up in full.

## Components

Risk badges use a tonal elevated background with colored text — not colored backgrounds. Colored badge backgrounds create contrast failures at mid-range chroma values (the amber and teal hues). Text-layer color signals read more precisely and survive against multiple background levels without adjustment.

Signal Cyan is the only color that appears as a primary button background. All destructive actions use Critical Rose (`risk-critical`) with Tactical Slate text. Secondary actions use the surface tonal background with Signal Cyan text. A single interaction color per screen is sufficient; more dilutes the signal.

All sensor readings, temperatures, and numeric risk scores are rendered in the IBM Plex Mono type scale. The `sensor-reading-lg` (20px) style is reserved for the primary live reading at the top of a truck detail card. Supporting values use `mono-md` (14px). Timestamps and coordinates use `mono-sm` (12px).

## Do's and Don'ts

- Do use Signal Cyan (`primary`) only for interactive elements and live-connection indicators. It does not appear in backgrounds, borders, or decorative elements.
- Do render every temperature, percentage, score, and timestamp in IBM Plex Mono. Proportional numerics on a data dashboard break scanning rhythm.
- Don't use a risk color for anything other than risk state. Amber Watch does not mean "secondary action" — it means a truck is at risk.
- Don't add drop shadows. The three-level tonal system (base → surface → elevated) communicates all necessary depth.
- Don't introduce a fourth background level. If a panel needs separation, use the 1px border at `#2d4160`.
- Do display a live timestamp on every sensor reading panel. Unlabeled data age is an operational hazard.
- Don't abbreviate risk levels in badges or incident cards. "CRITICAL" not "CRIT", "MEDIUM" not "MED". The full word fits and is unambiguous.
- Don't use more than two IBM Plex weights on a single screen (400 + 600). The 700 `display` weight is reserved for the top-level page heading only.
- Do use the `label` type style (uppercase, 0.06em tracking) for all field labels in data panels. It creates the classified-document visual grid that defines the direction.
- Don't center content in the main area. Left-aligned dense grids read faster than centered layouts in operational contexts.
