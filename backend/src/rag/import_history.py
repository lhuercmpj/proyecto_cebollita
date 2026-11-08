"""Importa el dataset historico (CSV de la Tarea 2) a la tabla ``measurements``.

    python -m src.rag.import_history data/sensors/dataset_limpio.csv
    python -m src.rag.import_history archivo.csv --dry-run

Columnas esperadas (nombres del proyecto): fecha_hora, humedad_tierra, luz,
humedad_aire, temp_dht11, temp_lm35 y, opcionalmente, temp_promedio y estado.
``fecha_hora`` se interpreta en la zona horaria de ``TIMEZONE``
(America/Montevideo) salvo que traiga desfase propio.

La prediccion se recalcula con el modelo actual; la etiqueta historica
(``estado``) se conserva aparte en ``raw_payload`` para no confundirlas.
Las filas ya importadas (mismo instante) se omiten.
"""

import argparse
import csv
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.db_models.measurement import Measurement
from src.services.model_data import MODEL_VERSION
from src.services.prediction_service import predict

logger = logging.getLogger("cebollita.import")

SOURCE = "historico_tarea2"
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M")


@dataclass
class ImportResult:
    imported: int = 0
    duplicated: int = 0
    skipped: list[str] = field(default_factory=list)


def parse_datetime(value: str, tz: ZoneInfo) -> datetime:
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        for fmt in DATE_FORMATS:
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"fecha no reconocida: {value!r}") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(UTC)


def parse_float(row: dict[str, str], column: str) -> float:
    raw = (row.get(column) or "").strip().replace(",", ".")
    if not raw:
        raise ValueError(f"falta {column}")
    return float(raw)


def import_rows(
    session: Session,
    rows: list[dict[str, str]],
    settings: Settings,
    dry_run: bool = False,
) -> ImportResult:
    tz = ZoneInfo(settings.timezone)
    result = ImportResult()
    existing = set(
        session.scalars(select(Measurement.measured_at).where(Measurement.plant_id == settings.plant_id))
    )
    existing = {value if value.tzinfo else value.replace(tzinfo=UTC) for value in existing}
    now = datetime.now(UTC)

    for line_number, row in enumerate(rows, start=2):
        try:
            measured_at = parse_datetime(row["fecha_hora"], tz)
            soil = parse_float(row, "humedad_tierra")
            light = parse_float(row, "luz")
            air = parse_float(row, "humedad_aire")
            t_dht = parse_float(row, "temp_dht11")
            t_lm = parse_float(row, "temp_lm35")
        except (KeyError, ValueError) as exc:
            result.skipped.append(f"línea {line_number}: {exc}")
            continue
        if measured_at in existing:
            result.duplicated += 1
            continue
        # Mismo calculo que el firmware y la Tarea 2.
        t_avg = (t_dht + t_lm) / 2
        prediction = predict(humedad_tierra=soil, luz=light, humedad_aire=air, temp_promedio=t_avg)
        timestamp = int(measured_at.timestamp())
        if not dry_run:
            session.add(
                Measurement(
                    measurement_id=f"{SOURCE}-{settings.plant_id}-{timestamp}",
                    plant_id=settings.plant_id,
                    source=SOURCE,
                    measured_at=measured_at,
                    received_at=now,
                    humedad_tierra=soil,
                    luz=light,
                    humedad_aire=air,
                    temp_dht11=t_dht,
                    temp_lm35=t_lm,
                    temp_promedio=t_avg,
                    predicted_class=prediction.class_index,
                    predicted_state=prediction.state,
                    confidence=prediction.confidence,
                    probabilities=prediction.probabilities,
                    model_version=MODEL_VERSION,
                    backend_prediction_matches=True,
                    raw_payload={"fuente": SOURCE, "fila": row, "estado_historico": row.get("estado")},
                )
            )
        existing.add(measured_at)
        result.imported += 1
    if not dry_run:
        session.commit()
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="validar sin guardar")
    parser.add_argument("--delimiter", default=None, help="separador (por defecto se detecta)")
    args = parser.parse_args()

    from src.database import SessionLocal, create_tables

    text = args.csv_path.read_text(encoding="utf-8-sig")
    delimiter = args.delimiter or csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t").delimiter
    rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
    create_tables()
    with SessionLocal() as session:
        result = import_rows(session, rows, get_settings(), dry_run=args.dry_run)
    logger.info(
        "%s %s filas, %s ya existían, %s omitidas",
        "Validadas" if args.dry_run else "Importadas",
        result.imported,
        result.duplicated,
        len(result.skipped),
    )
    for problem in result.skipped[:20]:
        logger.warning(problem)


if __name__ == "__main__":
    main()
