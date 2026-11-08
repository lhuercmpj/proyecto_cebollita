/*
 * Cebollita: backend -> HTTP -> sensores -> modelo local -> JSON.
 * Arduino ESP32 + DHT sensor library (Adafruit) + ArduinoJson 7.
 * Copiar el modelo.h REAL del entrenamiento junto a este .ino.
 * Contrato de modelo.h: igual al codigo original (MinMax + ReLU + softmax).
 * POST /api/medir: nueva medicion, demora aprox. 9 s. No usar reintentos
 * automaticos: cada POST realiza una medicion distinta.
 * GET /api/salud: conectividad, sin medir.
 * Cuerpo opcional: {"timestamp_unix":1794142800} (segundos UTC, no ms).
 * Serial: UNA, VERIFICAR, LEDS, HORA, IP (115200).
 * La programacion cada 30 minutos queda a cargo del backend.
 */
#include <Arduino.h>
#include <DHT.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <time.h>
#include <sys/time.h>
#include <math.h>
#include "modelo.h"

#define PIN_HUMEDAD_TIERRA 34
#define PIN_DHT11 4
#define PIN_LM35 32
#define PIN_LUZ 33
// Se conserva el cableado DEFINIDO en el codigo original; su encabezado
// tenia verde/amarillo intercambiados. Revisar estos pines en la placa.
#define LED_ROJO 25
#define LED_VERDE 27
#define LED_AMARILLO 26
#define MUESTRAS 30
#define DELAY_ENTRE_MUESTRAS 300
#define LM35_MAX_RAZONABLE 50.0f
#define WIFI_SSID "TU_RED"
#define WIFI_PASS "TU_CLAVE"
#define ZONA_HORARIA "<-03>3"

static_assert(N_SALIDAS == 4, "Revisar clases y LEDs para este modelo");
#if USA_PERIODO
static_assert(N_ENTRADAS == 7, "Se esperan 4 sensores y 3 columnas de periodo");
static_assert(COL_MANANA >= 4 && COL_MANANA < N_ENTRADAS &&
              COL_TARDE >= 4 && COL_TARDE < N_ENTRADAS &&
              COL_NOCHE >= 4 && COL_NOCHE < N_ENTRADAS &&
              COL_MANANA != COL_TARDE && COL_MANANA != COL_NOCHE &&
              COL_TARDE != COL_NOCHE, "Columnas de periodo invalidas");
#else
static_assert(N_ENTRADAS == 4, "Se esperan humedad_tierra, luz, humedad_aire, temp_promedio");
#endif

DHT dht(PIN_DHT11, DHT11);
WebServer servidor(80);
int claseLED = -1;
unsigned long ultimoIntentoWifi = 0;
bool wifiAnterior = false;
String lineaSerial;

// Declaraciones explicitas: evita problemas del preprocesador de Arduino
// con tipos definidos por el sketch.
struct Medicion {
  float x[N_ENTRADAS] = {};
  float tempDHT = NAN;
  float tempLM = NAN;
  int validasDHT = 0;
  int validasLM = 0;
  bool lmSospechoso = false;
  time_t instante = 0;
};
bool leerSensores(Medicion& m, String& error);
void completarRespuesta(JsonDocument& doc, const Medicion& m,
                       int clase, const float* prob, unsigned long duracion);
void actualizarLEDs();
int clasificar(const float* xraw, float* prob);

bool relojListo() {
  return time(nullptr) >= 1577836800; // 2020-01-01 UTC
}

int horaActual() {
  if (!relojListo()) return -1;
  time_t ahora = time(nullptr);
  struct tm local;
  localtime_r(&ahora, &local);
  return local.tm_hour;
}

void mostrarHora() {
  Serial.println("Hora local: " + String(horaActual()) + " (UTC-3; -1 = sin hora)");
}

void enviarJSON(int codigo, const JsonDocument& doc) {
  String cuerpo;
  serializeJson(doc, cuerpo);
  servidor.sendHeader("Cache-Control", "no-store");
  servidor.send(codigo, "application/json; charset=utf-8", cuerpo);
}

void enviarError(int codigo, const char* tipo, const String& mensaje) {
  JsonDocument doc;
  doc["ok"] = false;
  doc["error"] = tipo;
  doc["mensaje"] = mensaje;
  enviarJSON(codigo, doc);
}

