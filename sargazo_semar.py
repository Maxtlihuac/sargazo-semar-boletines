"""
Boletines diarios de sargazo de SEMAR (Instituto Oceanográfico del Golfo y Mar Caribe).

Dos pasos, se corren por separado:

    python sargazo_semar.py descargar     # baja todos los PDFs a ./boletines
    python sargazo_semar.py recuperar     # reintenta los 404 corrigiendo errores en los nombres de SEMAR
    python sargazo_semar.py inventario    # lee los PDFs y genera inventario.csv, zonas.csv y un resumen
    python sargazo_semar.py prueba        # ¿las regiones río arriba anticipan al Caribe mexicano?

Requisitos (una vez):
    pip install requests beautifulsoup4 pdfplumber

El inventario NO es todavía la base final: marca qué secciones trae cada boletín
para decidir si alcanza para validar. Las cifras extraídas deben revisarse
contra algunos PDFs antes de usarlas en un modelo.
"""

import csv
import re
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

PAGINA = "https://diredimoat.semar.gob.mx/OpSargazo/SargazoBoletinDiario.html"
CARPETA = Path("boletines")
PAUSA_SEG = 1.0  # pausa entre descargas para no saturar el servidor de SEMAR

MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
}
# "Muy ..." va primero para que no se quede solo con "Bajo"/"Alto".
NIVEL = r"(?:Muy\s+bajo|Muy\s+alto|Escaso|Bajo|Moderado|Medio|Abundante|Alto|Excesivo|Nulo)"
NIVELES = rf"((?:de\s+)?{NIVEL}(?:\s+a\s+{NIVEL})?)"


# ---------------------------------------------------------------- descarga

