import csv, sys, statistics
from datetime import datetime
from collections import Counter

raw_path, out_path, report_path = sys.argv[1:4]
rows = list(csv.reader(open(raw_path, encoding="utf-8-sig")))
header = rows[0]
log = Counter(); examples = {}

def note(key, line, detail=""):
    log[key] += 1
    examples.setdefault(key, []).append(f"línea {line}{': ' + detail if detail else ''}")

def num(s):
    s = (s or "").strip()
    if not s: return None
    return float(s.replace(",", "."))

ESTADOS = {"bien": "Estoy bien", "estoy bien": "Estoy bien", "preciso agua": "Preciso agua",
           "preciso luz": "Preciso luz", "estoy mal (preciso ambos)": "Estoy mal", "estoy mal": "Estoy mal"}

recs = []
for i, r in enumerate(rows[1:], start=2):
    if not any(c.strip() for c in r):
        note("fila vacía", i); continue
    fecha = datetime.strptime(r[0].strip(), "%d/%m/%Y %H:%M:%S")
    vals = dict(zip(["humedad_tierra","temp_dht11","humedad_aire","temp_lm35","temp_promedio","luz"], [num(x) for x in r[2:8]]))
    estado_raw = r[8]
    est = ESTADOS.get(estado_raw.strip().lower())
    if est is None: raise SystemExit(f"estado desconocido {estado_raw!r} línea {i}")
    if estado_raw != est and estado_raw.strip() != "Estoy mal (preciso ambos)": note("etiqueta normalizada (espacios / 'Bien')", i, repr(estado_raw))
    if "," in "".join(r[2:8]) or any('"' in x for x in r): pass
    fmt = "coma_decimal" if any("," in x for x in r[2:8]) else "punto_decimal"
    recs.append(dict(line=i, fecha=fecha, estado=est, periodo_orig=r[9].strip(), formato=fmt, **vals))

valid = []
for rec in recs:
    i = rec["line"]
    if any(rec[k] is None for k in ("humedad_tierra","luz","humedad_aire","temp_dht11")):
        note("falta lectura del DHT11 u otro sensor", i); continue
    if rec["luz"] < 10:
        note("luz ≈ 0 (lectura inválida)", i, f"luz={rec['luz']}"); continue
    valid.append(rec)

# Duplicados por fecha
seen = set(); dedup = []
for rec in valid:
    if rec["fecha"] in seen: note("fecha duplicada", rec["line"]); continue
    seen.add(rec["fecha"]); dedup.append(rec)
valid = sorted(dedup, key=lambda r: r["fecha"])

def neighbors(lst, idx, k=3):
    return [r for r in lst[max(0, idx-k):idx] + lst[idx+1:idx+1+k]]

final = []
for idx, rec in enumerate(valid):
    i = rec["line"]
    nb = neighbors(valid, idx)
    med_dht = statistics.median(r["temp_dht11"] for r in nb)
    med_hum = statistics.median(r["humedad_aire"] for r in nb)
    # DHT11: lectura caída (típica del primer muestreo tras encender): temp. y humedad bajan juntas
    lm_gap = (rec["temp_lm35"] - rec["temp_dht11"]) if rec["temp_lm35"] is not None else 0
    if med_dht - rec["temp_dht11"] > 3 and (med_hum - rec["humedad_aire"] > 5 or lm_gap > 4):
        note("DHT11 con lectura caída (temp. y humedad bajan de golpe)", i,
             f"dht={rec['temp_dht11']} (vecinos {med_dht:.1f}) hum={rec['humedad_aire']} (vecinos {med_hum:.1f})"); continue
    # Humedad de tierra: pico aislado (difiere > 500 del anterior Y del siguiente, en la misma dirección)
    if 0 < idx < len(valid) - 1:
        a, b = valid[idx-1]["humedad_tierra"], valid[idx+1]["humedad_tierra"]
        x = rec["humedad_tierra"]
        if (x - a > 500 and x - b > 500) or (a - x > 500 and b - x > 500):
            note("pico aislado de humedad de tierra", i, f"{x} entre {a} y {b}"); continue
    # Humedad de tierra ~0 con estado "Estoy bien": sensor fuera de la tierra (contradicción)
    if rec["humedad_tierra"] < 50 and rec["estado"] == "Estoy bien":
        note("humedad de tierra ≈ 0 con estado «Estoy bien» (sensor fuera de la tierra)", i, f"{rec['humedad_tierra']}"); continue
    # LM35: pico respecto del DHT11 -> temp_promedio con solo DHT11 (el firmware marca >50 °C como sospechoso)
    if rec["temp_lm35"] is None:
        note("falta LM35 (temp_promedio = solo DHT11)", i); rec["lm35_sospechoso"] = True
    else:
        rec["lm35_sospechoso"] = rec["temp_lm35"] - rec["temp_dht11"] > 5 or rec["temp_lm35"] > 50
        if rec["lm35_sospechoso"]:
            note("LM35 con pico (temp_promedio = solo DHT11)", i, f"dht={rec['temp_dht11']} lm35={rec['temp_lm35']}")
    rec["temp_promedio"] = rec["temp_dht11"] if rec["lm35_sospechoso"] else round((rec["temp_dht11"] + rec["temp_lm35"]) / 2, 2)
    final.append(rec)

def periodo(h): return "Manana" if h < 12 else ("Tarde" if h < 18 else "Noche")
cambios_periodo = 0
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["registro","fecha_hora","humedad_tierra","luz","humedad_aire","temp_dht11","temp_lm35","temp_promedio","estado","periodo_dia","lm35_sospechoso","formato_origen"])
    for n, rec in enumerate(final, 1):
        p = periodo(rec["fecha"].hour)
        if p != rec["periodo_orig"]: cambios_periodo += 1
        w.writerow([n, rec["fecha"].strftime("%Y-%m-%d %H:%M:%S"), rec["humedad_tierra"], rec["luz"], rec["humedad_aire"],
                    rec["temp_dht11"], "" if rec["temp_lm35"] is None else rec["temp_lm35"], rec["temp_promedio"],
                    rec["estado"], p, int(rec["lm35_sospechoso"]), rec["formato"]])

import json
summary = dict(filas_crudas=len(rows)-1, filas_limpias=len(final), periodo_recalculado=cambios_periodo,
               estados=Counter(r["estado"] for r in final), desde=str(final[0]["fecha"]), hasta=str(final[-1]["fecha"]),
               log={k: v for k, v in log.items()}, ejemplos={k: v[:4] for k, v in examples.items()})
json.dump(summary, open(report_path, "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
