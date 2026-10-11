# Boletines diarios de sargazo de SEMAR, 2023–2026, en tabla

Este repositorio convierte en datos tabulares los **1,053 boletines diarios** que el Instituto Oceanográfico del Golfo y Mar Caribe de la Secretaría de Marina (IOGMC-SEMAR) publica en PDF sobre el sargazo en el Caribe mexicano, del 12 de enero de 2023 al 9 de octubre de 2026.

Hasta ahora esa información solo existía como un PDF por día, con cinco formatos distintos a lo largo del tiempo. Aquí queda en dos tablas listas para análisis, con el código para reproducirlas y una revisión de lo que los datos permiten y no permiten concluir.

**Autor:** Maximiliano Macías Herrera, Ingeniería Industrial, UNAM.
**Fuente original:** [Boletines diarios de sargazo, SEMAR](https://diredimoat.semar.gob.mx/OpSargazo/SargazoBoletinDiario.html).

---

## Qué contiene

| Archivo | Descripción |
|---|---|
| [`datos/boletines_diarios.csv`](datos/boletines_diarios.csv) | Una fila por boletín: toneladas estimadas, semáforo, regiones río arriba, nubosidad, conglomerados |
| [`datos/niveles_por_zona.csv`](datos/niveles_por_zona.csv) | Nivel de arribo por zona (Sur, Centro, Norte) y día, abr-2023 a oct-2024 |
| [`datos/diccionario.md`](datos/diccionario.md) | Definición de cada columna y de la escala de alertamiento |
| `sargazo_semar.py` | Descarga los PDF, corrige enlaces rotos y extrae los campos |
| `preparar_datos.py` | Limpia la extracción y genera las tablas publicadas |
| `figuras.py` | Genera las figuras y la prueba de anticipación de este README |

### Cobertura

| Campo | Boletines con el dato |
|---|---|
| Toneladas en el Caribe mexicano | 913 |
| Semáforo regional (escala de 8 niveles) | 943 |
| Toneladas por región río arriba (Caribe central, oriental y Atlántico) | 441 (abr-2025 en adelante) |
| Nivel por zona Sur / Centro / Norte | 376 días completos (abr-2023 a oct-2024) |
| Pronóstico de toneladas que ingresan a costa | 154 (abr–sep 2023) |
| Nota de cifra arrastrada por nubosidad | 47 |

![Cobertura por campo y mes](figuras/2_cobertura.png)

El archivo en línea cubre enero–octubre de 2023, marzo–octubre de 2024, marzo–diciembre de 2025 y enero–octubre de 2026. La numeración de los boletines (el del 12-ene-2023 es el núm. 491) indica que existen boletines anteriores que no están publicados.

---

## Hallazgos

### 1. El tamaño de la temporada cambia mucho de un año a otro

El máximo diario estimado fue de 28,441 t en 2023, 13,208 t en 2024, 82,699 t en 2025 y 90,538 t en 2026.

![Temporadas 2023–2026](figuras/1_temporadas.png)

### 2. La censura por nubes está documentada en el propio boletín

Cuando la nubosidad impide estimar el sargazo, el boletín lo declara y usa la cifra de un día anterior. En 2024 ocurrió en 44 días, concentrados entre junio y septiembre. Esos días quedan marcados en la columna `dato_arrastrado_por_nubes`: la serie oficial no es una medición diaria independiente en esos periodos.

![Días con cifra arrastrada en 2024](figuras/3_censura_nubes_2024.png)

### 3. El nivel de arribo por zona es muy persistente

Entre abril de 2023 y octubre de 2024, el nivel reportado cambió entre 28 y 40 veces por zona en ~380 días. "Mañana igual que hoy" acierta casi siempre, lo que fija una línea base muy exigente para cualquier pronóstico de corto plazo. SEMAR dejó de publicar este nivel por zona a partir de 2025.

![Nivel por zona](figuras/4_niveles_por_zona.png)

### 4. Las regiones río arriba no anticipan al Caribe mexicano (resultado negativo)

Se probó si las toneladas del Caribe central y oriental mejoran el pronóstico del Caribe mexicano a 28, 42 y 56 días, frente a usar solo el Caribe mexicano. La regla se fijó antes de ver los datos: la mejora debía ser de al menos 10%.

| Días adelante | Persistencia | Solo Caribe mexicano | Con Caribe central y oriental | Mejora |
|---|---|---|---|---|
| 28 | 0.649 | 0.843 | 0.717 | −10% |
| 42 | 0.586 | 1.459 | 1.397 | −139% |
| 56 | 0.825 | 2.118 | 1.960 | −137% |

*Error absoluto medio en log(1 + toneladas). Entrenamiento con 2025, evaluación con 2026.*

No pasa. Los modelos entrenados con la temporada 2025 fallan en la de 2026, que fue mucho mayor: con año y medio de datos regionales no es posible estimar una relación estable.

![Anticipación por región](figuras/5_anticipacion.png)

El Atlántico central occidental muestra correlaciones altas a 28–56 días, pero **no se probó fuera de muestra** y puede reflejar solo el ciclo estacional compartido. Queda como hipótesis para evaluar con la temporada 2027.

---

## Limitaciones

- **Son evaluaciones de SEMAR, no mediciones independientes.** Las toneladas salen de la composición satelital de 7 días de la Universidad del Sur de Florida (índice AFAI); el semáforo y el nivel por zona combinan esas toneladas, corrientes, vientos y fotografías diarias de playas de la ZOFEMAT de Quintana Roo.
- **Errores de extracción.** Cuatro valores de toneladas que cambian más de 8 veces respecto a sus vecinos están marcados como `sospechoso` y se excluyen de las figuras. Seis niveles por zona con rango incompleto ("De alto") están marcados en `qc_nivel`.
- **Huecos.** Unos 56 boletines no existen en el servidor con ningún nombre probado (sobre todo 11–31 oct 2024 y 14–21 mar 2026). Nueve PDF sin texto ni fecha (`SIN_INFORMACION_*.pdf`) se excluyeron.
- **Escala de alertamiento reconstruida.** El orden de 1 a 8 (Escaso, Muy bajo, Bajo, Moderado, Alto, Muy alto, Abundante, Excesivo) se dedujo de los pares categoría-semáforo que aparecen juntos en los boletines; no proviene de un documento oficial.

## Reproducir

```bash
pip install requests beautifulsoup4 pdfplumber matplotlib
python sargazo_semar.py descargar     # ~1,100 PDF, ~30 min
python sargazo_semar.py recuperar     # corrige enlaces mal escritos en la página de SEMAR
python sargazo_semar.py inventario    # extrae los campos a inventario.csv y zonas.csv
# copiar inventario.csv y zonas.csv a datos/crudos/
python preparar_datos.py
python figuras.py
```

## Licencia y cita

- Código: MIT.
- Tablas derivadas: CC BY 4.0. Al usarlas, cita este repositorio **y** la fuente original (IOGMC-SEMAR).

> Macías Herrera, M. (2026). *Boletines diarios de sargazo de SEMAR, 2023–2026, en tabla* [Conjunto de datos y código]. GitHub.

Si trabajas en SEMAR, LANOT u otra institución y tienes registros de arribo por playa (por ejemplo, de ZOFEMAT o SIMSAR), me interesaría conversar: es el dato que permitiría validar pronósticos y decisiones operativas.
