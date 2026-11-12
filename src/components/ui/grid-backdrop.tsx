/**
 * Single-line diagram in the page background.
 *
 * A substation drawing reduced to its geometry: two buses, incoming feeders,
 * breakers, a transformer and outgoing distribution feeders. It is decorative
 * only (`aria-hidden`), fixed behind the page, and it never carries meaning the
 * reader would lose without it.
 *
 * The moving energy is a dashed stroke whose offset animates along the paths.
 * Dark theme gets glowing light on dark steel; the light theme keeps the same
 * drawing as faint copper lines and does not animate them, so daylight pages
 * stay calm. Both stop entirely under `prefers-reduced-motion: reduce`.
 */
const FEEDERS = [
  'M-20 118 H320 L392 190',
  'M-20 262 H320 L392 334',
  'M1620 150 H1300 L1228 222',
  'M1620 300 H1300 L1228 372',
]

const OUTGOING = [
  'M392 262 V360 L300 440 V560',
  'M392 262 V360 L484 440 V560',
  'M1228 262 V360 L1136 440 V560',
  'M1228 262 V360 L1320 440 V560',
  'M1620 430 H1400 L1320 510',
  'M-20 430 H200 L300 510',
]

export function GridBackdrop() {
  return (
    <div className="grid-backdrop" aria-hidden="true">
      <svg className="grid-backdrop__svg" viewBox="0 0 1600 800" preserveAspectRatio="xMidYMid slice" focusable="false">
        <g className="grid-backdrop__lines">
          {/* Buses */}
          <path d="M392 190 H1228" className="grid-backdrop__bus" />
          <path d="M392 334 H1228" className="grid-backdrop__bus" />
          {/* Incoming feeders */}
          {FEEDERS.map((d) => <path key={d} d={d} className="grid-backdrop__line" />)}
          {/* Outgoing distribution feeders */}
          {OUTGOING.map((d) => <path key={d} d={d} className="grid-backdrop__line" />)}
          {/* Breaker squares on the buses */}
          {[520, 690, 860, 1030].map((x) => (
            <rect key={x} x={x - 9} y={253} width={18} height={18} rx={3} className="grid-backdrop__switch" />
          ))}
          {/* Power transformer between the buses */}
          <circle cx="776" cy="253" r="17" className="grid-backdrop__coil" />
          <circle cx="812" cy="253" r="17" className="grid-backdrop__coil" />
          <path d="M790 190 V236 M798 270 V334" className="grid-backdrop__line" />
          {/* Instrument taps: voltage and current sensing */}
          <path d="M560 334 V392 H640" className="grid-backdrop__line grid-backdrop__line--thin" />
          <circle cx="648" cy="392" r="8" className="grid-backdrop__coil" />
          <path d="M690 190 V142 H770" className="grid-backdrop__line grid-backdrop__line--thin" />
          <circle cx="778" cy="142" r="8" className="grid-backdrop__coil" />
        </g>

        {/* The same geometry again, as short dashes that travel along it. */}
        <g className="grid-backdrop__flow">
          {[...FEEDERS, ...OUTGOING].map((d) => <path key={d} d={d} className="grid-backdrop__pulse" />)}
        </g>
      </svg>
    </div>
  )
}
