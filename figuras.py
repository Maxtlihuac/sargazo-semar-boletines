"""Genera las figuras del README y los números de la prueba de anticipación.

    python figuras.py      (requiere: pip install matplotlib)
"""
import csv
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import ListedColormap, BoundaryNorm

from sargazo_semar import _ols

FIG = Path("figuras")
FIG.mkdir(exist_ok=True)

# Paleta (validada: categórica de 4 posiciones en orden fijo; rampa secuencial azul)
SUP, TXT, TXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
AZUL = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#104281"]

plt.rcParams.update({
    "figure.facecolor": SUP, "axes.facecolor": SUP, "savefig.facecolor": SUP,
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": TXT2,
    "xtick.color": TXT2, "ytick.color": TXT2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 2, "lines.solid_capstyle": "round",
})


def titulo(ax, t, sub):
    ax.set_title(t, loc="left", fontsize=12.5, fontweight="bold", color=TXT, pad=26)
    ax.text(0, 1.035, sub, transform=ax.transAxes, fontsize=9.5, color=TXT2, va="bottom")


def fuente(fig, texto="Fuente: boletines diarios del IOGMC-SEMAR, 2023–2026. Elaboración propia."):
    fig.text(0.01, 0.01, texto, fontsize=8, color=TXT2)


def leer():
    with open("datos/boletines_diarios.csv", encoding="utf-8") as f:
        b = list(csv.DictReader(f))
    with open("datos/niveles_por_zona.csv", encoding="utf-8") as f:
        z = list(csv.DictReader(f))
    return b, z


def miles(x, _):
    return f"{x/1000:.0f}K" if x else "0"


# ---------------------------------------------------------------- 1. temporadas
def fig_temporadas(b):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    por_anio = defaultdict(dict)
    for r in b:
        if r["toneladas_caribe_mexicano"] and r["qc_toneladas"] != "sospechoso":
            d = date.fromisoformat(r["fecha"])
            por_anio[d.year][d] = float(r["toneladas_caribe_mexicano"])
    maximos = {}
    for i, anio in enumerate(sorted(por_anio)):
        serie = por_anio[anio]
        pico = max(serie.items(), key=lambda kv: kv[1])
        maximos[anio] = pico
        # media móvil centrada de 7 días (solo con al menos 4 días con dato)
        xs, ys, tramos = [], [], []
        for d in sorted(serie):
            ventana = [serie[d + timedelta(days=k)] for k in range(-3, 4) if (d + timedelta(days=k)) in serie]
            if len(ventana) < 4:
                continue
            if xs and (d - xs[-1]).days > 3:
                tramos.append((xs, ys)); xs, ys = [], []
            xs.append(d); ys.append(sum(ventana) / len(ventana))
        tramos.append((xs, ys))
        etiqueta = f"{anio}  (máx. diario {pico[1]:,.0f} t)"
        for k, (tx, ty) in enumerate(tramos):
            ax.plot([date(2000, d.month, d.day) for d in tx], ty, color=SERIES[i],
                    label=etiqueta if k == 0 else None)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(miles))
    ax.set_ylabel("Toneladas (media de 7 días)")
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    ax.set_ylim(0, None)
    titulo(ax, "El tamaño de la temporada varió casi 7 veces entre 2024 y 2026",
           "Sargazo estimado por SEMAR en el Caribe mexicano, media móvil de 7 días por día del año")
    fuente(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / "1_temporadas.png", dpi=160)
    plt.close(fig)
    return maximos


