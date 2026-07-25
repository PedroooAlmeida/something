# Handoff: Gordon — AI Coding Coach (desktop overlay + Kitchen dashboard)

## Overview

Gordon is a desktop overlay that watches how you use AI coding tools. When you submit a prompt in a
supported AI tool, Gordon captures the prompt (+ a screenshot of the active window), scores it 0–100
across six categories, then appears in the corner of the screen to **roast you, diagnose the mistake,
teach the lesson, and hand you a rewritten prompt**. Violations are logged to a progress dashboard
("The Kitchen") and can fire physical punishment devices over a webhook.

This bundle covers the **frontend/overlay surface** (PRD Person 1's scope, plus the personality and
privacy surfaces): onboarding, the always-on-top overlay card, the six-category radar verdict, the
progress dashboard, the personality selector, settings (roast intensity + ElevenLabs voice + devices),
and privacy controls.

## About the design files

`Gordon.dc.html` in this folder is a **design reference created in HTML** — a working prototype that
demonstrates the intended look, motion, copy, and interaction flow. It is **not production code to
copy**. The job is to **recreate these screens in the target codebase's environment** — for Gordon
that will most likely be **Tauri or Electron + React**, per the PRD — using that project's existing
component library, state management, and styling conventions.

If no environment exists yet: React + TypeScript in a Tauri shell is the recommended target. The
overlay window should be a frameless, transparent, always-on-top window; the Kitchen dashboard can be
a second window or a routed view inside the same window.

To view the prototype: open `Gordon.dc.html` in a browser (keep `support.js` next to it). Both files
are in this folder.

## Fidelity

**High fidelity.** Colors, type, spacing, radii, motion timings and all copy are final and specified
below. Recreate pixel-accurately unless the target codebase has an established design system, in
which case map the tokens below onto that system and keep the layout/proportions.

All colors are authored in **oklch**. Modern browsers and Tauri/Electron webviews support it natively.
Approximate sRGB hex equivalents are given for platforms that need them.

---

## Design tokens

### Color

| Token | Value (oklch) | ≈ hex | Use |
|---|---|---|---|
| `bg/base` | `oklch(0.13 0.014 268)` | `#0d0e14` | app background |
| `bg/glow-violet` | `oklch(0.24 0.05 292 / 0.55)` | — | radial glow, top-right (1200×700 @ 78% 8%) |
| `bg/glow-ember` | `oklch(0.24 0.06 32 / 0.40)` | — | radial glow, bottom-left (900×600 @ 10% 92%) |
| `surface/1` | `oklch(0.155 0.014 268)` | `#101117` | window body |
| `surface/2` | `oklch(0.165 0.016 268)` | `#12131a` | overlay card, panel rows |
| `surface/3` | `oklch(0.185 0.016 268)` | `#16171f` | cards inside panels |
| `surface/4` | `oklch(0.20 0.016 268)` | `#191a23` | titlebars, chips |
| `surface/sunken` | `oklch(0.115 0.012 268)` | `#0b0c11` | code blocks |
| `border/1` | `oklch(0.27 0.02 268)` | `#24252f` | default border |
| `border/2` | `oklch(0.30 0.02 268)` | `#292a35` | window border |
| `border/3` | `oklch(0.34 0.02 268)` | `#2f303c` | button border |
| `text/hi` | `oklch(0.94 0.008 268)` | `#eceef2` | primary text |
| `text/mid` | `oklch(0.78 0.012 268)` | `#bfc2ca` | body copy |
| `text/lo` | `oklch(0.60 0.015 268)` | `#8b8e99` | labels |
| `text/faint` | `oklch(0.48 0.015 268)` | `#6b6e79` | meta / monospace captions |
| `accent/ember` | `oklch(0.74 0.16 52)` | `#eb8b3e` | **primary accent** (user-tweakable) |
| `accent/ember-deep` | `oklch(0.63 0.19 28)` | `#d95f34` | gradient end |
| `accent/violet` | `oklch(0.76 0.13 300)` | `#c48ce8` | frontier-knowledge card |
| `ok/mint` | `oklch(0.78 0.15 165)` | `#4fd6a8` | good scores, safe privacy facts |
| `warn/amber` | `oklch(0.80 0.14 85)` | `#dda93f` | mid scores |
| `bad/red` | `oklch(0.72 0.18 32)` | `#e4713f` | low scores, violations |

