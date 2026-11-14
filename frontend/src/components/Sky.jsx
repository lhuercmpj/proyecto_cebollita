// Numeros pseudo-aleatorios deterministas: la escena siempre se ve igual al cargar.
const rand = (i, n) => ((Math.sin(i * 12.9898 + n * 78.233) * 43758.5453) % 1 + 1) % 1;

const STARS = Array.from({ length: 46 }, (_, i) => ({
  left: `${rand(i, 1) * 100}%`,
  top: `${rand(i, 2) * 70}%`,
  size: 1 + rand(i, 3) * 2.2,
  delay: `${rand(i, 4) * 5}s`,
  duration: `${2.5 + rand(i, 5) * 3}s`,
}));

// Particulas flotantes: cada una recibe su posicion y tiempos como variables CSS.
const particles = (count, seed, extra = () => ({})) =>
  Array.from({ length: count }, (_, i) => ({
    "--x": `${rand(i, seed) * 100}%`,
    "--y": `${15 + rand(i, seed + 1) * 80}%`,
    "--s": `${3 + rand(i, seed + 2) * 5}px`,
    "--d": `${14 + rand(i, seed + 3) * 18}s`,
    "--delay": `${-rand(i, seed + 4) * 30}s`,
    "--dx": `${(rand(i, seed + 5) - 0.5) * 120}px`,
    "--dy": `${(rand(i, seed + 6) - 0.5) * 110}px`,
    ...extra(i),
  }));

const POLLEN = particles(16, 10);
const MOTES = particles(18, 30);
const FIREFLIES = particles(16, 50);
const PETALS = particles(5, 70, (i) => ({ "--y": "-6%", "--s": `${10 + rand(i, 8) * 8}px`, "--d": `${26 + rand(i, 9) * 18}s` }));

const BUTTERFLIES = [
  { top: "18%", color: "#f4a6c1", d: "58s", delay: "-8s", size: 26 },
  { top: "42%", color: "#f7d56b", d: "74s", delay: "-40s", size: 22 },
  { top: "64%", color: "#9ec7f2", d: "66s", delay: "-22s", size: 20 },
];

function Butterfly({ top, color, d, delay, size }) {
  return (
    <div className="butterfly" style={{ top, "--d": d, "--delay": delay }}>
      <svg viewBox="0 0 24 20" width={size} height={size * 0.83} style={{ fill: color }}>
        <g className="wing wing--l"><path d="M12 10C8 1 0 2 1.5 8c1 4 7 5.5 10.5 2z" /></g>
        <g className="wing wing--r"><path d="M12 10c4-9 12-8 10.500-2-1 4-7 5.500-10.500 2z" /></g>
        <rect x="11.2" y="5" width="1.6" height="10" rx=".8" style={{ fill: "#5a4a3a" }} />
      </svg>
    </div>
  );
}

const Dots = ({ items, className }) =>
  items.map((style, i) => <span key={i} className={`particle ${className}`} style={style} />);

/** Fondo: los tres cielos estan siempre montados y se funden segun el tema. */
export default function Sky() {
  return (
    <div className="sky" aria-hidden="true">
      <div className="sky__layer sky__morning">
        <div className="sun sun--morning" />
        <span className="cloud cloud--a" /><span className="cloud cloud--b" /><span className="cloud cloud--c" />
        <Dots items={POLLEN} className="pollen" />
        {BUTTERFLIES.map((b) => <Butterfly key={b.top} {...b} />)}
      </div>

      <div className="sky__layer sky__afternoon">
        <div className="sun sun--afternoon" />
        <span className="cloud cloud--a" /><span className="cloud cloud--b" /><span className="cloud cloud--c" />
        <Dots items={MOTES} className="mote" />
        <Dots items={PETALS} className="petal" />
      </div>

      <div className="sky__layer sky__night">
        {STARS.map((s, i) => (
          <span
            key={i}
            className="star"
            style={{ left: s.left, top: s.top, width: s.size, height: s.size, animationDelay: s.delay, animationDuration: s.duration }}
          />
        ))}
        <div className="moon" />
        <Dots items={FIREFLIES} className="firefly" />
      </div>
    </div>
  );
}
