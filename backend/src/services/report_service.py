"""Textos deterministas de reportes y alertas.

Las cifras salen siempre de la medicion guardada: estos mensajes no pasan por
Gemini, asi que no puede inventar ni redondear valores.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.config import Settings
from src.schemas.measurement import MeasurementRead

ALERT_STATES = ("Preciso agua", "Preciso luz", "Estoy mal")
OK_STATE = "Estoy bien"

STATE_LINES = {
    "Estoy bien": "Estoy re bien, gracias por cuidarme 🌿",
    "Preciso luz": "Me vendría bárbaro un poco más de luz (indirecta, eh, que el sol directo me quema).",
    "Preciso agua": "Tengo seeed... si me ves medio desmayada es por eso 💧",
    "Estoy mal": "No me siento nada bien, ¿me das una mano? 🥀",
}

ALERT_TEXTS = {
    "Preciso agua": (
        "💧 ¡Alerta de riego! Soy Cebollita y necesito agua.\n"
        "Regame con agua a temperatura ambiente hasta que la tierra quede húmeda "
        "(no encharcada) y tirá el agua que sobre en el plato."
    ),
    "Preciso luz": (
        "☀️ Cebollita acá: me falta luz.\n"
        "Acercame a una ventana con luz brillante pero indirecta; el sol directo me quema las hojas."
    ),
    "Estoy mal": (
        "🥀 Cebollita no está bien.\n"
        "Revisá la tierra, la luz y la temperatura del lugar. "
        "Preguntame «¿cómo estás?» y te cuento qué ven mis sensores."
    ),
}


def _number(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def local_time(value: datetime, settings: Settings) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo(settings.timezone))


def format_local(value: datetime, settings: Settings) -> str:
    return local_time(value, settings).strftime("%d/%m/%Y %H:%M")


def is_stale(measurement: MeasurementRead, settings: Settings, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    limit = timedelta(minutes=settings.report_interval_minutes + settings.stale_margin_minutes)
    return now - measurement.measured_at > limit


def sensor_lines(measurement: MeasurementRead) -> list[str]:
    sensors = measurement.sensors
    return [
        f"• Temperatura promedio: {_number(measurement.temp_promedio)} °C "
        f"(DHT11 {_number(sensors.temp_dht11)} / LM35 {_number(sensors.temp_lm35)})",
        f"• Humedad del aire: {_number(sensors.humedad_aire, 0)} %",
        f"• Humedad de la tierra: {_number(sensors.humedad_tierra, 0)} "
        "(lectura cruda del sensor, escala 0–4095, sin calibrar)",
        f"• Luz: {_number(sensors.luz, 0)} (lectura cruda del sensor, escala 0–4095, sin calibrar)",
    ]


def format_report(
    measurement: MeasurementRead,
    settings: Settings,
    now: datetime | None = None,
) -> str:
    prediction = measurement.prediction
    lines = [
        f"🌱 Reporte de Cebollita — {format_local(measurement.measured_at, settings)}",
        f"Estado estimado por el modelo: {prediction.state} "
        f"(probabilidad {_number(prediction.confidence * 100, 0)} %)",
        *sensor_lines(measurement),
        "",
        STATE_LINES.get(prediction.state, ""),
    ]
    if is_stale(measurement, settings, now):
        lines.append("⚠️ Ojo: esta lectura está atrasada, no llegaron datos nuevos de los sensores.")
    return "\n".join(line for line in lines if line is not None).strip()


def format_alert(measurement: MeasurementRead, settings: Settings, reminder: bool = False) -> str:
    state = measurement.prediction.state
    header = ALERT_TEXTS.get(state, f"⚠️ Estado: {state}")
    if reminder:
        header = "🔁 Recordatorio: sigo igual.\n" + header
    return (
        f"{header}\n\n"
        f"Lectura de las {format_local(measurement.measured_at, settings)} — "
        f"probabilidad {_number(measurement.prediction.confidence * 100, 0)} %."
    )


def format_recovery(measurement: MeasurementRead, settings: Settings) -> str:
    return (
        "🌿 ¡Ya estoy mejor! El modelo volvió a estimar «Estoy bien» "
        f"en la lectura de las {format_local(measurement.measured_at, settings)}. Gracias 💚"
    )


def format_device_error(settings: Settings) -> str:
    return (
        "📡 No pude leer mis sensores en la última medición programada. "
        "Revisá que la placa esté encendida y conectada al Wi-Fi. "
        "Te aviso cuando vuelva a medir."
    )