The **accent is a runtime tweak** with four presets: ember `oklch(0.74 0.16 52)`, magenta
`oklch(0.74 0.16 340)`, mint `oklch(0.74 0.16 165)`, violet `oklch(0.74 0.16 285)`. Current default in
the prototype is **violet `oklch(0.74 0.16 285)`**. It drives: send button gradient, toggle "on" state,
intensity selector, volume bars, roast rail, device-fire flash.

Primary CTA gradient: `linear-gradient(135deg, oklch(0.74 0.16 52), oklch(0.63 0.19 28))` on
`color: oklch(0.15 0.03 40)`; hover `filter: brightness(1.1)`.

### Typography

Two families, both Google Fonts:

- **Space Grotesk** — 400/500/600/700 — all UI text, headings, body.
- **IBM Plex Mono** — 400/500/600 — labels, metadata, code, section numbers, status lines.

| Role | Font | Size / line-height | Weight | Letter-spacing |
|---|---|---|---|---|
| Panel H1 | Space Grotesk | 25 / 1.2 | 700 | -0.02em |
| Section title | Space Grotesk | 19 / 1.2 | 700 | 0 |
| Metric number | Space Grotesk | 26 / 1 | 700 | -0.02em |
| Score number | Space Grotesk | 40 / 1 | 700 | -0.03em |
| Roast quote | Space Grotesk | 14.5 / 1.5 | 500 | 0 |
| Body | Space Grotesk | 12.5 / 1.6 | 400 | 0 |
| Small body | Space Grotesk | 11.5 / 1.5 | 400 | 0 |
| Eyebrow label | IBM Plex Mono | 10 / 1 | 400 | 0.14em |
| Chip / button label | IBM Plex Mono | 10–11 / 1 | 500 | 0.08em |
| Code block | IBM Plex Mono | 11.5 / 1.65 | 400 | 0 |
| Brand wordmark | IBM Plex Mono | 11.5 / 1 | 600 | 0.16em |

Eyebrow labels are always UPPERCASE. Long prose uses `text-wrap: pretty`.

### Spacing, radii, shadows

- Spacing scale in use: 2, 4, 6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26 px.
- Radii: `4` (menubar mark) · `5–7` (chips, small buttons) · `8–9` (buttons, rows) · `10–12` (cards) · `14–16` (windows, overlay card) · `18` (onboarding modal) · `999` (toggles, status pills).
- Overlay card shadow: `0 30px 80px -24px oklch(0.04 0.02 268), 0 0 0 1px oklch(0.1 0.01 268 / 0.6)`.
- Window shadow: `0 50px 120px -30px oklch(0.03 0.02 268)`.
- Tool window shadow: `0 40px 90px -30px oklch(0.05 0.02 268 / 0.9)`.
- Glass surfaces: `backdrop-filter: blur(18px)` (menubar), `blur(24px)` (overlay card), `blur(6px)` (modal scrim).

### Background texture

Behind everything: a 40×40px grid of 1px lines at `oklch(0.5 0.02 268 / 0.06)`, whole layer at
`opacity: 0.35`, `pointer-events: none`.

### Keyframes

```css
@keyframes gwave  { from{transform:scaleY(.35)} to{transform:scaleY(1)} }
@keyframes gpop   { from{opacity:0;transform:translateY(26px) scale(.965)} to{opacity:1;transform:none} }
@keyframes gfade  { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
@keyframes gpulse { 0%,100%{opacity:1} 50%{opacity:.25} }
@keyframes gflash { 0%,100%{box-shadow:0 0 0 0 oklch(.72 .17 48/0)} 50%{box-shadow:0 0 0 6px oklch(.72 .17 48/.25)} }
@keyframes gspin  { to{transform:rotate(360deg)} }
```

---

## Screens / views

### 1. Menu bar (always visible, 34px)

Fixed strip at the top of the desktop. `background: oklch(0.16 0.014 268 / 0.82)`, `blur(18px)`,
1px bottom border `oklch(0.28 0.02 268 / 0.7)`, horizontal padding 14px.

- **Left**: 14×14 rounded-4 gradient mark `linear-gradient(135deg, oklch(0.78 0.17 55), oklch(0.6 0.2 25))`; wordmark `GORDON`; then a monitoring pill — 6px dot + label, `gpulse 1.6s infinite`.
  - Watching: label `WATCHING`, dot/text `oklch(0.75 0.16 32)`, bg `oklch(0.26 0.07 32)`, border `oklch(0.45 0.1 32)`.
  - Paused: label `PAUSED`, dot/text `oklch(0.62 0.015 268)`, bg `oklch(0.21 0.016 268)`, border `oklch(0.3 0.02 268)`.