def descargar():
    import requests
    from bs4 import BeautifulSoup

    CARPETA.mkdir(exist_ok=True)
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "Mozilla/5.0 (investigacion academica UNAM)"

    html = sesion.get(PAGINA, timeout=60).text
    sopa = BeautifulSoup(html, "html.parser")
    enlaces = sorted({
        urljoin(PAGINA, a["href"])
        for a in sopa.find_all("a", href=True)
        if a["href"].lower().endswith(".pdf") and "BoletinesDiarios" in a["href"]
    })
    print(f"Enlaces a PDF encontrados en la página: {len(enlaces)}")

    fallos = []
    nuevos = 0
    for i, url in enumerate(enlaces, 1):
        destino = CARPETA / Path(url).name
        if destino.exists() and destino.stat().st_size > 0:
            continue
        try:
            r = sesion.get(url, timeout=120)
            # Los espacios reservados para días futuros no tienen archivo todavía.
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                fallos.append((url, f"HTTP {r.status_code}"))
                continue
            destino.write_bytes(r.content)
            nuevos += 1
            print(f"[{i}/{len(enlaces)}] {destino.name}")
        except Exception as e:  # red, SSL, tiempo de espera
            fallos.append((url, repr(e)))
        time.sleep(PAUSA_SEG)

    with open("fallos_descarga.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "motivo"])
        w.writerows(fallos)
    print(f"\nDescargados ahora: {nuevos}. Fallidos: {len(fallos)} (ver fallos_descarga.csv).")
    print("Es normal que fallen los días que todavía no se publican.")


# ---------------------------------------------------------------- recuperación

NOMBRE_MES = {v: k for k, v in MESES.items() if k != "SETIEMBRE"}


def recuperar():
    """Muchos 404 vienen de errores de captura en la página de SEMAR
    (carpeta "Abrilo" o "JJulio", día faltante, "_2026_2025", espacios, "-1").
    Para cada fallo arma nombres canónicos y los prueba."""
    import requests

    if not Path("fallos_descarga.csv").exists():
        sys.exit("No existe fallos_descarga.csv. Corre primero: python sargazo_semar.py descargar")

    # Número de boletín -> fecha, a partir de lo ya descargado, para inferir días faltantes.
    conocidos = {}
    for pdf in CARPETA.glob("*.pdf"):
        num, fecha = fecha_y_numero(pdf.name)
        if num and fecha:
            conocidos[num] = fecha

    def fecha_por_numero(num):
        if not conocidos:
            return None
        cercano = min(conocidos, key=lambda k: abs(k - num))
        from datetime import timedelta
        return conocidos[cercano] + timedelta(days=num - cercano)

    base = "https://diredimoat.semar.gob.mx/OpSargazo/BoletinesDiarios/"
    hoy = date.today()
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "Mozilla/5.0 (investigacion academica UNAM)"

    with open("fallos_descarga.csv", encoding="utf-8") as f:
        fallos = list(csv.DictReader(f))

    recuperados, sin_archivo = [], []
    for fallo in fallos:
        nombre = Path(fallo["url"]).name.upper().replace(" ", "").replace("-1.PDF", ".PDF")
        nombre = re.sub(r"_(\d{4})_\d{4}\.PDF$", r"_\1.PDF", nombre)
        m = re.match(r"SARGAZO_(\d+)_(?:(\d{1,2})_)?([A-ZÁÉÍÓÚ]+)_(\d{4})\.PDF", nombre)
        if not m:
            sin_archivo.append((fallo["url"], "nombre no reconocido"))
            continue
        num, dia, mes, anio = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
        candidatos = []
        if dia:
            try:
                candidatos.append((num, date(anio, MESES[mes], int(dia))))
            except (KeyError, ValueError):
                pass
        inferida = fecha_por_numero(num)
        if inferida and inferida.year == anio:
            candidatos.append((num, inferida))
        if dia and conocidos:  # número mal capturado (ej. 11043): inferirlo desde la fecha
            try:
                f_dia = date(anio, MESES[mes], int(dia))
                cercano = min(conocidos, key=lambda k: abs((conocidos[k] - f_dia).days))
                candidatos.append((cercano + (f_dia - conocidos[cercano]).days, f_dia))
            except (KeyError, ValueError):
                pass

        exito = False
        for n, f_c in dict.fromkeys(candidatos):
            if f_c > hoy:
                break
            if (CARPETA / f"SARGAZO_{n}_{f_c.day:02d}_{NOMBRE_MES[f_c.month]}_{f_c.year}.pdf").exists():
                exito = True
                break
            archivo = f"SARGAZO_{n}_{f_c.day:02d}_{NOMBRE_MES[f_c.month]}_{f_c.year}.pdf"
            url = base + NOMBRE_MES[f_c.month].capitalize() + "/" + archivo
            try:
                r = sesion.get(url, timeout=60)
                if r.status_code == 200 and r.content.startswith(b"%PDF"):
                    (CARPETA / archivo).write_bytes(r.content)
                    recuperados.append(archivo)
                    print("Recuperado:", archivo)
                    exito = True
                    break
            except Exception:
                pass
            time.sleep(PAUSA_SEG)
        if not exito:
            sin_archivo.append((fallo["url"], "no existe con ningún nombre probado"))

    with open("faltantes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url_original", "motivo"])
        w.writerows(sin_archivo)
    print(f"\nRecuperados: {len(recuperados)}. Siguen faltando: {len(sin_archivo)} (ver faltantes.csv).")
    print("Los días futuros siempre aparecerán como faltantes.")


# ---------------------------------------------------------------- extracción

def fecha_y_numero(nombre):
    """SARGAZO_491_12_ENERO_2023.pdf -> (491, date(2023,1,12))"""
    m = re.match(r"SARGAZO_(\d+)_(\d{1,2})_([A-ZÁÉÍÓÚ]+)_(\d{4})", nombre.upper())
    if not m:
        return None, None
    num, dia, mes, anio = m.groups()
    try:
        return int(num), date(int(anio), MESES[mes], int(dia))
    except (KeyError, ValueError):
        return int(num), None


def rx(patron):
    """Algunos PDFs pierden los espacios al extraer texto ("cantidadestimadade").
    Convierte cada espacio literal del patrón en espacio opcional."""
    return patron.replace(" ", r"\s*")


