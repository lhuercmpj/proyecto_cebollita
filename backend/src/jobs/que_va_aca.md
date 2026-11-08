# Trabajos periódicos

Implementado en `sensor_report_job.py` (`python -m src.jobs.sensor_report_job`).

Cada `REPORT_INTERVAL_MINUTES` (30 por defecto):

1. Pide una medición a la ESP32 (`POST /api/medir`) sin reintentos automáticos.
2. Si responde, la guarda (sin duplicar), envía el reporte a los chats
   suscriptos y evalúa la alerta.
3. Si falla, registra el error en `job_runs` sin generar una medición y avisa
   una vez por racha de fallos.

Decisiones:

- Una lectura está atrasada si supera el intervalo más `STALE_MARGIN_MINUTES`.
- Alertas: al cambiar a `Preciso agua`, `Preciso luz` o `Estoy mal`;
  recordatorio cada `ALERT_REPEAT_MINUTES` si sigue igual; aviso al volver a
  `Estoy bien`. Si ningún chat la recibió, se reintenta en la próxima medición.
- Al reiniciar se mide una sola vez y se retoma el ritmo; no se envían los
  reportes omitidos.
- Una sola instancia: advisory lock de PostgreSQL.