- **Right**: `PAUSE ⌥⇧G` / `RESUME ⌥⇧G` button, `KITCHEN ⌘K` button, clock `Fri 23:47`.
  Buttons: 1px `oklch(0.34 0.02 268)`, bg `oklch(0.2 0.016 268)`, radius 7, padding 6/11. Hover: border + text go accent-ember.

**Real implementation note:** in Tauri/Electron this is a tray/menubar item, not an in-app strip. The
strip in the prototype stands in for it.

### 2. Host AI tool window (demo scaffolding only)

A generic AI chat app ("Clyde") that stands in for whatever tool the user is really in. **Do not
build this** — it exists so the overlay can be demoed. Useful only as a reference for how the overlay
sits over other apps. Max-width 880px, radius 14, traffic lights, URL pill, message thread, preset
prompt chips, composer with word/token counter.

The four preset chips map to the four evaluation scenarios (`token dump`, `"make this work"`,
`outdated model`, `an actually good one`) — keep these in a dev/demo build for testing the overlay
without a live capture pipeline.

### 3. Gordon overlay — the hero surface

Fixed to `bottom: 22px; right: 22px; z-index: 40`. Column, `gap: 10px`, right-aligned.
Width animates: **330px idle → 418px when a verdict is shown**.

#### 3a. Device status strip (above the card)

Pill container: padding 6, radius 11, `oklch(0.17 0.014 268 / 0.9)`, blur 14, border `oklch(0.29 0.02 268)`.
Three device chips (EMBER LAMP / DESK BUZZER / BELL-BOT), each = 6px dot + 9.5px mono label,
padding 5/9, radius 7.

| State | bg | border | dot | text | anim |
|---|---|---|---|---|---|
| firing | `oklch(0.32 0.1 32)` | `oklch(0.65 0.17 32)` | `oklch(0.8 0.19 32)` | `oklch(0.9 0.13 40)` | `gflash 0.5s ×3` |
| armed | `oklch(0.2 0.016 268)` | `oklch(0.28 0.02 268)` | `oklch(0.6 0.11 155)` | `oklch(0.72 0.015 268)` | none |
| off | `oklch(0.17 0.014 268)` | `oklch(0.28 0.02 268)` | `oklch(0.4 0.015 268)` | `oklch(0.45 0.015 268)` | none |

#### 3b. Card shell

Radius 16, `oklch(0.165 0.016 268 / 0.96)`, `blur(24px)`.
Border: `oklch(0.3 0.02 268)` idle → `oklch(0.42 0.09 40)` on verdict.
Entrance on verdict: `gpop 0.42s cubic-bezier(.2,1.2,.3,1)`.

#### 3c. Waveform head — *the character*

Gordon has no face. **The waveform is the character.** Header block: padding 14/16/12, bottom border
`oklch(0.26 0.02 268)`, tint `linear-gradient(180deg, <tint>, transparent)` where tint is
`oklch(0.3 0.09 40 / 0.6)` while speaking and `oklch(0.22 0.02 268 / 0.5)` otherwise.

Top row: persona name (700 12px) + voice chip (`11LABS · EMBER`, or `MUTED` when paused); right side
`SWAP` (hover → violet) and `✕` buttons.

Waveform: **34 bars**, 3px wide, 2px gap, radius 2, container height 56px, centered.
- Amplitude: `height = seed[i] * amp + (i % 3) * 2`, min 3px, where **amp = 34 while speaking/thinking, 9 when idle**. `transition: height .25s ease`.
- Seed multipliers (0–1), in order:
  `.42 .78 .31 .95 .55 .70 .38 .88 .62 .44 .81 .29 .72 .50 .93 .35 .66 .84 .40 .58 .76 .33 .90 .47 .69 .53 .86 .36 .74 .60 .45 .82 .39 .65`
- Per-bar `animation: gwave <dur> ease-in-out infinite alternate`, `dur = 0.42 + (i%5)*0.13` s, `delay = (i%7)*0.06` s.
- Fill: speaking → `linear-gradient(180deg, oklch(0.85 0.15 58), oklch(0.62 0.2 26))`; idle → flat `oklch(0.42 0.03 268)`.

Status line under the waveform, 9.5px mono, `letter-spacing: .14em`, centered:

