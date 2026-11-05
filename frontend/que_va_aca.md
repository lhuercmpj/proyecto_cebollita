# Frontend

## Qué va aquí

La página de Cebollita, construida con React + Vite y JavaScript. Esta carpeta se inicializará con Vite; este README no instala React.

## Organización sugerida

- `src/components/`: chat, ilustración de la planta, tarjetas de mediciones y estado de conexión.
- `src/pages/`: pantalla principal, si se necesita separar vistas.
- `src/services/api.js`: llamadas al backend.
- `src/assets/`: ilustraciones e iconos.
- `src/styles/`: estilos y adaptación a dispositivos móviles.

## Comportamiento esperado

Mostrar el chat, el estado de la planta, las últimas mediciones y la fecha de la lectura. Indicar cuando aún no llegaron datos o están desactualizados. Mantener la estética del boceto de Cebollita.

Ejemplo: cuando llega una lectura al backend, la página puede consultarla periódicamente; más adelante se puede usar SSE o WebSocket. La frecuencia de actualización de la pantalla es independiente de los 30 minutos entre mediciones.

## Límites de responsabilidad

El frontend muestra información y envía consultas. Gemini, el modelo predictivo, el almacenamiento y los avisos programados se ejecutan en el backend. Cerrar la página no debe detener los reportes a Telegram. Nunca guardar aquí tokens privados.
