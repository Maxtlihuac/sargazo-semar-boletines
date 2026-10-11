# Diccionario de datos

## `boletines_diarios.csv` (una fila por boletín)

| Columna | Tipo | Descripción |
|---|---|---|
| `fecha` | fecha (AAAA-MM-DD) | Fecha del boletín, tomada del nombre del archivo |
| `boletin` | entero | Número de boletín del IOGMC |
| `archivo_pdf` | texto | Nombre del PDF de origen |
| `toneladas_caribe_mexicano` | número | Toneladas estimadas de sargazo en el Caribe mexicano. Composición satelital de 7 días (USF, AFAI) |
| `qc_toneladas` | texto | `sospechoso`: cambia más de 8× respecto a sus vecinos (probable error de extracción). `sin_dato`: el boletín no trae el valor |
| `toneladas_caribe_central` | número | Toneladas en el Caribe central (desde abr-2025) |
| `toneladas_caribe_oriental` | número | Toneladas en el Caribe oriental, al oeste de las Antillas Menores (desde abr-2025) |
| `toneladas_atlantico_central_occ` | número | Toneladas en el Atlántico central occidental (desde abr-2025) |
| `toneladas_zee` | número | Toneladas en la Zona Económica Exclusiva (mar–jun 2025) |
| `cobertura_zee_pct` | número | Porcentaje de cobertura en la ZEE (mar–jun 2025) |
| `pronostico_ingreso_costa_ton` | número | Toneladas que el boletín pronostica que ingresarán a costa (abr–sep 2023) |
| `semaforo` | texto | Nivel del semáforo regional tal como aparece en el boletín |
| `semaforo_nivel` | entero 1–8 | Semáforo en escala ordinal (ver abajo) |
| `categoria_boletin` | entero | Categoría numérica cuando el boletín la reporta |
| `menciona_nubosidad` | 0/1 | El boletín menciona nubosidad |
| `dato_arrastrado_por_nubes` | 0/1 | El boletín declara que la nubosidad impidió estimar y se usó una cifra previa |
| `nubosidad_min_pct`, `nubosidad_max_pct` | número | Rango de nubosidad cuando se reporta (ej. 55–85%) |
| `n_conglomerados` | entero | Número de conglomerados de sargazo listados cerca de la costa |

## `niveles_por_zona.csv` (una fila por zona y día)

| Columna | Descripción |
|---|---|
| `fecha`, `boletin` | Fecha y número del boletín |
| `zona` | Sur (Xcalak a Sian Ka'an), Centro (Tulum a Playa del Carmen y Cozumel), Norte (Puerto Morelos a Cancún e Isla Mujeres) |
| `nivel_texto` | Nivel tal como aparece (ej. "De moderado a alto") |
| `nivel_min`, `nivel_max` | Extremos del rango en la escala 1–8 |
| `qc_nivel` | `rango_incompleto` cuando el texto quedó truncado (ej. "De alto") |

## Escala de alertamiento (reconstruida)

| Nivel | Nombre |
|---|---|
| 1 | Escaso |
| 2 | Muy bajo |
| 3 | Bajo |
| 4 | Moderado |
| 5 | Alto |
| 6 | Muy alto |
| 7 | Abundante |
| 8 | Excesivo |

Deducida de los pares categoría-semáforo que aparecen juntos en los boletines (por ejemplo, categoría 1 con "Escaso" en 194 boletines y categoría 8 con "Excesivo" en 3). No proviene de un documento oficial de SEMAR.
