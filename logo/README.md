# Gordon logo — option 1c (toque)

Chef's toque built from three circles + two rectangles, with the overlay's voice
waveform cut into the band. All geometry is on a `0 0 120 120` grid. No fonts, no
gradients, no external assets — every file is hand-editable SVG.

## Files

| File | Use |
|---|---|
| `gordon-mark.svg` | Primary mark, full colour, transparent bg. 120×120 with padding. |
| `gordon-mark-tight.svg` | Same mark cropped to its bounding box (82×79). Use inline next to text or in a tray where you control padding yourself. |
| `gordon-mark-mono.svg` | Single-colour silhouette using `currentColor`, bars knocked out. Inherits text colour — best for menu bars, disabled states, print, embroidery. |
| `gordon-icon.svg` | App icon: ember tile, hat knocked out in dark ink. Corner radius 27/120 (matches macOS squircle proportion closely enough; regenerate with a real squircle mask if you need Apple-exact). |
| `gordon-icon-dark.svg` | App icon on the product's dark surface, for docks/launchers where the ember tile is too loud. |
| `gordon-lockup.svg` | Horizontal lockup: mark + `GORDON` wordmark. **The wordmark is live text in IBM Plex Mono 700, letter-spacing 6.1.** Outline it (`Path > Object to Path`) before shipping anywhere the font isn't guaranteed. |

## Geometry (viewBox 0 0 120 120)

```
crown puffs   circle(38, 42, r19)  circle(60, 33, r22)  circle(82, 42, r19)
crown body    rect(30, 46, 60×26)
band          rect(28, 70, 64×20, r6)
waveform      rect(36, 76, 5×8,   r2.5)
              rect(46, 73, 5×14,  r2.5)
              rect(56, 70.5, 5×19, r2.5)
              rect(66, 74, 5×12,  r2.5)
              rect(76, 77, 5×6,   r2.5)
bounding box  x 19–101, y 11–90   (82 × 79)
```

Bar heights follow the same rhythm as the live waveform in the overlay UI, so the
logo and the character animation stay visually related.

## Colour

| Role | Hex | oklch (source of truth in the product) |
|---|---|---|
| Crown | `#EDEEF2` | `oklch(0.93 0.008 268)` |
| Band (ember accent) | `#EB8B3E` | `oklch(0.78 0.16 46)` |
| Bars / ink | `#15161C` | `oklch(0.15 0.02 268)` |
| Icon tile ink | `#2A1409` | `oklch(0.2 0.05 45)` |
| Icon bars on ember | `#F0A65C` | `oklch(0.84 0.13 58)` |
| Dark tile | `#12131A` | `oklch(0.165 0.016 268)` |

The product UI authors colour in oklch; the hex values above are sRGB fallbacks.
The band colour tracks the app's accent token — if the accent is themed (the
prototype ships ember / magenta / mint / violet presets), theme the band with it
and leave the crown and bars fixed.

## Usage rules

- **Minimum size**: 20px for the full-colour mark, 16px for `gordon-mark-mono.svg`.
  Below 20px the waveform bars fill in — use the mono file, which is designed to
  hold up when the bars close.
- **Clear space**: one band-height (20 units / ~17% of the mark's width) on all sides.
- **Don't**: rotate it, add a drop shadow, outline the crown, recolour the crown to
  the accent, or squash the aspect ratio. The crown must stay lighter than the band.
- **On light backgrounds**: the white crown disappears. Use `gordon-mark-mono.svg`
  with `color: #15161C`, or `gordon-icon.svg`.

## Favicon / app icon generation

```sh
# PNGs
for s in 16 32 48 128 256 512 1024; do
  rsvg-convert -w $s -h $s gordon-icon.svg -o gordon-icon-$s.png
done
# or: npx sharp-cli -i gordon-icon.svg -o gordon-icon-512.png resize 512 512
```

At 16 and 32px, swap in `gordon-mark-mono.svg` rather than downscaling the tile —
the knocked-out bars survive better than the ember tile's contrast does.

## React component (drop-in)

```tsx
export function GordonMark({ size = 24, ...props }: { size?: number } & React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="19 11 82 79" width={size} height={size * (79 / 82)} aria-label="Gordon" {...props}>
      <circle cx="38" cy="42" r="19" fill="#EDEEF2" />
      <circle cx="60" cy="33" r="22" fill="#EDEEF2" />
      <circle cx="82" cy="42" r="19" fill="#EDEEF2" />
      <rect x="30" y="46" width="60" height="26" fill="#EDEEF2" />
      <rect x="28" y="70" width="64" height="20" rx="6" fill="#EB8B3E" />
      <g fill="#15161C">
        <rect x="36" y="76" width="5" height="8" rx="2.5" />
        <rect x="46" y="73" width="5" height="14" rx="2.5" />
        <rect x="56" y="70.5" width="5" height="19" rx="2.5" />
        <rect x="66" y="74" width="5" height="12" rx="2.5" />
        <rect x="76" y="77" width="5" height="6" rx="2.5" />
      </g>
    </svg>
  );
}
```

## Wordmark

`IBM Plex Mono` 700, uppercase, letter-spacing `0.18em`, set in `#EDEEF2` on dark or
`#15161C` on light. Cap height of the wordmark should equal the height of the logo's
band + waveform block (20 units) when they sit side by side; the lockup file already
uses that relationship.
