import { useEffect, useRef, useState } from "react";
import { TRACKS } from "../data/music.js";

// Cada estilo es una lista fija de temas (src/data/music.js, generada con
// scripts/generar_musica.py): no se usan playlists de terceros, asi que no puede
// sonar nada de otro genero. Los temas se mezclan al elegir el estilo.
const STYLES = [
  { id: "jazz", label: "Jazz", emoji: "🎷" },
  { id: "bossa", label: "Bossa", emoji: "🌴" },
  { id: "clasica", label: "Clásica", emoji: "🎻" },
  { id: "pop", label: "Pop", emoji: "🎀" },
];
const STORAGE_KEY = "cebollita.music_style";
const DEFAULT_STYLE = "bossa";
const DEFAULT_VOLUME = 35;
const MAX_ERRORS_IN_A_ROW = 6;
const MAX_CORRECTIONS = 2;
const LOADING_TIMEOUT_MS = 10_000; // si el navegador bloquea el audio, no dejar el indicador girando

const BY_ID = Object.fromEntries(
  Object.entries(TRACKS).map(([style, tracks]) => [style, Object.fromEntries(tracks.map((t) => [t.id, t]))]),
);

function shuffledIds(styleId) {
  const ids = TRACKS[styleId].map((t) => t.id);
  for (let i = ids.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [ids[i], ids[j]] = [ids[j], ids[i]];
  }
  return ids;
}

function loadStyleId() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return STYLES.some((s) => s.id === saved) ? saved : DEFAULT_STYLE;
  } catch {
    return DEFAULT_STYLE;
  }
}

let apiPromise;
function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (!apiPromise) {
    apiPromise = new Promise((resolve) => {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        previous?.();
        resolve(window.YT);
      };
      const script = document.createElement("script");
      script.src = "https://www.youtube.com/iframe_api";
      document.head.appendChild(script);
    });
  }
  return apiPromise;
}

