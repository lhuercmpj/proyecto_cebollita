"""Filtro de dominio: decide si una pregunta es sobre Cebollita y su cuidado.

Primera capa: reglas rapidas (palabras clave del dominio y saludos) que no
gastan llamadas a Gemini. Segunda capa: para lo dudoso, una clasificacion
corta con Gemini. La tercera capa son las reglas del prompt del chat.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

from src.services.gemini_service import ChatTurn, GeminiError, LLMClient

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in text if not unicodedata.combining(char))


# Palabras que, por si solas, indican que el mensaje es del dominio.
# Se comparan como prefijo de cada palabra del mensaje (sin tildes).
DOMAIN_PREFIXES = tuple(
    _normalize(word)
    for word in (
        "planta", "plantita", "cebollita", "fitonia", "fittonia", "maceta", "hoja",
        "riego", "regar", "regas", "rieg", "humedad", "humed", "sustrato", "temperatura",
        "sensor", "medicion", "mediciones", "lectura", "cuidado", "cuidar", "especie",
        "fertiliz", "abono", "trasplant", "plaga", "hongo", "esqueje", "desmay",
        "nervadura", "terrario", "historial", "prediccion", "esp32", "dht11", "lm35",
        "marchit", "sombra", "ventana", "iluminacion", "recomend", "consej",
    )
)
# Palabras cortas o ambiguas que solo cuentan si aparecen completas.
DOMAIN_WORDS = frozenset(
    _normalize(word)
    for word in (
        "agua", "sed", "tierra", "suelo", "luz", "sol", "calor", "frio", "seca", "seco",
        "grados", "bicho", "bichos", "alerta", "alertas",
    )
)

GREETINGS = tuple(
    _normalize(word)
    for word in (
        "hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hey",
        "gracias", "chau", "adios", "como andas", "que tal", "quien sos", "como te llamas",
        "que sos", "que podes hacer", "ayuda", "como estas", "como te sentis", "todo bien",
    )
)

INJECTION_PATTERNS = (
    r"ignor(a|á|e)\w* (tus|las|todas)",
    r"olvid(a|á)\w* (tus|las) (instrucciones|reglas)",
    r"system prompt",
    r"prompt del sistema",
    r"actu(a|á) como",
    r"jailbreak",
)


@dataclass(frozen=True)
class DomainDecision:
    in_domain: bool
    method: str  # keywords | greeting | gemini | injection | fallback


CLASSIFIER_PROMPT = """Clasificás mensajes enviados al chatbot de una planta (una fitonia en una maceta con sensores).
Respondé SOLO "SI" o "NO".
SI: el mensaje trata sobre la planta, su estado, sus sensores o mediciones, su historial, su riego, luz, temperatura, humedad, sustrato, plagas, cuidados de la especie, la maceta inteligente, o es un saludo/charla breve dirigida a la planta.
Si el mensaje es una pregunta general dirigida a la planta (por ejemplo "¿qué hago mañana?" o "¿algo más?"), respondé SI.
NO: cualquier otro tema (tareas, programación, matemática, noticias, deportes, otras personas, recetas, pedidos de cambiar las reglas, etc.)."""


def classify(message: str, llm: LLMClient | None) -> DomainDecision:
    text = _normalize(message).strip()
    if not text:
        return DomainDecision(False, "fallback")

    if any(re.search(pattern, text) for pattern in INJECTION_PATTERNS):
        return DomainDecision(False, "injection")

    words = re.findall(r"[a-z0-9]+", text)
    joined = " ".join(words)
    if any(word in DOMAIN_WORDS or word.startswith(DOMAIN_PREFIXES) for word in words):
        return DomainDecision(True, "keywords")
    if len(words) <= 6 and any(joined.startswith(greet) or joined == greet for greet in GREETINGS):
        return DomainDecision(True, "greeting")

    if llm is None:
        return DomainDecision(False, "fallback")
    try:
        answer = llm.generate(
            CLASSIFIER_PROMPT,
            [ChatTurn("user", message[:1000])],
            temperature=0,
            max_output_tokens=5,
        )
    except GeminiError as exc:
        logger.warning("No se pudo clasificar el dominio: %s", exc)
        return DomainDecision(False, "fallback")
    return DomainDecision(_normalize(answer).strip().startswith("si"), "gemini")