// NTP es opcional. El backend puede proporcionar la hora en cada llamada.
bool recibirHora() {
  String cuerpo = servidor.arg("plain");
  if (cuerpo.length() == 0) return true;
  if (cuerpo.length() > 256) {
    enviarError(413, "cuerpo_grande", "Enviar como maximo 256 bytes.");
    return false;
  }
  JsonDocument doc;
  if (deserializeJson(doc, cuerpo) || !doc.is<JsonObject>()) {
    enviarError(400, "json_invalido", "Se espera un objeto JSON.");
    return false;
  }
  if (doc["timestamp_unix"].isNull()) return true;
  if (!doc["timestamp_unix"].is<int64_t>()) {
    enviarError(400, "hora_invalida", "timestamp_unix debe ser un entero en segundos UTC.");
    return false;
  }
  int64_t segundos = doc["timestamp_unix"].as<int64_t>();
  if (segundos < 1577836800LL || segundos > 4102444799LL) {
    enviarError(400, "hora_invalida", "Se espera una fecha entre 2020 y 2099, en segundos.");
    return false;
  }
  struct timeval tv = {};
  tv.tv_sec = static_cast<time_t>(segundos);
  if (settimeofday(&tv, nullptr) != 0) {
    enviarError(500, "reloj", "No se pudo configurar el reloj.");
    return false;
  }
  return true;
}

bool leerSensores(Medicion& m, String& error) {
#if USA_PERIODO
  if (!relojListo()) {
    error = "Modelo con periodo: enviar timestamp_unix o esperar sincronizacion NTP.";
    return false;
  }
#endif
  m.instante = relojListo() ? time(nullptr) : 0;
  float tierra = 0, luz = 0, hum = 0, tdht = 0, tlm = 0;
  for (int i = 0; i < MUESTRAS; i++) {
    tierra += analogRead(PIN_HUMEDAD_TIERRA);
    luz += analogRead(PIN_LUZ);
    // DHT reutiliza su lectura interna entre actualizaciones. Se mantiene
    // el promedio original: 30 llamadas no son 30 lecturas DHT independientes.
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (isfinite(h) && isfinite(t)) {
      hum += h; tdht += t; m.validasDHT++;
    }
    float lm = analogReadMilliVolts(PIN_LM35) / 10.0f;
    if (isfinite(lm) && lm >= -10 && lm <= 80) {
      tlm += lm; m.validasLM++;
    }
    actualizarLEDs();
    delay(DELAY_ENTRE_MUESTRAS);
  }
  if (m.validasDHT == 0) {
    error = "El DHT11 no devolvio lecturas validas.";
    return false;
  }
  m.tempDHT = tdht / m.validasDHT;
  float promedio = m.tempDHT;
  if (m.validasLM > 0) {
    m.tempLM = tlm / m.validasLM;
    m.lmSospechoso = m.tempLM > LM35_MAX_RAZONABLE;
    promedio = (m.tempDHT + m.tempLM) / 2.0f;
  }
  // NO cambiar este orden sin reexportar el modelo entrenado.
  m.x[0] = tierra / MUESTRAS;
  m.x[1] = luz / MUESTRAS;
  m.x[2] = hum / m.validasDHT;
  m.x[3] = promedio;
#if USA_PERIODO
  struct tm local;
  localtime_r(&m.instante, &local);
  int h = local.tm_hour;
  m.x[COL_MANANA] = h < 12 ? 1.0f : 0.0f;
  m.x[COL_TARDE] = h >= 12 && h < 18 ? 1.0f : 0.0f;
  m.x[COL_NOCHE] = h >= 18 ? 1.0f : 0.0f;
#endif
  return true;
}

