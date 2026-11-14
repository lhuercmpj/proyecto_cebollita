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
        "document", "fuente", "bibliograf", "estudio", "investigac", "dataset", "historic",
        "registro", "septiembre", "setiembre", "octubre", "noviembre", "promedio", "estadistic",
    )
)
# Palabras cortas o ambiguas que solo cuentan si aparecen completas.
DOMAIN_WORDS = frozenset(
    _normalize(word)
    for word in (
        "agua", "sed", "tierra", "suelo", "luz", "sol", "calor", "frio", "seca", "seco",
        "grados", "bicho", "bichos", "alerta", "alertas", "dato", "datos", "rag", "mes",
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

# Preguntas dirigidas a la propia Cebollita (identidad, personalidad, gustos).
SELF_PATTERNS = (
    r"\b(quien|que|como) sos\b",
    r"\bsos (una|un|la|el|muy|re|de)\b",
    r"\bte (gusta|gustan|encanta|llamas|sentis|pasa|parece|cae|molesta|cuidan|regaron|riegan)\b",
    r"\b(tenes|tienes) (sed|frio|calor|hambre|nombre|amigos|hojas|flores|miedo|ganas)\b",
    r"\b(tu|tus) (nombre|hojas|nervaduras|color|colores|maceta|especie|personalidad|estilo|dia|dueno|duena|origen|familia)\b",
    r"\bde donde (sos|venis)\b",
    r"\bcuantos anos\b",
    r"\bque (opinas|pensas|sentis|necesitas|queres|preferis|haces)\b",
    r"\bcomo (estuviste|dormiste|amaneciste|te fue|andas|va)\b",
    r"\bestas (bien|mal|feliz|triste|contenta|enojada|linda|divina)\b",
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
También SI: preguntas sobre la propia planta como personaje (su nombre, personalidad, gustos, origen, especie, cómo se siente, qué opina de quien la cuida, su día).
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

    if any(re.search(pattern, joined) for pattern in SELF_PATTERNS):
        return DomainDecision(True, "self")

    if llm is None:
        return DomainDecision(False, "fallback")
    try:
        # Sin limite de tokens: los modelos Flash actuales "piensan" antes de
        # responder y con un limite chico devolvian una respuesta vacia.
        answer = llm.generate(CLASSIFIER_PROMPT, [ChatTurn("user", message[:1000])], temperature=0)
    except GeminiError as exc:
        # Si el clasificador falla, se deja pasar: las reglas del prompt (tercera
        # capa) igual hacen que la planta rechace lo que no es de su dominio.
        logger.warning("No se pudo clasificar el dominio, se deja pasar: %s", exc)
        return DomainDecision(True, "fallback-permit")
    return DomainDecision("si" in _normalize(answer).split()[:3] or _normalize(answer).strip().startswith("si"), "gemini")
