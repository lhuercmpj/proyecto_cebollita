import { PLANT_STATES, formatAge, formatNumber, minutesSince, readings, STALE_MINUTES } from "../utils/measurements.js";

/** Tarjeta compacta con las lecturas, para mostrar dentro del chat. */
export default function MiniReadings({ measurement }) {
  const age = minutesSince(measurement.measured_at);
  const state = PLANT_STATES[measurement.prediction.state];
  return (
    <div className="mini">
      <div className="mini__title">
        {state?.icon} {measurement.prediction.state}
        <span className="mini__conf"> · {formatNumber(measurement.prediction.confidence * 100)} %</span>
      </div>
      <ul className="mini__list">
        {readings(measurement).map((r) => (
          <li key={r.id} title={r.hint}>
            <span>{r.icon} {r.label}</span>
            <strong>
              {formatNumber(r.value, r.digits)}
              {r.unit && ` ${r.unit}`}
              {r.raw && <em> crudo</em>}
            </strong>
          </li>
        ))}
      </ul>
      <div className="mini__age">
        {age > STALE_MINUTES && "⚠️ Lectura atrasada · "}
        {formatAge(age)}
      </div>
    </div>
  );
}