# ---------------------------------------------------------------- 2. cobertura
def fig_cobertura(b, z):
    campos = [
        ("Toneladas Caribe mexicano", lambda r: r["toneladas_caribe_mexicano"]),
        ("Semáforo regional", lambda r: r["semaforo"]),
        ("Nubosidad mencionada", lambda r: r["menciona_nubosidad"] == "1"),
        ("Pronóstico de ingreso a costa", lambda r: r["pronostico_ingreso_costa_ton"]),
        ("Cobertura en la ZEE (%)", lambda r: r["cobertura_zee_pct"]),
        ("Conglomerados", lambda r: r["n_conglomerados"] not in ("", "0")),
        ("Toneladas por región río arriba", lambda r: r["toneladas_caribe_oriental"]),
    ]
    zonas_dias = {r["fecha"] for r in z}
    meses = sorted({r["fecha"][:7] for r in b})
    por_mes = defaultdict(list)
    for r in b:
        por_mes[r["fecha"][:7]].append(r)
    filas = [nombre for nombre, _ in campos] + ["Nivel por zona (Sur/Centro/Norte)"]
    M = []
    for nombre, f in campos:
        M.append([sum(1 for r in por_mes[m] if f(r)) / len(por_mes[m]) for m in meses])
    M.append([sum(1 for r in por_mes[m] if r["fecha"] in zonas_dias) / len(por_mes[m]) for m in meses])

    fig, ax = plt.subplots(figsize=(10, 3.9))
    cmap = ListedColormap(["#efeeea"] + AZUL[1::2])
    norm = BoundaryNorm([0, 0.05, 0.35, 0.65, 0.95, 1.01], cmap.N)
    ax.imshow(M, aspect="auto", cmap=cmap, norm=norm)
    ax.set_yticks(range(len(filas)), filas, fontsize=9)
    idx = [i for i, m in enumerate(meses) if i == 0 or m[:4] != meses[i - 1][:4]]
    MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    ax.set_xticks(idx, [f"{MES[int(meses[i][5:]) - 1]} {meses[i][:4]}" for i in idx], fontsize=9)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([i - 0.5 for i in range(len(meses) + 1)], minor=True)
    ax.set_yticks([i - 0.5 for i in range(len(filas) + 1)], minor=True)
    ax.grid(which="minor", color=SUP, linewidth=2)
    ax.tick_params(which="minor", length=0)
    titulo(ax, "Cada formato de boletín trae campos distintos",
           "Proporción de boletines del mes con cada campo (gris = ninguno, azul oscuro = todos). Solo meses con boletines")
    fuente(fig)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG / "2_cobertura.png", dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------- 3. nubes 2024
def fig_nubes(b):
    pts, arr = [], []
    for r in b:
        if r["fecha"].startswith("2024") and r["toneladas_caribe_mexicano"]:
            d, v = date.fromisoformat(r["fecha"]), float(r["toneladas_caribe_mexicano"])
            pts.append((d, v))
            if r["dato_arrastrado_por_nubes"] == "1":
                arr.append((d, v))
    pts.sort()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(*zip(*pts), color=SERIES[0], label="Toneladas reportadas")
    ax.plot(*zip(*arr), "o", ms=6, color=SERIES[1], mec=SUP, mew=1.5, linestyle="none",
            label=f"Día con cifra arrastrada por nubosidad ({len(arr)})")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(miles))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_ylabel("Toneladas estimadas")
    ax.set_ylim(0, None)
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    titulo(ax, f"En 2024, SEMAR repitió la cifra anterior en {len(arr)} días por nubes",
           "El propio boletín lo declara: la nubosidad impide estimar y se toma como base un día previo")
    fuente(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / "3_censura_nubes_2024.png", dpi=160)
    plt.close(fig)
    return len(arr)


# ---------------------------------------------------------------- 4. zonas
def fig_zonas(z):
    nombres = ["Escaso", "Muy bajo", "Bajo", "Moderado", "Alto", "Muy alto"]
    cmap = ListedColormap(["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"])
    zonas = ["Norte", "Centro", "Sur"]
    fig, axes = plt.subplots(2, 1, figsize=(10, 3.6), gridspec_kw={"hspace": 0.6})
    cambios = {}
    for ax, (ini, fin) in zip(axes, [(date(2023, 4, 20), date(2023, 10, 31)), (date(2024, 3, 1), date(2024, 10, 15))]):
        for j, zona in enumerate(zonas):
            serie = sorted((date.fromisoformat(r["fecha"]), int(r["nivel_max"])) for r in z
                           if r["zona"] == zona and r["nivel_max"])
            for d, n in serie:
                if ini <= d <= fin:
                    ax.barh(j, 1, left=mdates.date2num(d), height=0.8, color=cmap(n - 1), linewidth=0)
            cambios[zona] = sum(1 for a, c in zip(serie, serie[1:]) if a[1] != c[1])
        ax.set_yticks(range(3), zonas, fontsize=9)
        ax.set_xlim(mdates.date2num(ini), mdates.date2num(fin))
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=cmap(i)) for i in range(6)]
    fig.legend(handles, nombres, ncol=6, frameon=False, fontsize=8.5, loc="lower center", bbox_to_anchor=(0.5, 0.05))
    axes[0].set_title("El nivel de arribo por zona casi no cambia de un día a otro", loc="left",
                      fontsize=12.5, fontweight="bold", color=TXT, pad=24)
    axes[0].text(0, 1.06, "Nivel de recale por zona según SEMAR (máximo del rango reportado). Existe solo de abr-2023 a oct-2024",
                 transform=axes[0].transAxes, fontsize=9.5, color=TXT2)
    fuente(fig)
    fig.subplots_adjust(top=0.82, bottom=0.25, left=0.08, right=0.98)
    fig.savefig(FIG / "4_niveles_por_zona.png", dpi=160)
    plt.close(fig)
    return cambios


