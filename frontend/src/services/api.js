const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {}

/** Ultima medicion de los sensores, o null si todavia no hay ninguna. */
export async function getLatestMeasurement() {
  let response;
  try {
    response = await fetch(`${API_URL}/api/measurements/latest`);
  } catch {
    throw new ApiError("No pude conectarme con el servidor.");
  }
  if (response.status === 404) return null;
  if (!response.ok) throw new ApiError("No pude leer las mediciones.");
  return response.json();
}

/** Envia un mensaje a Cebollita y devuelve { conversation_id, reply, ... }. */
export async function sendMessage(message, conversationId) {
  let response;
  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
    });
  } catch {
    throw new ApiError("No pude conectarme con Cebollita. ¿Está encendido el servidor?");
  }
  if (!response.ok) {
    throw new ApiError("Cebollita no pudo responder ahora. Probá de nuevo en un rato.");
  }
  return response.json();
}
