# Trabajos periódicos

## Qué va aquí

La programación de tareas que se ejecutan sin que el usuario escriba al chat. Esta carpeta se añade al esqueleto para ubicar explícitamente el requisito de los 30 minutos.

## Reporte de sensores

Archivo propuesto: `sensor_report_job.py`.

Cada 30 minutos debe:

1. Leer el destinatario registrado y la última medición persistida.
2. Revisar la fecha de la lectura y si hay datos nuevos.
3. Recuperar el estado predictivo asociado a esa lectura, si existe.
4. Construir el reporte con valores, unidades confirmadas y fecha.
5. Enviarlo a Telegram y registrar el resultado del envío.

Ejemplo: «Última lectura: 12:00. Temperatura promedio: 21,8 °C. Estado estimado: Bien». Si falta información, declararlo. No expresar humedad de tierra ni luz en porcentajes sin calibración.

## Frecuencia y datos atrasados

El intervalo del reporte es de 30 minutos. La toma y envío desde el dispositivo también se prevé cada 30 minutos, pero son procesos independientes. Definir cuándo una lectura se considera atrasada; por ejemplo, intervalo esperado más un margen configurable. No confundir esa política propuesta con una medición garantizada.

## Alertas de riego

Evaluarlas al recibir una lectura nueva, sin esperar al siguiente reporte periódico. El servicio de notificaciones conserva qué aviso fue enviado para no repetirlo continuamente.

## Operación

Ejecutar una única instancia del programador y mantenerla activa. Guardar el estado de envíos y reintentar errores transitorios de forma limitada. Prevenir la ejecución simultánea del mismo trabajo. Al reiniciar, continuar con el siguiente reporte según una política documentada, sin enviar de golpe todos los reportes omitidos.

En esta entrega se documenta la responsabilidad; el programador todavía debe implementarse.
