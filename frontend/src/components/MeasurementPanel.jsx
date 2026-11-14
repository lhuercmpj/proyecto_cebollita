import { PLANT_STATES, formatAge, formatNumber, readings } from "../utils/measurements.js";

/** Tarjetas de vidrio con las ultimas lecturas de los sensores. */
export default function MeasurementPanel({ status, measurement, ageMinutes, stale }) {
  if (!measurement) {
    const text =
      status === "loading" ? "Leyendo mis sensores…"
      : status === "error" ? "No pude conectarme con el servidor."
      : "Todavía no hay mediciones.";
    return <section className="panel glass panel--empty" aria-label="Mediciones">{text}</section>;
  }

  const prediction = measurement.prediction;
  const state = PLANT_STATES[prediction.state];

  return (
    <section className="panel glass" aria-label="Últimas mediciones">
      <div className="panel__grid">
        {readings(measurement).map((r) => (
          <div key={r.id} className="metric" title={r.hint}>
            <div className="metric__label">
              <span aria-hidden="true">{r.icon}</span> {r.label}
            </div>
            <div className="metric__value">
              {formatNumber(r.value, r.digits)}
              {r.unit && <span className="metric__unit">{r.unit}</span>}
              {r.raw && <span className="metric__tag">crudo</span>}
            </div>
            {r.fill !== undefined && (
              <div className="metric__bar" aria-hidden="true">
                <span style={{ width: `${Math.round(Math.min(1, Math.max(0, r.fill)) * 100)}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="panel__foot">
        <span className={`panel__state panel__state--${state?.key ?? "bien"}`}>
          {prediction.state} · {formatNumber(prediction.confidence * 100)} %
        </span>
        <span className={`panel__age${stale ? " panel__age--stale" : ""}`}>
          {stale && "⚠️ "}
          {formatAge(ageMinutes)}
        </span>
      </div>
    </section>
  );
}
