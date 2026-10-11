"""Convierte la salida cruda del extractor (datos/crudos/) en las tablas publicadas (datos/).

    python preparar_datos.py
"""
import csv
import re
from datetime import date, timedelta
from pathlib import Path

CRUDOS = Path("datos/crudos")
SALIDA = Path("datos")

# Escala de alertamiento del IOGMC-SEMAR, reconstruida de los pares categoría-semáforo
# que aparecen juntos en los boletines (ver README).
ESCALA = {"escaso": 1, "muy bajo": 2, "bajo": 3, "moderado": 4, "alto": 5,
          "muy alto": 6, "abundante": 7, "excesivo": 8}
NIVELES_RX = r"(muy bajo|muy alto|escaso|bajo|moderado|alto|abundante|excesivo)"


def nivel_rango(texto):
    """'De moderado a alto' -> (4, 5); 'Bajo' -> (3, 3)."""
    encontrados = [ESCALA[n] for n in re.findall(NIVELES_RX, texto.lower())]
    if not encontrados:
        return None, None
    return min(encontrados), max(encontrados)


def num(x):
    return float(x) if x not in ("", None) else None


def boletines():
    with open(CRUDOS / "inventario.csv", encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f)]

    ton = {r["fecha"]: num(r["toneladas_cm"]) for r in filas if r["fecha"]}

    def sospechoso(fecha):
        """Valor aislado que cambia más de 8 veces respecto a sus vecinos con dato (hasta 3 días
        antes y después) en la misma dirección: casi siempre es un número mal extraído del PDF."""
        v = ton.get(fecha)
        if not v:
            return False
        d = date.fromisoformat(fecha)
        vecinos = []
        for signo in (-1, 1):  # vecino más cercano con dato, hasta 3 días antes o después
            for k in (1, 2, 3):
                x = ton.get((d + timedelta(days=signo * k)).isoformat())
                if x:
                    vecinos.append(x)
                    break
        if not vecinos:
            return False
        return all(v > 8 * x for x in vecinos) or all(v * 8 < x for x in vecinos)

    salida = []
    for r in sorted(filas, key=lambda r: (r["fecha"] or "9999", r["archivo"])):
        if r["sin_informacion"] == "1":
            continue  # páginas en blanco sin fecha: se reportan en el README
        nivel = ESCALA.get(r["semaforo"].lower()) if r["semaforo"] else None
        salida.append({
            "fecha": r["fecha"],
            "boletin": r["numero"],
            "archivo_pdf": r["archivo"],
            "toneladas_caribe_mexicano": r["toneladas_cm"],
            "qc_toneladas": "sospechoso" if sospechoso(r["fecha"]) else ("" if r["toneladas_cm"] else "sin_dato"),
            "toneladas_caribe_central": r["ton_cc"],
            "toneladas_caribe_oriental": r["ton_co"],
            "toneladas_atlantico_central_occ": r["ton_aco"],
            "toneladas_zee": r["toneladas_zee"],
            "cobertura_zee_pct": r["cobertura_zee_pct"],
            "pronostico_ingreso_costa_ton": r["pronostico_ingreso_ton"],
            "semaforo": r["semaforo"],
            "semaforo_nivel": nivel or "",
            "categoria_boletin": r["categoria"],
            "menciona_nubosidad": r["menciona_nubosidad"],
            "dato_arrastrado_por_nubes": r["dato_arrastrado"],
            "nubosidad_min_pct": r["nubosidad_min_pct"],
            "nubosidad_max_pct": r["nubosidad_max_pct"],
            "n_conglomerados": r["n_conglomerados"],
        })
    with open(SALIDA / "boletines_diarios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(salida[0]))
        w.writeheader()
        w.writerows(salida)
    return salida


def zonas():
    with open(CRUDOS / "zonas.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    salida = []
    for r in filas:
        lo, hi = nivel_rango(r["nivel"])
        incompleto = bool(re.fullmatch(r"de\s+\w+(\s+\w+)?", r["nivel"].strip().lower())) and " a " not in r["nivel"].lower()
        salida.append({
            "fecha": r["fecha"], "boletin": r["numero"], "zona": r["zona"],
            "nivel_texto": r["nivel"], "nivel_min": lo or "", "nivel_max": hi or "",
            "qc_nivel": "rango_incompleto" if incompleto else "",
        })
    with open(SALIDA / "niveles_por_zona.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(salida[0]))
        w.writeheader()
        w.writerows(salida)
    return salida


if __name__ == "__main__":
    b = boletines()
    z = zonas()
    print(f"boletines_diarios.csv: {len(b)} filas; sospechosos: {sum(1 for x in b if x['qc_toneladas']=='sospechoso')}")
    print(f"niveles_por_zona.csv: {len(z)} filas; rangos incompletos: {sum(1 for x in z if x['qc_nivel'])}")