| Condition | Text | Color |
|---|---|---|
| paused | `PAUSED — HE IS SULKING` | `oklch(0.52 0.015 268)` |
| scoring | `SCORING YOUR PROMPT…` | `oklch(0.52 0.015 268)` |
| speaking | `SPEAKING · STREAMING AUDIO` | `oklch(0.82 0.14 45)` |
| verdict, done | `AWAITING YOUR MOVE` | `oklch(0.82 0.14 45)` |
| idle | `LISTENING` | `oklch(0.52 0.015 268)` |

#### 3d. Idle footer (no verdict)

Padding 12/16/14. One quip (11.5px, `text/lo`) + `KITCHEN` button.
- paused: "Paused. Nothing is being captured. Enjoy your mediocrity."
- scoring: "Reading your prompt. This won't take long — there isn't much of it."
- idle: "Send a prompt. I'll tell you what's wrong with it."

#### 3e. Verdict body

Padding 14/16/16, `gap: 13px`, `max-height: 60vh`, scrolls. Blocks fade in with `gfade 0.35s both`
at delays 0 / .08 / .16 / .24 / .28 / .32 / .40s.

**Score + radar row** (`gap: 14px`):
- SVG radar, 118×118, viewBox `0 0 148 148`, center (74, 74). Three guide hexagons at r = 20 / 38 / 56, strokes `oklch(0.24 / 0.26 / 0.28 · 0.02 268)`. Vertex i at angle `-90 + 60i` degrees, in category order **Specificity, Tokens, Frontier, Tool, Context, Verify**. Data polygon radius `8 + (score/100) * 48`; stroke-width 1.5, round joins, 2.2r dots on each vertex.
  - score ≥ 75: fill `oklch(0.72 0.15 165 / 0.2)`, stroke `oklch(0.78 0.15 165)`.
  - else: fill `oklch(0.72 0.18 32 / 0.2)`, stroke `oklch(0.78 0.17 34)`.
- Right column: 40px score number + `/100`; verdict label (10px mono, `.1em`) — `BURNT · SEVERITY 3`, `RAW · SEVERITY 2`, `STALE · SEVERITY 2`, `SERVICEABLE`.
- Six category rows, `grid-template-columns: 64px 1fr 24px`, gap 7, row gap 4. 4px track `oklch(0.24 0.018 268)`, fill width = score%. Fill color: ≥70 mint, ≥40 amber, else red. The **primary category's label is highlighted** `oklch(0.85 0.14 32)`; others `oklch(0.6 0.015 268)`.

**Score color thresholds** (number + label): ≥75 mint · ≥45 amber · else `oklch(0.72 0.18 32)`.

**01 · ROAST** — padding 13/14, radius 11, bg `oklch(0.22 0.045 36)`, 2px left border in accent.
Eyebrow in accent; quote 14.5px/1.5 weight 500 `oklch(0.95 0.008 268)`.

**02 · DIAGNOSIS** and **03 · BETTER APPROACH** — eyebrow `oklch(0.55 0.015 268)`, body 12.5/1.6 `text/mid`.

**Frontier knowledge card** (only when the scenario has a source) — padding 11/12, radius 10,
bg `oklch(0.2 0.03 292)`, border `oklch(0.36 0.05 292)`. Eyebrow `FRONTIER KNOWLEDGE` in
`oklch(0.76 0.13 300)`, release date right-aligned, body `oklch(0.85 0.02 292)`, then
`OPEN RELEASE NOTE ↗` link + confidence string. **Never render a claim here without a source + date.**

**04 · FIXED PROMPT** — eyebrow row with `COPY` button (label → `COPIED ✓` for 1.6s). Code block:
padding 12/13, radius 10, bg `oklch(0.115 0.012 268)`, border `oklch(0.27 0.02 268)`,
IBM Plex Mono 11.5/1.65 in `oklch(0.8 0.05 155)`, `white-space: pre-wrap`, `max-height: 150px`, scrolls.

**Actions** — `Use this prompt` (flex 1, gradient CTA, radius 9, padding 11) + `Ignore him` (ghost,
1px `oklch(0.32 0.02 268)`).

**Footer** — `logged → token_conservation · desk_buzzer` (or `nothing logged. shame.` on a clean
prompt) and a `VIEW KITCHEN` underlined text button.

### 4. The Kitchen (modal window)

