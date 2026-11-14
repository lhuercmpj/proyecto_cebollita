import { useEffect, useState } from "react";
import { getLatestMeasurement } from "../services/api.js";
import { STALE_MINUTES, minutesSince } from "../utils/measurements.js";

/** Consulta la ultima medicion cada `pollMs` y calcula su antiguedad. */
export function useMeasurement(pollMs = 60_000) {
  const [state, setState] = useState({ status: "loading", measurement: null });
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const measurement = await getLatestMeasurement();
        if (!cancelled) setState({ status: measurement ? "ok" : "empty", measurement });
      } catch {
        // Si ya habia una lectura se conserva; solo se marca el error.
        if (!cancelled) setState((prev) => ({ ...prev, status: "error" }));
      }
    }
    load();
    const poll = setInterval(load, pollMs);
    const tick = setInterval(() => setNow(Date.now()), 30_000);
    return () => {
      cancelled = true;
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [pollMs]);

  const ageMinutes = state.measurement ? minutesSince(state.measurement.measured_at, now) : null;
  return { ...state, ageMinutes, stale: ageMinutes !== null && ageMinutes > STALE_MINUTES };
}