# ---------------------------------------------------------------- 5. anticipación
def fig_anticipacion(b):
    s = {}
    for r in b:
        if r["qc_toneladas"] == "sospechoso":
            continue
        d = date.fromisoformat(r["fecha"])
        s[d] = {k: (math.log1p(float(r[c])) if r[c] else None) for k, c in [
            ("CM", "toneladas_caribe_mexicano"), ("CC", "toneladas_caribe_central"),
            ("CO", "toneladas_caribe_oriental"), ("ACO", "toneladas_atlantico_central_occ")]}

    def corr(p):
        a, c = zip(*p)
        ma, mc = sum(a) / len(a), sum(c) / len(c)
        num = sum((x - ma) * (y - mc) for x, y in zip(a, c))
        den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mc) ** 2 for y in c))
        return num / den

    lags = list(range(0, 85, 7))
    etiquetas = {"CM": "Caribe mexicano (persistencia)", "CC": "Caribe central",
                 "CO": "Caribe oriental", "ACO": "Atlántico central occidental"}
    curvas = {}
    for k in etiquetas:
        ys = []
        for lag in lags:
            p = [(v[k], s[d + timedelta(days=lag)]["CM"]) for d, v in s.items()
                 if v[k] is not None and d + timedelta(days=lag) in s and s[d + timedelta(days=lag)]["CM"] is not None]
            ys.append(corr(p) if len(p) > 30 else float("nan"))
        curvas[k] = ys

    fig, ax = plt.subplots(figsize=(9, 4.6))
    for i, k in enumerate(etiquetas):
        ax.plot(lags, curvas[k], color=SERIES[i], marker="o", ms=4, label=etiquetas[k])
    ax.axhline(0, color=GRID, linewidth=1)
    ax.set_xticks(lags)
    ax.set_xlabel("Días de anticipación")
    ax.set_ylabel("Correlación con el Caribe mexicano (log)")
    ax.set_ylim(-0.2, 1.02)
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    titulo(ax, "El Caribe central y oriental no anticipan mejor que la persistencia",
           "Correlación entre cada región hoy y el Caribe mexicano X días después. El Atlántico (amarillo) no se probó fuera de muestra")
    fuente(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / "5_anticipacion.png", dpi=160)
    plt.close(fig)

    # Prueba preregistrada: entrena 2025, evalúa 2026
    res = []
    for h in (28, 42, 56):
        datos = [(d, v["CM"], v["CC"], v["CO"], s[d + timedelta(days=h)]["CM"]) for d, v in s.items()
                 if None not in (v["CM"], v["CC"], v["CO"]) and d + timedelta(days=h) in s
                 and s[d + timedelta(days=h)]["CM"] is not None]
        ent = [x for x in datos if x[0].year == 2025]
        pru = [x for x in datos if x[0].year == 2026]
        c0 = _ols([[1, x[1]] for x in ent], [x[4] for x in ent])
        c1 = _ols([[1, x[1], x[2], x[3]] for x in ent], [x[4] for x in ent])
        ep = sum(abs(x[4] - x[1]) for x in pru) / len(pru)
        e0 = sum(abs(x[4] - c0[0] - c0[1] * x[1]) for x in pru) / len(pru)
        e1 = sum(abs(x[4] - c1[0] - c1[1] * x[1] - c1[2] * x[2] - c1[3] * x[3]) for x in pru) / len(pru)
        res.append((h, len(ent), len(pru), ep, e0, e1, 1 - e1 / min(ep, e0)))
    return {k: dict(zip(lags, v)) for k, v in curvas.items()}, res


if __name__ == "__main__":
    b, z = leer()
    maximos = fig_temporadas(b)
    fig_cobertura(b, z)
    n_arr = fig_nubes(b)
    cambios = fig_zonas(z)
    curvas, res = fig_anticipacion(b)
    print("Máximos por temporada:", {a: (str(p[0])[5:], round(p[1])) for a, p in maximos.items()})
    print("Días con dato arrastrado 2024:", n_arr)
    print("Cambios de nivel por zona:", cambios)
    for k, v in curvas.items():
        print(k, {l: round(c, 2) for l, c in v.items() if l in (0, 28, 42, 56)})
    print("h n_ent n_prueba persistencia soloCM CM+CC+CO mejora")
    for r in res:
        print(r[0], r[1], r[2], *(round(x, 3) for x in r[3:6]), f"{r[6]:.0%}")
