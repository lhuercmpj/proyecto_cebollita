// Una lectura se considera atrasada pasados 30 min de intervalo + 10 de margen
// (igual que REPORT_INTERVAL_MINUTES + STALE_MARGIN_MINUTES del backend).
export const STALE_MINUTES = 40;

// Estados que estima el modelo -> variante de la planta y mensaje.
export const PLANT_STATES = {
  "Estoy bien": { key: "bien", icon: "✨", text: "Todo bien por acá" },
  "Preciso luz": { key: "luz", icon: "☀️", text: "Quiero más luz" },
  "Preciso agua": { key: "agua", icon: "💧", text: "¡Tengo sed!" },
  "Estoy mal": { key: "mal", icon: "🥀", text: "No me siento bien" },
};

/** El backend puede devolver fechas sin zona horaria: se interpretan como UTC. */
export function parseDate(value) {
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function minutesSince(value, now = Date.now()) {
  return Math.max(0, Math.floor((now - parseDate(value).getTime()) / 60000));
}

export function formatAge(minutes) {
  if (minutes < 1) return "hace un momento";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `hace ${hours} h ${rest} min` : `hace ${hours} h`;
}

export function formatNumber(value, digits = 0) {
  return Number(value).toLocaleString("es", { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

/**
 * Lecturas listas para mostrar. La humedad de la tierra y la luz son valores crudos
 * del sensor (0-4095, sin calibrar): se muestran tal cual, nunca como porcentaje.
 */
export function readings(measurement) {
  const s = measurement.sensors;
  return [
    { id: "temp", icon: "🌡️", label: "Temperatura", value: measurement.temp_promedio, digits: 1, unit: "°C" },
    { id: "air", icon: "🌫️", label: "Humedad del aire", value: s.humedad_aire, digits: 0, unit: "%", fill: s.humedad_aire / 100 },
    {
      id: "soil", icon: "🪴", label: "Tierra", value: s.humedad_tierra, digits: 0, raw: true, fill: s.humedad_tierra / 4095,
      hint: "Lectura cruda del sensor (0–4095), sin calibrar",
    },
    {
      id: "light", icon: "💡", label: "Luz", value: s.luz, digits: 0, raw: true, fill: s.luz / 4095,
      hint: "Lectura cruda del sensor (0–4095), sin calibrar. Un número más alto significa menos luz",
    },
  ];
}

export function greetingFor(theme) {
  return { morning: "¡Buen día!", afternoon: "¡Buenas tardes!", night: "¡Buenas noches!" }[theme];
}
