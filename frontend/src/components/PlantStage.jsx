import bien from "../assets/plant/bien.webp";
import luz from "../assets/plant/luz.webp";
import agua from "../assets/plant/agua.webp";
import mal from "../assets/plant/mal.webp";
import { PLANT_STATES } from "../utils/measurements.js";

const IMAGES = { bien, luz, agua, mal };

const DESCRIPTIONS = {
  bien: "Cebollita está bien",
  luz: "Cebollita necesita más luz",
  agua: "Cebollita tiene sed",
  mal: "Cebollita no se siente bien",
};

function bubbleFor({ status, measurement, stale }) {
  if (measurement) {
    const info = PLANT_STATES[measurement.prediction.state];
    if (info) return { ...info, note: stale ? "lectura atrasada" : null };
  }
  if (status === "error") return { icon: "📡", text: "No me llegan datos", note: null };
  if (status === "empty") return { icon: "⏳", text: "Esperando mis datos…", note: null };
  return null;
}

/** La planta cambia de aspecto segun el estado que estima el modelo. */
export default function PlantStage({ status, measurement, stale }) {
  const state = measurement ? PLANT_STATES[measurement.prediction.state] : null;
  // Mientras se consulta el estado no se muestra ninguna variante (evita un "bien" falso al cargar).
  const active = status === "loading" ? null : state?.key ?? "bien";
  const bubble = bubbleFor({ status, measurement, stale });

  return (
    <div className={`plantstage plantstage--${active ?? "loading"}${stale ? " plantstage--stale" : ""}`}>
      {bubble && (
        <div className="thought" role="status">
          <span className="thought__icon" aria-hidden="true">{bubble.icon}</span>
          <span>
            {bubble.text}
            {bubble.note && <small className="thought__note">⚠️ {bubble.note}</small>}
          </span>
        </div>
      )}
      <div className="plantstage__stage">
        {/* Sombra del suelo: silueta de la planta aplastada; su direccion y color dependen de la hora (extras.css). */}
        <div className="plantstage__cast" aria-hidden="true">
          {Object.entries(IMAGES).map(([key, src]) => (
            <span
              key={key}
              className={`plantstage__castimg${key === active ? " is-active" : ""}`}
              style={{ WebkitMaskImage: `url(${src})`, maskImage: `url(${src})` }}
            />
          ))}
        </div>
        <span className="plantstage__contact" aria-hidden="true" />
        <div className="plantstage__sway">
          {Object.entries(IMAGES).map(([key, src]) => (
            <img
              key={key}
              src={src}
              alt={key === active ? DESCRIPTIONS[key] : ""}
              aria-hidden={key !== active}
              className={`plantstage__img${key === active ? " is-active" : ""}`}
              draggable="false"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
