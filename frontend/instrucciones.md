# Frontend

La página de Cebollita, construida con React + Vite y JavaScript. Muestra el chat, el estado de la planta, las últimas mediciones y un reproductor de música, con un fondo que cambia según la hora del día.

## Cómo correrla

**Con Docker (lo normal).** El servicio `frontend` de `compose.yaml` compila la página (`Dockerfile`) y la sirve con nginx en http://localhost:5173. Sale con `docker compose up --build` junto con el resto, o solo con `docker compose up -d --build frontend`. La URL de la API se fija al compilar con `VITE_API_URL` (en el `.env` de la raíz; por defecto `http://localhost:8000`), así que si cambia hay que reconstruir.

**Para desarrollar, con recarga en vivo.** Hace falta Node 20.19 o superior (o 22.12+) y la API levantada (`docker compose up -d db simulator api`). Vite usa siempre el puerto 5174, así que puede convivir con el contenedor (5173) sin apagarlo:

```powershell
cd frontend
npm install
copy .env.example .env     # VITE_API_URL=http://localhost:8000
npm run dev                # http://localhost:5174
npm run build              # versión de producción en dist/
```

La API tiene que permitir el origen de la página: se configura con `CORS_ORIGINS` en el `.env` de la raíz (por defecto los puertos 5173, del contenedor, y 5174, de `npm run dev`). Si la página se publica en otro dominio, agregarlo ahí.

## Qué muestra

- **Chat** dentro de un celular: burbujas con hora, botones de sugerencia y una tarjeta con las lecturas (botón «Mostrame tus datos», que no usa Gemini). Habla con `POST /api/chat`, el mismo servicio que el bot de Telegram.
- **Planta con estados**: cambia de aspecto según el estado que estima el modelo (`Estoy bien`, `Preciso luz`, `Preciso agua`, `Estoy mal`) y muestra una burbuja con lo que le pasa.
- **Panel de mediciones**: temperatura, humedad del aire, tierra y luz, con el estado del modelo y hace cuánto llegó la lectura. Avisa si está atrasada (más de 40 minutos: 30 de intervalo más 10 de margen, igual que el backend). Consulta `GET /api/measurements/latest` cada minuto.
- **Fondo según la hora**: mañana (6–12), tarde (12–19) y noche (19–6), con saludo, partículas (mariposas, polen, luciérnagas) y sombra de la planta en el suelo. El botón de arriba a la derecha rota entre los tres; `?tema=manana`, `?tema=tarde` o `?tema=noche` fuerza uno.
- **Música**: jazz, bossa, clásica y pop, con listas fijas de temas de YouTube (no hay archivos .mp3 en el proyecto).

La humedad de la tierra y la luz son lecturas crudas del sensor (0–4095, sin calibrar). Se muestran tal cual, con la etiqueta «crudo», nunca como porcentaje. En el sensor de luz actual, un número más alto significa menos luz.

## Organización

- `src/components/`: `Chat`, `Phone`, `PlantStage`, `MeasurementPanel`, `MiniReadings`, `MusicPlayer` y `Sky` (fondo y partículas).
- `src/hooks/`: `useTheme` (fondo según la hora) y `useMeasurement` (consulta de la última medición).
- `src/services/api.js`: llamadas al backend.
- `src/utils/measurements.js`: estados del modelo, formato de lecturas y saludos.
- `src/data/music.js`: catálogo de música. Está generado, no se edita a mano.
- `src/assets/`: `cebollita.png` (ilustración original) y `plant/` (las cuatro variantes generadas).
- `src/styles/`: `index.css` (base y diseño) y `extras.css` (planta, panel, chat, partículas y sombras).
- `scripts/`: herramientas para regenerar imágenes y música.

## Regenerar la planta y la música

Las cuatro imágenes de la planta se generan a partir de `src/assets/cebollita.png` (necesita `pillow`, `numpy` y `opencv-python-headless`):

```powershell
python scripts/generar_planta.py
```

El catálogo de música se arma desde álbumes oficiales de YouTube Music y comprueba que cada tema se pueda reproducir embebido (solo librería estándar, necesita internet):

```powershell
python scripts/generar_musica.py
```

Para agregar música, sumar el ID de un álbum (`OLAK5uy_...`, en la URL del álbum en music.youtube.com) a `ALBUMS` en `scripts/generar_musica.py` y volver a ejecutarlo.

## Límites de responsabilidad

El frontend muestra información y envía consultas. Gemini, el modelo predictivo, el almacenamiento y los avisos programados se ejecutan en el backend. Cerrar la página no detiene los reportes a Telegram. Nunca guardar aquí tokens privados: lo único que se configura es `VITE_API_URL`.
