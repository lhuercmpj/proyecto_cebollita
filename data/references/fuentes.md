# Fuentes del RAG de Cebollita

Especie: *Fittonia albivenis* (fitonia, planta nervio o planta mosaico), según el tablero del grupo. Confirmar si la planta es del grupo Argyroneura (nervadura blanca) o Verschaffeltii (nervadura roja/rosada): los cuidados son los mismos.

Cada archivo `.md` de esta carpeta es un **resumen propio en español** de la fuente indicada en su encabezado (no una copia del texto original). El encabezado conserva título, institución, URL y fecha de consulta para poder citar de dónde sale cada recomendación.

| Archivo | Fuente | Institución | Consultado |
| --- | --- | --- | --- |
| `ncsu-extension-fittonia-albivenis.md` | North Carolina Extension Gardener Plant Toolbox | NC State University Extension | 2026-11-08 |
| `ufifas-fittonia-production-guide.md` | Fittonia Production Guide (RH-91-17) | University of Florida, IFAS | 2026-11-08 |
| `rhs-how-to-grow-fittonia.md` | How to grow fittonia | Royal Horticultural Society | 2026-11-08 |
| `rhs-fittonia-argyroneura-group.md` | Ficha Fittonia albivenis Argyroneura Group | Royal Horticultural Society | 2026-11-08 |
| `kew-powo-fittonia-albivenis.md` | Plants of the World Online | Royal Botanic Gardens, Kew | 2026-11-08 |
| `nparks-fittonia-albivenis.md` | Flora & Fauna Web | National Parks Board, Singapur | 2026-11-08 |
| `guia-sensores-cebollita.md` | Documentación interna del proyecto | Grupo del proyecto | 2026-11-08 |

Para indexar (requiere `GEMINI_API_KEY`):

```powershell
docker compose run --rm api python -m src.rag.ingest
```

`fuentes.md` y `que_va_aca.md` no se indexan.