Scrim `oklch(0.08 0.012 268 / 0.72)` + `blur(6px)`, padding 26. Window: max 1000×660, radius 16,
`surface/1`, border `border/2`, `gpop 0.3s`. Titlebar 46px on `oklch(0.185 0.016 268)`: mark +
`THE KITCHEN` + four tabs (active bg `oklch(0.26 0.02 268)`, text `oklch(0.94 0.01 268)`; inactive
transparent, `text/lo`) + `CLOSE ESC`. Body scrolls, padding 22/24/28.

#### 4a. Dashboard

- **Kitchen rating**: eyebrow, then 5 pips (26×9, radius 3) — 3 filled with the ember gradient — plus name **"Line Cook"** (700 17px) and note *"Two more clean days and he'll promote you to Chef de Partie. He will not be nice about it."*
- **Today, in Gordon's words** card (max 330px, `surface/3`): eyebrow in accent, then
  *"You were yelled at N times today. Yesterday it was 17. Unfortunately, this counts as progress."*
  Zero-state: *"Zero interruptions. Either you've improved or you've stopped working. I know which one I'd bet on."*
- **Metric grid**: `repeat(auto-fit, minmax(160px, 1fr))`, gap 10. Cards padding 14, radius 11, `surface/3`.
  Eyebrow 9.5px mono → value 26px/700 → sub 10.5px mono.
  1. `YELLED AT TODAY` · live count · "↓ from 17 yesterday" · `oklch(0.8 0.16 40)`
  2. `AVG PROMPT SCORE` · 67 · "↑ 36 in two weeks" · mint
  3. `TOKENS NOT WASTED` · e.g. 12.4k · "est. from shortened prompts" · `text/hi`
  4. `WORST CATEGORY` · Specificity · "12 hits · 14 days" · amber
- **Category tracking (14 days)** — `grid-template-columns: 132px 1fr 60px`, 7px tracks radius 4.
  Specificity 82% "12 hits" · Token conservation 64% "9 hits" · Context 51% "7 hits" ·
  Verification 38% "5 hits" · Tool selection 24% "3 hits" · Frontier 14% "2 hits".
  Bar color: >60 red, >35 amber, else mint (**high = bad** here — these are violation counts).
- **Avg score trend** — SVG `viewBox 0 0 300 110`, `preserveAspectRatio: none`, height 120.
  Three horizontal gridlines at y = 27/55/83 in `oklch(0.25 0.02 268)`. Series
  `31 28 36 34 42 39 47 44 52 49 58 55 61 67` mapped `x = i*(300/13)`, `y = 105 - v*0.95`.
  Area fill `oklch(0.72 0.17 168 / 0.14)`, line `oklch(0.75 0.15 168)` 2px, dots r2 `oklch(0.8 0.13 168)`.
  Caption: *"31 → 67. He's still furious, just less often."* Axis labels `14d ago` / `today`.
- **Incident log** — rows `52px 116px 1fr 46px`, alternating bg `oklch(0.165 0.016 268)`.
  time · CATEGORY (colored: specificity red, token amber, frontier violet, else `oklch(0.72 0.1 210)`) ·
  truncated prompt · score (mint/amber/red by threshold). Header has a `DELETE ALL HISTORY` button
  (hover → red) that clears history **and** today's count.

#### 4b. Personalities

H1 *"Who's yelling at you today?"* + subhead explaining that the evaluation engine is identical
across personalities and only voice/animation/contempt change; voices are original and streamed via
the ElevenLabs API.

Grid `repeat(auto-fill, minmax(292px, 1fr))`, gap 12. Card: padding 15, radius 12, `surface/3`,
border `border/1`; **active** card gets bg `oklch(0.21 0.03 40)` + border `oklch(0.5 0.1 40)`.
Contents: 34×34 radius-10 gradient swatch with initials → name (600 13.5) + voice line (9.5 mono) →
badge (ACTIVE / INSTALLED / GET IT · 4.9★) → italic sample line → `HEAT` meter of five 17×5 bars
(filled bars use `oklch(0.72 0.17 <60 - 9i>)`). Clicking a card switches persona and closes the window.