void completarRespuesta(JsonDocument& doc, const Medicion& m,
                       int clase, const float* prob, unsigned long duracion) {
  doc["ok"] = true;
  doc["clase"] = clase;
  doc["estado"] = NOMBRES_CLASE[clase];
  doc["confianza"] = prob[clase]; // 0..1, no porcentaje ni garantia de acierto
  if (m.instante) doc["timestamp_unix"] = static_cast<int64_t>(m.instante);
  else doc["timestamp_unix"] = nullptr;
  doc["duracion_ms"] = duracion;
  doc["muestras"] = MUESTRAS;
  doc["datos"]["humedad_tierra"] = m.x[0];
  doc["datos"]["luz"] = m.x[1];
  doc["datos"]["humedad_aire"] = m.x[2];
  doc["datos"]["temp_promedio"] = m.x[3];
  doc["datos"]["temp_dht11"] = m.tempDHT;
  if (m.validasLM) doc["datos"]["temp_lm35"] = m.tempLM;
  else doc["datos"]["temp_lm35"] = nullptr;
#if USA_PERIODO
  doc["datos"]["periodo"] = m.x[COL_MANANA] > 0 ? "Manana" :
                              (m.x[COL_TARDE] > 0 ? "Tarde" : "Noche");
#else
  doc["datos"]["periodo"] = nullptr;
#endif
  JsonArray probabilidades = doc["probabilidades"].to<JsonArray>();
  for (int k = 0; k < N_SALIDAS; k++) {
    JsonObject p = probabilidades.add<JsonObject>();
    p["clase"] = k;
    p["estado"] = NOMBRES_CLASE[k];
    p["probabilidad"] = prob[k];
  }
  doc["calidad"]["llamadas_dht_validas"] = m.validasDHT;
  doc["calidad"]["lecturas_lm35_validas"] = m.validasLM;
  doc["calidad"]["lm35_sospechoso"] = m.lmSospechoso;
  doc["calidad"]["solo_dht_para_temperatura"] = m.validasLM == 0;
}

void atenderMedicion() {
  if (!recibirHora()) return;
#if USA_PERIODO
  if (!relojListo()) {
    enviarError(503, "hora_no_disponible", "Enviar timestamp_unix para calcular el periodo.");
    return;
  }
#endif
  unsigned long inicio = millis();
  Medicion m;
  String error;
  if (!leerSensores(m, error)) {
    claseLED = -1;
    actualizarLEDs();
    enviarError(503, "sensor_no_disponible", error);
    return;
  }
  float prob[N_SALIDAS];
  int clase = clasificar(m.x, prob);
  for (int k = 0; k < N_SALIDAS; k++) {
    if (!isfinite(prob[k])) {
      claseLED = -1;
      actualizarLEDs();
      enviarError(500, "inferencia_invalida", "Revisar entradas y modelo.h.");
      return;
    }
  }
  claseLED = clase;
  actualizarLEDs();
  JsonDocument doc;
  completarRespuesta(doc, m, clase, prob, millis() - inicio);
  enviarJSON(200, doc);
  Serial.println("Medicion HTTP -> " + String(NOMBRES_CLASE[clase]));
}

void atenderSalud() {
  JsonDocument doc;
  doc["ok"] = true;
  doc["ip"] = WiFi.localIP().toString();
  doc["hora_disponible"] = relojListo();
  doc["usa_periodo"] = bool(USA_PERIODO);
  doc["uptime_ms"] = millis();
  enviarJSON(200, doc);
}

void predecirUna() {
  Medicion m;
  String error;
  if (!leerSensores(m, error)) { Serial.println(error); return; }
  float prob[N_SALIDAS];
  int clase = clasificar(m.x, prob);
  claseLED = clase;
  actualizarLEDs();
  Serial.println("Estado: " + String(NOMBRES_CLASE[clase]) +
                 " | probabilidad: " + String(prob[clase], 4));
}

// El forward pass y VERIFICAR se conservan del firmware original.

void actualizarLEDs() {
  bool parpadeo = (millis() / 400) % 2;
  digitalWrite(LED_VERDE,    claseLED == 0);
  digitalWrite(LED_AMARILLO, claseLED == 1);
  digitalWrite(LED_ROJO,     claseLED == 2 || (claseLED == 3 && parpadeo));
}

void probarLEDs() {
  int pines[3] = {LED_VERDE, LED_AMARILLO, LED_ROJO};
  for (int i = 0; i < 3; i++) {
    digitalWrite(pines[i], HIGH); delay(400); digitalWrite(pines[i], LOW);
  }
}


int clasificar(const float* xraw, float* prob) {
  float x[N_ENTRADAS];
  for (int i = 0; i < N_ENTRADAS; i++) x[i] = xraw[i] * ESC_SCALE[i] + ESC_MIN[i];

  float h[N_OCULTAS];
  for (int j = 0; j < N_OCULTAS; j++) {
    float s = BIAS1[j];
    for (int i = 0; i < N_ENTRADAS; i++) s += x[i] * W1[i][j];
    h[j] = (s > 0) ? s : 0;                     // ReLU
  }

  float z[N_SALIDAS], zmax = -1e30f;
  for (int k = 0; k < N_SALIDAS; k++) {
    float s = BIAS2[k];
    for (int j = 0; j < N_OCULTAS; j++) s += h[j] * W2[j][k];
    z[k] = s;
    if (s > zmax) zmax = s;
  }

  float suma = 0;                                // softmax (restar el maximo evita overflow)
  for (int k = 0; k < N_SALIDAS; k++) { prob[k] = expf(z[k] - zmax); suma += prob[k]; }
  int mejor = 0;
  for (int k = 0; k < N_SALIDAS; k++) {
    prob[k] /= suma;
    if (prob[k] > prob[mejor]) mejor = k;
  }
  return mejor;
}