def numero(texto):
    return float(texto.replace(",", "").rstrip("."))


def nivel(texto):
    return re.sub(r"\s+", " ", texto).strip().capitalize()


def extraer(texto):
    t = re.sub(r"[ \t]+", " ", texto)
    r = {}

    # Toneladas en el Caribe Mexicano. Cada formato lo escribe distinto.
    patrones_ton = [
        r"cantidad (?:estimada|aproximada) de sargazo\s+de ([\d,\.]+)\s*Ton",   # 2023
        r"cobertura algal a la fecha de ([\d,\.]+)\s*Ton",                     # 2024
        r"Biomasa total en el Caribe Mexicano de ([\d,\.]+)",                   # 2026
        r"Biomasa total de ([\d,\.]+)\s*Ton",                                  # 2025-26
        r"Caribe Mexicano \(CM\)\s+([\d,\.]+)",                               # tablas 2025-26
    ]
    for p in patrones_ton:
        m = re.search(rx(p), t, re.I)
        if m:
            try:
                r["toneladas_cm"] = numero(m.group(1))
                break
            except ValueError:
                pass

    # Pronóstico de ingreso a costa (formato 2023).
    m = re.search(rx(r"ingresen a costas mexicanas un aproximado de ([\d,\.]+)\s*Ton"), t, re.I)
    if m:
        r["pronostico_ingreso_ton"] = numero(m.group(1))

    m = re.search(r"categor[ií]a\s*[“\"]?\s*(?:CAT-)?(\d)", t, re.I) or re.search(r"CAT-\s*(\d)", t)
    if m:
        r["categoria"] = int(m.group(1))

    # Semáforo regional.
    m = re.search(r"(\d)\s+" + NIVELES + r"\s+([\d,\.]+)\s*TON\.?\s+(\d{1,3})\s*%", t, re.I)   # 2025
    if m:
        r["categoria"] = r.get("categoria") or int(m.group(1))
        r["semaforo"] = nivel(m.group(2))
        r["toneladas_zee"] = numero(m.group(3))
        r["cobertura_zee_pct"] = int(m.group(4))
    if "semaforo" not in r:
        m = re.search(r"SEM[ÁA]FORO\s*\n\s*" + NIVELES + r"\s*$", t, re.I | re.M)
        if m:
            r["semaforo"] = nivel(m.group(1))
    if "semaforo" not in r:
        m = re.search(rx(r"denominaci[óo]n de") + r"\s*[“\"]" + NIVELES, t, re.I) or \
            re.search(r"CATEGOR[ÍI]A\s*[“\"]" + NIVELES, t, re.I)
        if m:
            r["semaforo"] = nivel(m.group(1))

    # Censura por nubes: SEMAR avisa cuando no puede estimar y arrastra un dato anterior.
    nubes = re.search(r"nubos", t, re.I)
    arrastre = re.search(rx(r"imposibilit|no (?:es )?confiable|se toma como base"), t, re.I)
    r["menciona_nubosidad"] = int(bool(nubes))
    r["dato_arrastrado"] = int(bool(nubes and arrastre))
    m = re.search(r"nubosidad[^%]{0,60}?\(?(\d{1,3})\s*(?:a|-|–)\s*(\d{1,3})\s*%", t, re.I)
    if m:
        r["nubosidad_min_pct"], r["nubosidad_max_pct"] = int(m.group(1)), int(m.group(2))

    # Nivel de recale por zona: tabla (2024) o prosa (2023).
    zonas = {}
    bloque = re.search(rx(r"IMPACTO DE RECALE") + r"(.{0,900})", t, re.I | re.S)
    if bloque:
        for zona in ("Sur", "Centro", "Norte"):
            m = re.search(rf"\b{zona}\b\s+{NIVELES}", bloque.group(1), re.I)
            if m:
                zonas[zona] = nivel(m.group(1))
    if len(zonas) < 3:
        for zona in ("sur", "centro", "norte"):
            m = re.search(rf"zona\s+{zona},?\s+{NIVELES}", t, re.I)
            if m:
                zonas[zona.capitalize()] = nivel(m.group(1))
    r["tiene_tabla_zonas"] = int(len(zonas) == 3)

    # Toneladas por región río arriba (formatos 2025-26).
    regiones = {
        "ton_cc": r"Caribe Central \(CC\)\s+([\d,\.]+)",
        "ton_co": r"Caribe Oriental \(al oeste de las Antillas Menores\)\s+([\d,\.]+)",
        "ton_aco": r"Atl[áa]ntico Central Occidental \(ACO\)\s+([\d,\.]+)",
    }
    for col, p in regiones.items():
        m = re.search(rx(p), t, re.I)
        if m:
            try:
                r[col] = numero(m.group(1))
            except ValueError:
                pass

    # Conglomerados: cuatro maneras de escribir la fila.
    patrones_cong = [
        r"^\s*\d{1,2}\s+[\d\.,]+\s+\d+\s+\d{1,2}\s*°",          # dic 2025: "1 14.4 97 19°.."
        r"^\s*\d{1,2}\s+[\d\.,]+\s+\d+\s*km\b",                 # 2026: "1 6 21 km"
        r"^\s*\d{1,2}\s+[\d\.,]+\s*Ton\s+\d+\s*Km",              # 2024: "1 7 Ton 40 Km al sureste.."
        r"^\s*\d{1,2}\s+[\d\.,]+\s*Ton\s+\d{1,2}\s*°",            # may 2025: "1 65 Ton 20°52'.."
    ]
    # El texto trae dos lecturas del PDF; se cuentan filas distintas para no duplicar.
    # Se cuentan números de conglomerado distintos (1, 2, 3...).
    n = max(len({int(x.split()[0]) for x in re.findall(p, t, re.M | re.I)}) for p in patrones_cong)
    r["n_conglomerados"] = n
    r["tiene_conglomerados"] = int(n > 0)

    return r, zonas


