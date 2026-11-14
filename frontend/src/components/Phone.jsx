import { useEffect, useState } from "react";
import avatar from "../assets/plant/bien.webp";

function useClock() {
  const format = () =>
    new Date().toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit", hour12: false });
  const [time, setTime] = useState(format);
  useEffect(() => {
    const id = setInterval(() => setTime(format()), 15_000);
    return () => clearInterval(id);
  }, []);
  return time;
}

/** Marco de celular; el contenido (el chat) va dentro de la pantalla. */
export default function Phone({ children }) {
  const time = useClock();
  return (
    <div className="phone">
      <div className="phone__screen">
        <div className="phone__island" aria-hidden="true" />
        <div className="phone__status" aria-hidden="true">
          <span>{time}</span>
          <span className="phone__icons">
            <svg viewBox="0 0 18 12" width="17" height="11" fill="currentColor"><rect x="0" y="8" width="3" height="4" rx="1" /><rect x="5" y="5.5" width="3" height="6.5" rx="1" /><rect x="10" y="3" width="3" height="9" rx="1" /><rect x="15" y="0" width="3" height="12" rx="1" /></svg>
            <svg viewBox="0 0 27 12" width="26" height="12" fill="none"><rect x="0.5" y="0.5" width="22" height="11" rx="3.5" stroke="currentColor" opacity="0.5" /><rect x="2" y="2" width="16" height="8" rx="2" fill="currentColor" /><rect x="24" y="4" width="2" height="4" rx="1" fill="currentColor" opacity="0.5" /></svg>
          </span>
        </div>

        <div className="phone__header">
          <img src={avatar} alt="" className="phone__avatar" />
          <div>
            <div className="phone__name">Cebollita</div>
            <div className="phone__sub">Fittonia · en línea</div>
          </div>
        </div>

        {children}
        <div className="phone__home" aria-hidden="true" />
      </div>
    </div>
  );
}