| Persona | Initials | Voice | Heat | Sample line |
|---|---|---|---|---|
| Angry Chef | AC | ElevenLabs · Ember (original) | 5 | "This prompt is raw. RAW. Where is the error message?" |
| Disappointed Professor | DP | Slate | 2 | "I'm not angry. I had simply hoped for more by week four." |
| Overly Competitive Coach | OC | Blitz | 4 | "That prompt was a warm-up lap. Give me the real one. GO." |
| Passive-Aggressive Senior | PA | Dry | 3 | "Interesting approach. Ship it. I'll be in the incident channel." |
| Medieval King | MK | Herald | 4 | "Thou hast summoned the machine and told it nothing. Off with it." |
| Deeply Concerned Mother | CM | Warm | 1 | "Sweetheart. It's 2am. You didn't even paste the error again." |

Swatch gradients: AC `135deg oklch(.8 .16 60)→oklch(.62 .2 26)` · DP `oklch(.78 .1 250)→oklch(.6 .14 275)` ·
OC `oklch(.8 .15 140)→oklch(.6 .16 160)` · PA `oklch(.75 .08 210)→oklch(.55 .09 225)` ·
MK `oklch(.8 .13 90)→oklch(.62 .15 65)` · CM `oklch(.82 .1 20)→oklch(.66 .12 350)`.

**Legal:** all personalities must be original characters and original synthesised voices. No
imitation of a real person's voice or likeness.

#### 4c. Settings

Two columns, gap 14.

- **Roast intensity** — five equal buttons: `1 GENTLE`, `2 FIRM`, `3 SHARP`, `4 BRUTAL`, `5 UNHINGED`.
  Selected: bg `oklch(0.28 0.09 40)`, border accent, text `oklch(0.9 0.12 50)`. Note below changes:
  1. "Corrections only. No insults. For when someone is watching your screen."
  2. "Mild disappointment. Suitable for open-plan offices."
  3. "Direct. He will name the mistake and the file it lives in."
  4. "Mild profanity unlocked. He will question your judgement, never your identity."
  5. "Everything above, at volume, with the buzzer. Demo mode."
- **Voice · ElevenLabs** — volume as 10 clickable 20px-tall bars (filled = accent, empty
  `oklch(0.25 0.018 268)`) + `NN%` readout in accent. Three toggles:
  *Stream audio while generating* ("first syllable in ~380ms"), *Cache common roasts*
  ("repeat offences play instantly"), *Fallback to local TTS* ("if the voice API fails mid-demo").
- **Punishment devices** — four rows, each with name, mono meta line, `TEST` button (fires the strip
  animation for 1.2s) and a toggle:
  - Ember Lamp — `hue://desk-1 · severity ≥ 1 · flash red`
  - Desk Buzzer — `usb://buzz0 · severity ≥ 2 · 400ms`
  - Bell-Bot (servo + foam hand) — `ws://bellbot.local · severity 3 · hits the bell, not you`
  - Slack #shame — `webhook · severity ≥ 2 · posts the roast`
- **Webhook payload preview** — live JSON reflecting the last verdict:
  ```json
  { "event": "prompt_violation", "category": "token_conservation", "severity": 3, "message": "token waste" }
  ```

**Toggle spec** (used everywhere): 40×22, radius 999. On → track = accent, border = accent, knob
`oklch(0.16 0.03 40)` at `left: 20px`. Off → track `oklch(0.24 0.018 268)`, border `oklch(0.34 0.02 268)`,
knob `oklch(0.5 0.015 268)` at `left: 2px`. Knob 16×16 circle, `top: 2px`, `transition: left .18s ease`.

#### 4d. Privacy

- **Status banner** — pulsing dot + title/sub + pause button.
  Watching: bg `oklch(0.21 0.04 32)`, border `oklch(0.42 0.08 32)`, title "Gordon is watching Clyde",
  sub "Captures the active window only when you press send. Nothing between.", ghost `Pause monitoring`.
  Paused: `surface/3` + `border/1`, title "Gordon is paused",
  sub "No capture, no scoring, no audio. He'll be here when you're ready to be humbled.",
  gradient `Resume monitoring`.
- **Apps Gordon may watch** — Clyde `ON SUBMIT` (mint) · Terminal `ON SUBMIT` (mint) ·
  Editor `ASK EACH TIME` (amber) · Everything else `NEVER` (`text/faint`).
- **What leaves your machine** — five bullets with 6px square dots (mint, except the storage bullet
  which is amber): screenshots scored in memory and discarded; keys/tokens/passwords redacted before
  leaving the machine; only roast text goes to the voice API, never code; prompt text + score stored
  locally for the dashboard; delete-all is one button.
