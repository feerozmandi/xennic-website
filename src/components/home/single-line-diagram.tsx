/**
 * The living single-line diagram.
 *
 * A schematic of one Xennic energy path — the sun on a roof, the 20 kV
 * distribution board it feeds, the industrial panel below, and the analytics
 * that read the meters — drawn as SVG instead of a stock photograph, so every
 * line is a claim about the system and not decoration.
 *
 * The drawing (it is also its accessible label):
 *
 * - **20 kV distribution** enters at the top and passes a breaker.
 * - **Transformer** 20 kV / 400 V steps it down.
 * - **Industrial panel** at 400 V is where the work happens.
 * - **Solar array → inverter** feeds that panel from the same side as the
 *   capacitor bank that compensates it.
 * - **Analysis layer** above, on a measurement tap, because the platform reads
 *   rather than switches: it never sits in the power path.
 *
 * Every label lives inside its own bordered tag, so the text can never collide
 * with a wire whatever the language or the width. Motion is one CSS animation
 * on `stroke-dashoffset`: a dash of light travels each energized path in the
 * direction energy flows, gold for the solar side and cyan for the grid side.
 * It stops completely under `prefers-reduced-motion`, leaving the same drawing
 * at rest.
 *
 * Static, inline, no JavaScript, and it scales with its container through
 * `viewBox` + `preserveAspectRatio`.
 */
import { getDictionary, type Locale } from '@/lib/i18n'

type Box = { x: number; y: number; w: number; h: number }

/* Tag geometry, in the viewBox's own units. The trunk runs down the middle
 * third and the three feeders sit on one shelf at the foot, so no wire ever
 * crosses a label whatever the language. */
const TAG = {
  analytics: { x: 150, y: 10, w: 300, h: 46 } as Box,
  grid: { x: 170, y: 96, w: 260, h: 50 } as Box,
  transformer: { x: 185, y: 172, w: 230, h: 50 } as Box,
  panel: { x: 160, y: 248, w: 300, h: 54 } as Box,
  array: { x: 20, y: 344, w: 180, h: 54 } as Box,
  inverter: { x: 224, y: 344, w: 150, h: 54 } as Box,
  capacitor: { x: 398, y: 344, w: 192, h: 54 } as Box,
}

const centerX = (b: Box) => b.x + b.w / 2
const centerY = (b: Box) => b.y + b.h / 2

/* One AC bus under the panel carries the inverter, the panel and the capacitor
 * bank; the array reaches the inverter on its own DC feeder. These are named so
 * a wire can never point at a tag edge by arithmetic that has since moved. */
const BUS_Y = 322
const AC_BUS = { from: centerX(TAG.inverter), to: centerX(TAG.capacitor) }
const PANEL_BOTTOM = TAG.panel.y + TAG.panel.h
const TAGS_TOP = TAG.array.y
const PANEL_OUT = centerX(TAG.panel)