void verificar() {
  Serial.println();
  Serial.println("=== VERIFICACION contra sklearn (" + String(N_TEST) + " vectores) ===");
  int iguales = 0;
  float maxDif = 0;
  for (int n = 0; n < N_TEST; n++) {
    float prob[N_SALIDAS];
    int c = clasificar(TEST_X[n], prob);
    float difFila = 0;
    for (int k = 0; k < N_SALIDAS; k++) {
      float d = fabsf(prob[k] - TEST_P[n][k]);
      if (d > difFila) difFila = d;
    }
    if (difFila > maxDif) maxDif = difFila;
    bool ok = (c == TEST_Y[n]);
    if (ok) iguales++;
    Serial.println("  #" + String(n) + "  placa: " + String(NOMBRES_CLASE[c]) + " | sklearn: " + String(NOMBRES_CLASE[TEST_Y[n]]) +
                   " | dif prob max: " + String(difFila, 6) + (ok ? "  OK" : "  <-- DIFIERE"));
  }
  Serial.println("Coinciden " + String(iguales) + " de " + String(N_TEST) + " | diferencia maxima de probabilidad: " + String(maxDif, 6));
  Serial.println(iguales == N_TEST ? "RESULTADO: la implementacion en C es equivalente al modelo de sklearn." : "RESULTADO: HAY DIFERENCIAS, revisar escalado o pesos.");
}

void setup() {
  Serial.begin(115200); // No esperar un monitor Serial para arrancar.
  dht.begin();
  analogReadResolution(12); // ADC crudo 0..4095, como el entrenamiento.
  analogSetAttenuation(ADC_11db);
  pinMode(LED_ROJO, OUTPUT);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  probarLEDs();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  ultimoIntentoWifi = millis();
  // Se inicia la sincronizacion en segundo plano, sin bloquear el arranque
  // ni pedir datos por Serial si la red no tiene salida a internet.
  configTzTime(ZONA_HORARIA, "pool.ntp.org", "time.google.com");
  servidor.on("/api/medir", HTTP_POST, atenderMedicion);
  servidor.on("/api/salud", HTTP_GET, atenderSalud);
  servidor.onNotFound([]() {
    enviarError(404, "ruta_no_encontrada", "Usar POST /api/medir o GET /api/salud.");
  });
  servidor.begin();
  Serial.println("\nCebollita HTTP iniciada. Esperando Wi-Fi...");
  Serial.println("Configurar WIFI_SSID y WIFI_PASS antes de usar.");
  Serial.println("Serial: UNA | VERIFICAR | LEDS | HORA | IP");
}

void loop() {
  actualizarLEDs();
  bool conectado = WiFi.status() == WL_CONNECTED;
  if (conectado && !wifiAnterior) {
    Serial.println("IP de la ESP32: " + WiFi.localIP().toString());
    Serial.println("POST http://" + WiFi.localIP().toString() + "/api/medir");
  }
  wifiAnterior = conectado;
  if (!conectado && millis() - ultimoIntentoWifi >= 15000UL) {
    ultimoIntentoWifi = millis();
    WiFi.reconnect();
  }
  if (conectado) servidor.handleClient();

  // Parser Serial sin readStringUntil: una linea incompleta no bloquea HTTP.
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      lineaSerial.trim();
      lineaSerial.toUpperCase();
      if (lineaSerial == "UNA") predecirUna();
      else if (lineaSerial == "VERIFICAR") verificar();
      else if (lineaSerial == "LEDS") probarLEDs();
      else if (lineaSerial == "HORA") mostrarHora();
      else if (lineaSerial == "IP") Serial.println(WiFi.localIP());
      else if (lineaSerial.length()) Serial.println("Comando desconocido.");
      lineaSerial = "";
    } else if (lineaSerial.length() < 80) {
      lineaSerial += c;
    }
  }
  delay(2);
}