- **Redaction preview** — padding 15/17, radius 12, bg `oklch(0.19 0.03 32)`, border `oklch(0.36 0.06 32)`,
  mono 11/1.7 in `oklch(0.8 0.02 40)`:
  ```
  POST /v1/orders
  Authorization: Bearer ████████████████ [redacted: api_key]
  user_email: ██████████████ [redacted: pii]
  body: { "cartId": "c_8812", "guest": true }
  ```

### 5. Onboarding (3 steps, blocks the app on first run)

Scrim `oklch(0.09 0.014 268 / 0.9)` + `blur(10px)`. Card max-width 520, radius 18, `gpop 0.35s`.
Header padding 26/26/20 with tint `linear-gradient(180deg, oklch(0.24 0.05 40 / 0.55), transparent)`:
a 28-bar waveform (44px tall, heights `seed[i] * 30`, min 4px, durations `0.5 + (i%4)*0.15`s, delays
`(i%6)*0.07`s), then `STEP n OF 3` (10px mono, `.2em`, accent), H1, body.

Then 2–3 permission rows: 16×16 radius-5 badge (ember gradient for `1`/`2`/`3`/`✓`, grey
`oklch(0.4 0.015 268)` for `—`) + title (12.5/500) + mono sub. Footer: ghost `Skip`/`Back` +
gradient `Continue` / `Let him in`.

| Step | Title | Body | Rows |
|---|---|---|---|
| 1 | Someone has to watch you work. | Gordon reads the prompt you just sent, scores it against six categories, and tells you exactly what you left out. Loudly. | ① He only looks when you hit send / no continuous recording, ever · ② Every insult ships with a fix / roast → diagnosis → lesson → rewritten prompt · ③ One key pauses him / ⌥⇧G, or the button in the menu bar |
| 2 | Choose what he's allowed to see. | Gordon captures the active window only at the moment a prompt is submitted, and only in the apps you tick here. | ✓ Clyde · chat.clyde.dev / browser extension · prompt + model + screenshot · ✓ Terminal / active window only, on submit · — Everything else / invisible to Gordon |
| 3 | Pick your punishment. | Severity 3 fires a physical device. It hits a bell. It does not hit you — that's in the non-goals, in writing. | ✓ Ember Lamp / flashes red on any violation · ✓ Desk Buzzer / severity 2 and above · — Bell-Bot / pair later in Settings → Devices |

---

## Interactions & behavior

### The core loop (prototype timings — tune against the real pipeline)

1. User submits a prompt → append to thread, clear composer, host tool shows a "guessing…" spinner.
2. If **paused**: no scoring. The host tool replies and Gordon stays silent.
3. Otherwise `mode = "thinking"` immediately — waveform jumps to full amplitude, status
   `SCORING YOUR PROMPT…`.
4. After **1100ms** (stand-in for the real evaluation round trip; PRD budget is < 5s):
   - `mode = "verdict"`, card animates in with `gpop`, `speaking = true`.
   - Devices fire for **1600ms** if severity > 0.
   - Counters update: today count +1; tokens-saved += 7400 for a token-dump, else 600.
   - Incident log gets a new row (time, category, first 46 chars of the prompt, score).
5. After **5200ms** `speaking = false` — waveform drops to idle amplitude, status →
   `AWAITING YOUR MOVE`. Card stays until dismissed.

In production, step 4's delay is the actual capture → redact → evaluate → ElevenLabs round trip;
start the waveform the moment audio begins streaming, and drive its amplitude from real audio levels
rather than the canned seed array if the audio pipeline exposes them.

### Other behaviors

- **Use this prompt** — copies the rewritten prompt into the host composer and dismisses the card. (In production this is the "automatic prompt insertion" path via the extension.)
- **COPY** — clipboard write, label flips to `COPIED ✓` for 1600ms.
- **Ignore him / ✕** — dismiss, no state change other than closing.
- **SWAP** — opens the Kitchen on the Personalities tab.
- **Pause** — toggles monitoring globally; changes the menubar pill, the voice chip (`MUTED`), the status line, the idle quip, and the privacy banner.
- **TEST** on a device — fires the strip animation for 1200ms without logging anything.
- **DELETE ALL HISTORY** — clears the incident log and resets today's count to 0; the daily summary switches to its zero-state line.
- **Hover states** — ghost buttons brighten border + text to the accent; persona cards brighten border to `oklch(0.55 0.1 292)`; gradient CTAs use `filter: brightness(1.1)`.
- **Keyboard** (specified in the UI, not yet wired in the prototype): `⌘K` opens the Kitchen, `Esc` closes it, `⌥⇧G` toggles pause. Wire these as global shortcuts in the desktop shell.