export default function MusicPlayer() {
  const mountRef = useRef(null);
  const playerRef = useRef(null);
  const errorsInARow = useRef(0);
  const corrections = useRef(0);
  const [styleId, setStyleId] = useState(loadStyleId);
  const styleRef = useRef(styleId); // estilo vigente (lo leen los callbacks del reproductor)
  const queueRef = useRef(shuffledIds(styleId));
  const [nowId, setNowId] = useState(queueRef.current[0]);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(false); // se pidio reproducir y el audio todavia no llego
  const warmingUp = useRef(false); // precarga silenciosa del primer tema
  const loadingTimer = useRef(null);

  const style = STYLES.find((s) => s.id === styleId);
  const track = BY_ID[styleId][nowId];

  useEffect(() => {
    let cancelled = false;
    loadYouTubeApi().then((YT) => {
      if (cancelled || !mountRef.current) return;
      playerRef.current = new YT.Player(mountRef.current, {
        height: "0",
        width: "0",
        playerVars: { controls: 0, playsinline: 1 },
        events: {
          onReady: (e) => {
            e.target.setVolume(DEFAULT_VOLUME);
            e.target.cuePlaylist(queueRef.current, 0);
            e.target.setLoop(true);
            setReady(true);
            // Precarga: arranca en silencio y se pausa apenas empieza, asi el play del usuario es casi inmediato.
            warmingUp.current = true;
            e.target.mute();
            e.target.playVideo();
          },
          onStateChange: (e) => {
            if (warmingUp.current && e.data === YT.PlayerState.PLAYING) {
              warmingUp.current = false;
              e.target.pauseVideo();
              e.target.unMute();
              return;
            }
            setPlaying(e.data === YT.PlayerState.PLAYING);
            if (e.data === YT.PlayerState.PLAYING) stopLoading();
            if (e.data !== YT.PlayerState.PLAYING && e.data !== YT.PlayerState.BUFFERING) return;
            const videoId = e.target.getVideoData?.().video_id;
            if (!videoId) return;
            if (BY_ID[styleRef.current][videoId]) {
              errorsInARow.current = 0;
              corrections.current = 0;
              setUnavailable(false);
              setNowId(videoId);
            } else if (corrections.current < MAX_CORRECTIONS) {
              // Suena algo que no es del estilo elegido (por ejemplo, el tema anterior): se corrige.
              corrections.current += 1;
              e.target.loadPlaylist(queueRef.current, 0);
              e.target.setLoop(true);
            } else {
              e.target.stopVideo();
              setUnavailable(true);
            }
          },
          // Video no disponible o no embebible: pasar al siguiente (hasta cierto limite).
          onError: (e) => {
            stopLoading();
            errorsInARow.current += 1;
            if (errorsInARow.current > MAX_ERRORS_IN_A_ROW) {
              setUnavailable(true);
              return;
            }
            e.target.nextVideo();
          },
        },
      });
    });
    return () => {
      cancelled = true;
      clearTimeout(loadingTimer.current);
      playerRef.current?.destroy?.();
      playerRef.current = null;
    };
  }, []);

  function stopLoading() {
    clearTimeout(loadingTimer.current);
    setLoading(false);
  }

  function startLoading() {
    setLoading(true);
    clearTimeout(loadingTimer.current);
    loadingTimer.current = setTimeout(() => setLoading(false), LOADING_TIMEOUT_MS);
  }

  // Cualquier accion del usuario cancela la precarga silenciosa.
  function takeOver(player) {
    if (warmingUp.current) {
      warmingUp.current = false;
      player.unMute();
    }
  }

  function toggle() {
    const player = playerRef.current;
    if (!player || !ready) return;
    takeOver(player);
    if (playing || loading) {
      player.pauseVideo();
      stopLoading();
    } else {
      startLoading();
      player.playVideo();
    }
  }

  function next() {
    const player = playerRef.current;
    if (!player || !ready) return;
    takeOver(player);
    startLoading();
    player.nextVideo();
  }

  function chooseStyle(next) {
    if (next.id === styleId) return;
    const queue = shuffledIds(next.id);
    queueRef.current = queue;
    styleRef.current = next.id;
    errorsInARow.current = 0;
    corrections.current = 0;
    setStyleId(next.id);
    setNowId(queue[0]);
    setUnavailable(false);
    try {
      localStorage.setItem(STORAGE_KEY, next.id);
    } catch {
      /* sin almacenamiento: no se recuerda el estilo */
    }
    const player = playerRef.current;
    if (player && ready) {
      takeOver(player);
      startLoading();
      player.loadPlaylist(queue, 0); // arranca de inmediato con el nuevo estilo
      player.setLoop(true);
    }
  }

  return (
    <div className="music glass" data-style={styleId} role="group" aria-label="Reproductor de música">
      <div className="music__player" aria-hidden="true">
        <div ref={mountRef} id="cebollita-yt" />
      </div>

      <div className="music__row">
        <div className={`music__disc${playing ? " music__disc--spin" : ""}`} aria-hidden="true">{style.emoji}</div>
        <div className="music__info">
          <span className="music__label">{style.label}{track ? ` · ${track.artist}` : ""}</span>
          <span className="music__title" title={track?.title}>
            {unavailable ? "No pude reproducir este estilo" : track?.title ?? "Tocá play para empezar"}
          </span>
        </div>
        <div className="music__controls">
          <button type="button" onClick={toggle} disabled={!ready} aria-label={playing ? "Pausar" : loading ? "Cargando, tocá para cancelar" : "Reproducir"} aria-busy={loading}>
            {loading && !playing ? (
              <span className="music__spinner" aria-hidden="true" />
            ) : playing ? (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1.2" /><rect x="14" y="5" width="4" height="14" rx="1.2" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" /></svg>
            )}
          </button>
          <button type="button" onClick={next} disabled={!ready} aria-label="Siguiente">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M6 6.5v11a.9.9 0 0 0 1.4.75l8-5.5a.9.9 0 0 0 0-1.5l-8-5.5A.9.9 0 0 0 6 6.5zM17 6h1.6a.9.9 0 0 1 .9.9v10.2a.9.9 0 0 1-.9.9H17z" /></svg>
          </button>
        </div>
      </div>

      <div className="music__styles" role="radiogroup" aria-label="Estilo de música">
        {STYLES.map((s) => (
          <button
            key={s.id}
            type="button"
            role="radio"
            aria-checked={s.id === styleId}
            className={s.id === styleId ? "is-active" : ""}
            onClick={() => chooseStyle(s)}
          >
            <span aria-hidden="true">{s.emoji}</span> {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
