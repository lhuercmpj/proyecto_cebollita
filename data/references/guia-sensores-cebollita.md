---
source_id: guia-sensores-cebollita
title: Cómo interpretar los sensores y el modelo de Cebollita
institution: Grupo del proyecto Maceta Inteligente (documentación interna)
url:
accessed: 2026-11-08
species: Fittonia albivenis
language_original: es
note: Documento interno basado en el README del repositorio y el firmware. Revisar si cambian los sensores o el modelo.
---

# Sensores de la maceta

La maceta usa una ESP32 con cuatro sensores. Cada medición promedia 30 muestras tomadas durante unos 9 segundos.

- Humedad de la tierra: sensor analógico con lectura cruda del conversor de la ESP32, en escala de 0 a 4095. No está calibrado como porcentaje, así que no debe expresarse como "% de humedad del suelo". Lo que importa es comparar con lecturas anteriores y con lo que el modelo aprendió.
- Luz: sensor analógico, también en escala cruda de 0 a 4095 y sin calibrar en lux. Según la documentación del proyecto, el sensor de luz actual aumenta su lectura cuando hay MENOS luz (más oscuro = número más alto). Hay que tenerlo en cuenta antes de decir si hay mucha o poca luz.
- Humedad del aire: sensor DHT11, en porcentaje de humedad relativa (0 a 100 %).
- Temperatura: se mide con dos sensores (DHT11 y LM35) y se usa el promedio de ambos, en grados Celsius.

# Modelo predictivo (Tarea 2)

Una red neuronal pequeña (4 entradas, 16 neuronas ocultas, 4 salidas) clasifica cada medición en uno de cuatro estados: "Estoy bien", "Preciso luz", "Preciso agua" o "Estoy mal". Usa humedad de la tierra, luz, humedad del aire y temperatura promedio, en ese orden. La "confianza" es la probabilidad que el modelo asigna al estado elegido: no es una garantía de acierto.

El modelo corre en la placa y el backend lo vuelve a calcular para verificar que ambos coincidan. Las recomendaciones de riego del chatbot se basan en el estado que estima el modelo y en los cuidados de la especie, no en umbrales inventados.

# Mediciones automáticas

El backend pide una medición cada 30 minutos, la guarda en la base de datos y envía un reporte por Telegram. Si el estado es "Preciso agua", "Preciso luz" o "Estoy mal", también envía una alerta, sin repetirla en cada medición. Una lectura se considera atrasada si tiene más de 40 minutos (intervalo de 30 más 10 de margen).