### Scoring router (prototype heuristic — replace with the real engine)

Used only so the prototype can demo without a backend:
- matches `/davinci|gpt-3\b|completions endpoint|jquery|python 2|node 12|angular\.?js|claude-1/i` → **outdated**
- more than 90 words → **token dump**
- fewer than 9 words → **vague**
- contains an error/expected/constraint/filename signal and > 24 words → **good**
- otherwise → **vague**

---

## State management

```ts
type Mode = "idle" | "thinking" | "verdict";

interface GordonState {
  // onboarding
  onboardStep: 1 | 2 | 3;
  onboarded: boolean;
  // overlay
  mode: Mode;
  speaking: boolean;          // drives waveform amplitude + status line
  current: Verdict | null;
  copied: boolean;
  firing: boolean;            // device strip flash
  paused: boolean;            // global monitoring switch
  // preferences
  persona: PersonaId;         // "chef" | "prof" | "coach" | "senior" | "king" | "mother"
  intensity: 1|2|3|4|5;
  volume: number;             // 1..10
  devices: { lamp: boolean; buzzer: boolean; bell: boolean; slack: boolean };
  voiceFlags: { stream: boolean; cache: boolean; fallback: boolean };
  // panel
  panelOpen: boolean;
  tab: "dashboard" | "personality" | "settings" | "privacy";
  // analytics
  todayCount: number;
  saved: number;              // tokens
  history: Incident[];
}
```

The verdict object matches the PRD's shared engine response:

```ts
interface Verdict {
  overall_score: number;                       // 0-100
  primary_category: CategoryKey;
  category_scores: Record<CategoryKey, number>;
  roast: string; diagnosis: string; lesson: string; improved_prompt: string;
  severity: 0 | 1 | 2 | 3;
  action: "none" | "smart_light" | "desk_buzzer" | "bell_bot";
  source?: { text: string; date: string; confidence: string; url: string };
}

type CategoryKey =
  | "prompt_specificity" | "token_conservation" | "frontier_awareness"
  | "tool_selection" | "context_management" | "verification";
```

**Category display order is fixed** (radar + card rows): Specificity, Tokens, Frontier, Tool, Context, Verify.

### Data the overlay needs from other services

- **From capture (Person 2)**: normalized event — prompt text, selected model, application, screenshot path, session id, timestamp.
- **From the engine (Person 3)**: the `Verdict` above + an audio stream URL/blob from ElevenLabs. The overlay should begin the speaking animation on the first audio chunk, not on response completion.
- **From the backend (Person 4)**: dashboard aggregates (today count, 14-day averages, per-category counts, incident list, kitchen rating) and the webhook fire-and-forget for device actions.

The prototype hardcodes four verdicts (in `Gordon.dc.html`, `scenarios` in the logic class) — use them
as realistic fixtures for the overlay before the engine is live, and as copy examples for the roast
prompt templates.

---

## Content rules (carry these into implementation)

- Every roast **must** be paired with a diagnosis, a lesson and a rewritten prompt. Never ship the insult alone.
- Insult the technical decision, never the person's identity. No race, gender, disability, appearance, religion, nationality, sexuality or mental-health material at any intensity.
- Profanity unlocks at intensity 4 and stays mild ("damn", "hell").
- Never invent statistics. Frontier claims render only with a source and a date, and the source button must open the real release note.
- Token-savings figures are labelled as estimates ("est. from shortened prompts").

## Assets

None. No image files, no icon set, no illustrations. Everything is CSS/SVG geometry (hexagon radar,
polyline chart, bar waveform, toggles) or a text glyph (`✓ — ↵ ↗ ✕ ★ █`). The only external
dependency is the two Google Fonts. If the target codebase has an icon library, the glyphs may be
swapped for icons — the waveform, radar and chart should stay as drawn geometry.

## Files

- `Gordon.dc.html` — the full interactive prototype (all screens, all states). Open in a browser.
- `support.js` — runtime required by the prototype. Not part of the design; do not port it.

Inside `Gordon.dc.html`, the markup is the template and the logic lives in the `class Component`
script at the bottom: `scenarios` (the four fixture verdicts + all roast copy), `personas`,
`presetText` (demo prompts), and `renderVals()` (every computed color, width and label described above).
