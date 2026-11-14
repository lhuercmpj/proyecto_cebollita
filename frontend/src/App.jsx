import Chat from "./components/Chat.jsx";
import MeasurementPanel from "./components/MeasurementPanel.jsx";
import MusicPlayer from "./components/MusicPlayer.jsx";
import Phone from "./components/Phone.jsx";
import PlantStage from "./components/PlantStage.jsx";
import Sky from "./components/Sky.jsx";
import { useMeasurement } from "./hooks/useMeasurement.js";
import { useTheme } from "./hooks/useTheme.js";
import { greetingFor } from "./utils/measurements.js";

const THEME_LABELS = { morning: "Mañana", afternoon: "Tarde", night: "Noche" };

export default function App() {
  const { theme, toggle } = useTheme();
  const measurements = useMeasurement();
  const label = THEME_LABELS[theme];
  const greeting = greetingFor(theme);

  return (
    <>
      <Sky />
      <div className="app">
        <header className="app__header">
          <div>
            <h1>Cebollita</h1>
            <p className="app__greeting">{greeting}</p>
          </div>
          <button
            type="button"
            className="theme-toggle glass"
            onClick={toggle}
            aria-label={`Fondo: ${label}. Tocá para cambiar`}
            title={`${label} (tocá para cambiar)`}
          >
            {theme === "night" ? (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a.6.6 0 0 0-.8-.7A9.5 9.5 0 1 0 21.2 15.3a.6.6 0 0 0-.7-.8z" /></svg>
            ) : theme === "afternoon" ? (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M5 17a7 7 0 0 1 14 0M2 20h20M12 4v2M4.9 8.9l1.4 1.4M19.1 8.9l-1.4 1.4" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
            )}
          </button>
        </header>

        <aside className="app__side">
          <MusicPlayer />
          <MeasurementPanel {...measurements} />
          <PlantStage {...measurements} />
        </aside>

        <main className="app__main">
          <Phone>
            <Chat greeting={greeting} />
          </Phone>
        </main>
      </div>
    </>
  );
}