def inventario():
    import pdfplumber

    pdfs = sorted(CARPETA.glob("*.pdf"))
    if not pdfs:
        sys.exit("No hay PDFs en ./boletines. Corre primero: python sargazo_semar.py descargar")

    columnas = ["archivo", "numero", "fecha", "anio", "sin_informacion", "toneladas_cm",
                "pronostico_ingreso_ton", "ton_cc", "ton_co", "ton_aco", "toneladas_zee", "cobertura_zee_pct", "categoria", "semaforo",
                "menciona_nubosidad", "dato_arrastrado", "nubosidad_min_pct", "nubosidad_max_pct",
                "tiene_tabla_zonas", "tiene_conglomerados", "n_conglomerados", "error"]
    filas, filas_zonas = [], []

    for i, pdf in enumerate(pdfs, 1):
        num, fecha = fecha_y_numero(pdf.name)
        fila = {"archivo": pdf.name, "numero": num,
                "fecha": fecha.isoformat() if fecha else "",
                "anio": fecha.year if fecha else "",
                "sin_informacion": int(pdf.name.upper().startswith("SIN_INFORMACION"))}
        try:
            with pdfplumber.open(pdf) as doc:
                # Dos lecturas del mismo PDF: una conserva columnas (tablas), la otra los espacios (prosa).
                texto = "\n".join((p.extract_text(x_tolerance=1.5) or "") + "\n" +
                                  (p.extract_text(layout=True) or "") for p in doc.pages)
            datos, zonas = extraer(texto)
            fila.update(datos)
            for zona, nivel in zonas.items():
                filas_zonas.append({"fecha": fila["fecha"], "numero": num, "zona": zona, "nivel": nivel})
        except Exception as e:
            fila["error"] = repr(e)
        filas.append(fila)
        if i % 100 == 0:
            print(f"{i}/{len(pdfs)} leídos")

    with open("inventario.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)
    with open("zonas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fecha", "numero", "zona", "nivel"])
        w.writeheader()
        w.writerows(filas_zonas)

    # Resumen por año: cuántos boletines traen cada sección.
    por_anio = defaultdict(list)
    for fila in filas:
        por_anio[fila["anio"]].append(fila)
    campos = ["toneladas_cm", "semaforo", "ton_co", "dato_arrastrado", "tiene_tabla_zonas", "tiene_conglomerados"]
    print("\nAño   Boletines  " + "  ".join(f"{c:>18}" for c in campos))
    for anio in sorted(por_anio, key=str):
        grupo = por_anio[anio]
        conteos = []
        for c in campos:
            if c in ("dato_arrastrado", "tiene_tabla_zonas", "tiene_conglomerados"):
                conteos.append(sum(int(g.get(c) or 0) for g in grupo))
            else:
                conteos.append(sum(1 for g in grupo if g.get(c) not in (None, "")))
        print(f"{anio!s:<6}{len(grupo):>9}  " + "  ".join(f"{n:>18}" for n in conteos))
    errores = sum(1 for f in filas if f.get("error"))
    print(f"\nPDFs con error de lectura: {errores}")
    print("Listo: inventario.csv (uno por boletín) y zonas.csv (nivel de recale por zona y día).")


