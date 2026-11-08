from datetime import UTC, datetime

import httpx

from src.config import Settings
from src.schemas.measurement import DeviceMeasurement


class DeviceUnavailableError(RuntimeError):
    pass


async def request_measurement(
    settings: Settings,
    sample_index: int | None = None,
) -> DeviceMeasurement:
    params = {} if sample_index is None else {"sample_index": sample_index}
    url = f"{settings.sensor_device_url.rstrip('/')}/api/medir"
    body = {"timestamp_unix": int(datetime.now(UTC).timestamp())}

    try:
        async with httpx.AsyncClient(timeout=settings.sensor_timeout_seconds) as client:
            response = await client.post(
                url,
                params=params,
                json=body,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DeviceUnavailableError(f"No se pudo obtener la medicion: {exc}") from exc

    try:
        return DeviceMeasurement.model_validate(response.json())
    except (ValueError, TypeError) as exc:
        raise DeviceUnavailableError("La ESP32 devolvio una medicion invalida") from exc