export function SingleLineDiagram({ locale = 'fa' }: { locale?: Locale }) {
  const dict = getDictionary(locale)
  const t = dict.hero.diagram

  return (
    <figure className="sld">
      <svg className="sld__canvas" viewBox="0 0 610 412" role="img" aria-label={t.alt} preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="sld-gold" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--gold)" />
            <stop offset="100%" stopColor="var(--gold-2)" stopOpacity="0.55" />
          </linearGradient>
          <linearGradient id="sld-cyan" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--teal)" />
            <stop offset="100%" stopColor="var(--teal)" stopOpacity="0.45" />
          </linearGradient>
          <radialGradient id="sld-sun" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--gold-2)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--gold)" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Graph paper, faint: the drawing sits on a surface, not in air. */}
        <g className="sld__grid" aria-hidden="true">
          {Array.from({ length: 10 }, (_, i) => (
            <line key={`v${i}`} x1={18 + i * 64} y1="4" x2={18 + i * 64} y2="408" />
          ))}
          {Array.from({ length: 7 }, (_, i) => (
            <line key={`h${i}`} x1="4" y1={18 + i * 62} x2="606" y2={18 + i * 62} />
          ))}
        </g>

        {/* Connectors first, so every tag paints over its own wire ends. */}
        <g aria-hidden="true">
          {/* The trunk: 20 kV in, step down, 400 V panel. */}
          <path className="sld__rail" d={`M${centerX(TAG.grid)} ${TAG.grid.y + TAG.grid.h} V${TAG.transformer.y}`} />
          <path className="sld__flow sld__flow--cyan" d={`M${centerX(TAG.grid)} ${TAG.grid.y + TAG.grid.h} V${TAG.transformer.y}`} />
          <path className="sld__rail" d={`M${centerX(TAG.transformer)} ${TAG.transformer.y + TAG.transformer.h} V${TAG.panel.y}`} />
          <path className="sld__flow sld__flow--cyan" d={`M${centerX(TAG.transformer)} ${TAG.transformer.y + TAG.transformer.h} V${TAG.panel.y}`} />

          {/* The AC bus and its three drops: panel above, inverter and capacitor below. */}
          <path className="sld__rail" d={`M${AC_BUS.from} ${BUS_Y} H${AC_BUS.to}`} />
          <path className="sld__flow sld__flow--cyan" d={`M${AC_BUS.from} ${BUS_Y} H${AC_BUS.to}`} />
          <path className="sld__rail" d={`M${PANEL_OUT} ${PANEL_BOTTOM} V${BUS_Y}`} />
          <path className="sld__rail" d={`M${AC_BUS.from} ${BUS_Y} V${TAGS_TOP}`} />
          <path className="sld__rail" d={`M${AC_BUS.to} ${BUS_Y} V${TAGS_TOP}`} />

          {/* DC: the array feeds the inverter on its own feeder. */}
          <path className="sld__rail" d={`M${TAG.array.x + TAG.array.w} ${centerY(TAG.array)} H${TAG.inverter.x}`} />
          <path className="sld__flow sld__flow--gold" d={`M${TAG.array.x + TAG.array.w} ${centerY(TAG.array)} H${TAG.inverter.x}`} />

          {/* Metering: the analysis layer reads the transformer, it never switches it. */}
          <path className="sld__rail sld__rail--thin" d={`M${TAG.transformer.x + TAG.transformer.w} ${centerY(TAG.transformer)} H560 V${centerY(TAG.analytics)} H450`} />
          <path className="sld__flow sld__flow--gold sld__flow--thin" d={`M${TAG.transformer.x + TAG.transformer.w} ${centerY(TAG.transformer)} H560 V${centerY(TAG.analytics)} H450`} />

          {/* Sunlight, as a dotted ray onto the array. */}
          <path className="sld__ray" d={`M74 152 V${TAG.array.y - 8}`} />
        </g>

        {/* The sun, drawn rather than typed: a disc with eight rays. */}
        <g className="sld__sun-group" aria-hidden="true">
          <circle className="sld__sun-glow" cx="74" cy="112" r="38" />
          <circle className="sld__sun-core" cx="74" cy="112" r="15" />
          {Array.from({ length: 8 }, (_, i) => {
            const angle = (i * Math.PI) / 4
            const inner = 22
            const outer = 30
            return (
              <line
                key={i}
                className="sld__ray-line"
                x1={74 + Math.cos(angle) * inner}
                y1={112 + Math.sin(angle) * inner}
                x2={74 + Math.cos(angle) * outer}
                y2={112 + Math.sin(angle) * outer}
              />
            )
          })}
        </g>

        {/* Analysis layer: a tag with a drawn sparkline, not a number we cannot cite. */}
        <g className="sld__tag sld__tag--accent" aria-hidden="true">
          <rect x={TAG.analytics.x} y={TAG.analytics.y} width={TAG.analytics.w} height={TAG.analytics.h} rx="12" />
        </g>
        <text className="sld__label" x={centerX(TAG.analytics) - 30} y={centerY(TAG.analytics) + 5} textAnchor="middle">
          {t.analytics}
        </text>
        <g className="sld__bars" aria-hidden="true">
          <rect x={TAG.analytics.x + TAG.analytics.w - 62} y={centerY(TAG.analytics) - 6} width="7" height="20" rx="2" />
          <rect x={TAG.analytics.x + TAG.analytics.w - 50} y={centerY(TAG.analytics) - 14} width="7" height="28" rx="2" />
          <rect x={TAG.analytics.x + TAG.analytics.w - 38} y={centerY(TAG.analytics) - 2} width="7" height="16" rx="2" />
        </g>

        {/* 20 kV distribution: the incoming bus, with a breaker on it. */}
        <g className="sld__tag" aria-hidden="true">
          <rect x={TAG.grid.x} y={TAG.grid.y} width={TAG.grid.w} height={TAG.grid.h} rx="12" />
          <line className="sld__bus" x1={TAG.grid.x + 16} y1={TAG.grid.y + 12} x2={TAG.grid.x + 60} y2={TAG.grid.y + 12} />
          <line className="sld__bus" x1={TAG.grid.x + TAG.grid.w - 60} y1={TAG.grid.y + 12} x2={TAG.grid.x + TAG.grid.w - 16} y2={TAG.grid.y + 12} />
          <circle className="sld__dot" cx={TAG.grid.x + 38} cy={TAG.grid.y + 12} r="3" />
          <circle className="sld__dot" cx={TAG.grid.x + TAG.grid.w - 38} cy={TAG.grid.y + 12} r="3" />
        </g>
        <text className="sld__label" x={centerX(TAG.grid)} y={centerY(TAG.grid) + 14} textAnchor="middle">
          {t.grid}
        </text>

        {/* Transformer: two coupled coils beside the name. */}
        <g className="sld__tag" aria-hidden="true">
          <rect x={TAG.transformer.x} y={TAG.transformer.y} width={TAG.transformer.w} height={TAG.transformer.h} rx="12" />
          <circle className="sld__coil" cx={TAG.transformer.x + 34} cy={centerY(TAG.transformer) - 9} r="9" />
          <circle className="sld__coil" cx={TAG.transformer.x + 34} cy={centerY(TAG.transformer) + 9} r="9" />
        </g>
        <text className="sld__label sld__label--small" x={centerX(TAG.transformer) + 26} y={centerY(TAG.transformer) + 5} textAnchor="middle">
          {t.transformer}
        </text>

        {/* The industrial panel: three outgoing ways, drawn as breaker slots. */}
        <g className="sld__tag" aria-hidden="true">
          <rect x={TAG.panel.x} y={TAG.panel.y} width={TAG.panel.w} height={TAG.panel.h} rx="12" />
          {[0, 1, 2].map((i) => (
            <rect key={i} className="sld__way" x={TAG.panel.x + 20 + i * 16} y={TAG.panel.y + 18} width="9" height="20" rx="2" />
          ))}
        </g>
        <text className="sld__label" x={centerX(TAG.panel) + 34} y={centerY(TAG.panel) + 5} textAnchor="middle">
          {t.panel}
        </text>

        {/* Solar array: a module grid. */}
        <g className="sld__tag" aria-hidden="true">
          <rect x={TAG.array.x} y={TAG.array.y} width={TAG.array.w} height={TAG.array.h} rx="12" />
          <g className="sld__module">
            <rect x={TAG.array.x + 16} y={TAG.array.y + 16} width="44" height="24" rx="3" />
            <line x1={TAG.array.x + 31} y1={TAG.array.y + 16} x2={TAG.array.x + 31} y2={TAG.array.y + 40} />
            <line x1={TAG.array.x + 16} y1={TAG.array.y + 28} x2={TAG.array.x + 60} y2={TAG.array.y + 28} />
          </g>
        </g>
        <text className="sld__label sld__label--small" x={TAG.array.x + 118} y={centerY(TAG.array) + 5} textAnchor="middle">
          {t.array}
        </text>

        {/* Inverter + combiner: the DC/AC boundary. */}
        <g className="sld__tag" aria-hidden="true">
          <rect x={TAG.inverter.x} y={TAG.inverter.y} width={TAG.inverter.w} height={TAG.inverter.h} rx="12" />
          <path className="sld__wave" d={`M${TAG.inverter.x + 12} ${centerY(TAG.inverter) + 12} q7 -10 14 0 t14 0`} />
        </g>
        <text className="sld__label sld__label--small" x={TAG.inverter.x + TAG.inverter.w - 48} y={centerY(TAG.inverter) + 1} textAnchor="middle">
          {t.inverter}
        </text>
        <text className="sld__unit" x={TAG.inverter.x + TAG.inverter.w - 48} y={centerY(TAG.inverter) + 16} textAnchor="middle">
          {t.unitInverter}
        </text>

        {/* Capacitor bank: the plates are the symbol. */}
        <g className="sld__tag" aria-hidden="true">
          <rect x={TAG.capacitor.x} y={TAG.capacitor.y} width={TAG.capacitor.w} height={TAG.capacitor.h} rx="12" />
          <line className="sld__plate" x1={TAG.capacitor.x + 22} y1={centerY(TAG.capacitor) - 7} x2={TAG.capacitor.x + 46} y2={centerY(TAG.capacitor) - 7} />
          <line className="sld__plate" x1={TAG.capacitor.x + 22} y1={centerY(TAG.capacitor) + 5} x2={TAG.capacitor.x + 46} y2={centerY(TAG.capacitor) + 5} />
        </g>
        <text className="sld__label sld__label--small" x={TAG.capacitor.x + 116} y={centerY(TAG.capacitor) + 1} textAnchor="middle">
          {t.capacitor}
        </text>
        <text className="sld__unit" x={TAG.capacitor.x + 116} y={centerY(TAG.capacitor) + 16} textAnchor="middle">
          {t.unitCap}
        </text>
      </svg>

      <figcaption className="sld__caption">{t.caption}</figcaption>
    </figure>
  )
}