# ---------------------------------------------------------------- prueba de anticipación

def _ols(X, y):
    """Mínimos cuadrados con ecuaciones normales (sin numpy). X incluye la columna de 1s."""
    k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * yy for x, yy in zip(X, y)) for i in range(k)]
    for i in range(k):  # eliminación gaussiana con pivoteo
        piv = max(range(i, k), key=lambda r_: abs(A[r_][i]))
        A[i], A[piv], b[i], b[piv] = A[piv], A[i], b[piv], b[i]
        if abs(A[i][i]) < 1e-12:
            raise ValueError("matriz singular")
        for r_ in range(i + 1, k):
            f = A[r_][i] / A[i][i]
            A[r_] = [a - f * c for a, c in zip(A[r_], A[i])]
            b[r_] -= f * b[i]
    coef = [0.0] * k
    for i in reversed(range(k)):
        coef[i] = (b[i] - sum(A[i][j] * coef[j] for j in range(i + 1, k))) / A[i][i]
    return coef


def prueba():
    """Prueba preregistrada (versión B):
    ¿Las toneladas del Caribe oriental y central de hoy mejoran la predicción del
    Caribe mexicano a 28, 42 y 56 días frente a usar solo el Caribe mexicano de hoy?

    Entrenamiento: orígenes en 2025. Prueba: orígenes en 2026 (fuera de muestra).
    Métrica: error absoluto medio en log(1 + toneladas).
    Regla de muerte: si el modelo con regiones no reduce el error al menos 10%
    frente al modelo solo con el Caribe mexicano en 28-56 días, la versión B muere.
    """
    import math
    from datetime import timedelta

    if not Path("inventario.csv").exists():
        sys.exit("Falta inventario.csv. Corre primero: python sargazo_semar.py inventario")
    serie = {}
    with open("inventario.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if not fila["fecha"]:
                continue
            d = date.fromisoformat(fila["fecha"])
            serie[d] = {k: (math.log1p(float(fila[k])) if fila.get(k) not in (None, "") else None)
                        for k in ("toneladas_cm", "ton_cc", "ton_co", "ton_aco")}

    con_regiones = sorted(d for d, v in serie.items() if v["ton_co"] is not None and v["ton_cc"] is not None)
    if not con_regiones:
        sys.exit("Ningún boletín trae toneladas por región. Revisa la columna ton_co de inventario.csv.")
    print(f"Días con toneladas por región: {len(con_regiones)} ({con_regiones[0]} a {con_regiones[-1]})")
    por_mes = defaultdict(int)
    for d in con_regiones:
        por_mes[d.strftime("%Y-%m")] += 1
    print("Por mes:", ", ".join(f"{m}:{n}" for m, n in sorted(por_mes.items())))

    def corr(pares):
        if len(pares) < 10:
            return None
        a, b = zip(*pares)
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        sa = math.sqrt(sum((x - ma) ** 2 for x in a))
        sb = math.sqrt(sum((y - mb) ** 2 for y in b))
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else None

    print("\nCorrelación (log) entre la región hoy y el Caribe mexicano dentro de X días:")
    print(f"{'días':>5} {'CM→CM':>8} {'CC→CM':>8} {'CO→CM':>8} {'ACO→CM':>8}   n")
    for lag in (0, 7, 14, 21, 28, 35, 42, 49, 56, 70, 84):
        fila_txt, n = [], 0
        for col in ("toneladas_cm", "ton_cc", "ton_co", "ton_aco"):
            pares = [(serie[d][col], serie[d + timedelta(days=lag)]["toneladas_cm"])
                     for d in serie if serie[d][col] is not None
                     and (d + timedelta(days=lag)) in serie
                     and serie[d + timedelta(days=lag)]["toneladas_cm"] is not None]
            c = corr(pares)
            n = max(n, len(pares))
            fila_txt.append(f"{c:8.2f}" if c is not None else f"{'—':>8}")
        print(f"{lag:>5} " + " ".join(fila_txt) + f"  {n:>4}")

    print("\nPrueba fuera de muestra (entrena 2025, evalúa 2026). Error absoluto medio en log:")
    print(f"{'días':>5} {'n_ent':>6} {'n_prueba':>8} {'persistencia':>13} {'solo CM':>9} {'CM+CC+CO':>9} {'mejora':>8}  veredicto")
    resultados = []
    for h in (28, 42, 56):
        datos = []
        for d in con_regiones:
            obj = serie.get(d + timedelta(days=h))
            v = serie[d]
            if obj and obj["toneladas_cm"] is not None and v["toneladas_cm"] is not None:
                datos.append((d, v["toneladas_cm"], v["ton_cc"], v["ton_co"], obj["toneladas_cm"]))
        ent = [x for x in datos if x[0].year == 2025]
        pru = [x for x in datos if x[0].year == 2026]
        if len(ent) < 30 or len(pru) < 15:
            print(f"{h:>5} {len(ent):>6} {len(pru):>8}   datos insuficientes para evaluar")
            continue
        try:
            c0 = _ols([[1, x[1]] for x in ent], [x[4] for x in ent])
            c1 = _ols([[1, x[1], x[2], x[3]] for x in ent], [x[4] for x in ent])
        except ValueError:
            print(f"{h:>5}   no se pudo ajustar (regiones colineales); avísame")
            continue
        e_p = sum(abs(x[4] - x[1]) for x in pru) / len(pru)
        e_0 = sum(abs(x[4] - (c0[0] + c0[1] * x[1])) for x in pru) / len(pru)
        e_1 = sum(abs(x[4] - (c1[0] + c1[1] * x[1] + c1[2] * x[2] + c1[3] * x[3])) for x in pru) / len(pru)
        base = min(e_p, e_0)
        mejora = 1 - e_1 / base
        veredicto = "PASA" if mejora >= 0.10 else "NO PASA"
        resultados.append(veredicto)
        print(f"{h:>5} {len(ent):>6} {len(pru):>8} {e_p:>13.3f} {e_0:>9.3f} {e_1:>9.3f} {mejora:>7.0%}  {veredicto}")

    print()
    if not resultados:
        print("No hay datos suficientes para la prueba. Revisa en qué meses aparecen las regiones.")
    elif "PASA" in resultados:
        print("Las regiones río arriba aportan anticipación en al menos un horizonte: la versión B sigue.")
    else:
        print("Las regiones río arriba no mejoran 10% a la línea base: según la regla preregistrada, la versión B muere.")
    print("Ojo: es una sola temporada de prueba; un PASA es una señal, no una confirmación.")


if __name__ == "__main__":
    pasos = {"descargar": descargar, "recuperar": recuperar, "inventario": inventario, "prueba": prueba}
    if len(sys.argv) != 2 or sys.argv[1] not in pasos:
        sys.exit("Uso: python sargazo_semar.py [descargar|recuperar|inventario|prueba]")
    pasos[sys.argv[1]]()
