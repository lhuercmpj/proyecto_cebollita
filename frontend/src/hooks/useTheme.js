import { useEffect, useLayoutEffect, useState } from "react";

export const THEMES = ["morning", "afternoon", "night"];

// Horario (hora local del navegador): manana 6-12, tarde 12-19, noche 19-6.
function themeForNow() {
  const hour = new Date().getHours();
  if (hour >= 19 || hour < 6) return "night";
  return hour < 12 ? "morning" : "afternoon";
}

// Permite forzar el fondo con ?tema=manana | tarde | noche (util para probar).
const URL_THEMES = { manana: "morning", tarde: "afternoon", noche: "night" };
function themeFromUrl() {
  const value = new URLSearchParams(window.location.search).get("tema");
  return URL_THEMES[value] ?? null;
}

const BROWSER_COLOR = { morning: "#fbf3e8", afternoon: "#fbe5c6", night: "#0d1b2a" };

/** Fondo automatico segun la hora; `toggle` rota entre los tres hasta recargar la pagina. */
export function useTheme() {
  const [auto, setAuto] = useState(themeForNow);
  const [manual, setManual] = useState(themeFromUrl);
  const theme = manual ?? auto;

  useEffect(() => {
    const id = setInterval(() => setAuto(themeForNow()), 60_000);
    return () => clearInterval(id);
  }, []);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", BROWSER_COLOR[theme]);
  }, [theme]);

  const toggle = () => setManual(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]);
  return { theme, toggle };
}
