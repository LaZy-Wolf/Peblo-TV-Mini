/**
 * The hand-drawn layer, shared with the viewer so the two surfaces read as
 * one product.
 *
 * In the CMS this appears on the sign-in panel only. Past the front door an
 * editor is working, and a drifting doodle behind a table of ninety-four
 * episodes would be something to look past fifty times a week.
 */

type Mark = {
  d: string;
  stroke: string;
  top: string;
  left?: string;
  right?: string;
  size: number;
  delay: number;
  fill?: string;
};

const CURL = "M2 22c8-2 4-18 12-19s7 14 15 13";
const CLOUD = "M4 20c-6 0-4-9 3-8 1-7 12-8 14-1 7-1 9 9 2 9z";
const SPARK = "M12 1l2.6 7.4L22 11l-7.4 2.6L12 21l-2.6-7.4L2 11l7.4-2.6z";
const STAR = "M12 2l2.9 6.5 7.1.7-5.3 4.8 1.5 7-6.2-3.6L5.8 21l1.5-7L2 9.2l7.1-.7z";
const SUN = "M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10M12 1v2M12 21v2M3 12H1M23 12h-2M5 5L3.6 3.6M20.4 20.4L19 19M5 19l-1.4 1.4M20.4 3.6L19 5";
const ZIG = "M2 16l5-6 5 6 5-6 5 6";
const LOOP = "M3 18c0-8 7-12 10-8s-4 10-7 6 3-12 11-9";

/* Placement rule: the outer margins and corners only. A doodle that lands
   on the headline or the paragraph stops being charm and becomes noise, so
   none of these sit inside the copy block. */
const MARKS: Mark[] = [
  { d: CURL, stroke: "var(--violet)", top: "4%", left: "0.4%", size: 44, delay: 0 },
  { d: CLOUD, stroke: "var(--violet)", top: "84%", left: "0.4%", size: 42, delay: 900 },
  { d: STAR, stroke: "none", fill: "var(--pink)", top: "93%", left: "7%", size: 17, delay: 1500 },
  { d: SUN, stroke: "var(--amber)", top: "5%", right: "2%", size: 44, delay: 600 },
  { d: LOOP, stroke: "var(--pink)", top: "80%", right: "2%", size: 52, delay: 1200 },
  { d: ZIG, stroke: "var(--teal)", top: "46%", right: "0.5%", size: 38, delay: 300 },
  { d: SPARK, stroke: "none", fill: "var(--amber)", top: "30%", right: "1%", size: 22, delay: 400 },
  { d: SPARK, stroke: "none", fill: "var(--violet)", top: "26%", left: "0.3%", size: 15, delay: 1800 },
];

export function Doodles() {
  return (
    <div className="doodles" aria-hidden="true">
      {MARKS.map((m, i) => (
        <svg
          key={i}
          className="doodle"
          viewBox="0 0 24 24"
          width={m.size}
          height={m.size}
          fill={m.fill ?? "none"}
          stroke={m.stroke}
          strokeWidth={m.stroke === "none" ? 0 : 2}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            top: m.top,
            left: m.left,
            right: m.right,
            animationDelay: `${m.delay}ms`,
          }}
        >
          <path d={m.d} />
        </svg>
      ))}
    </div>
  );
}
