#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EDA de los tiempos logisticos de cada viaje de vehiculos de carga (RNDC, MinTransporte).
Fuente: https://www.datos.gov.co/d/tfrd-amb4

Uso:
    python3 eda_tiempos_logisticos.py <archivo.csv> [carpeta_salida]

Genera en <carpeta_salida>:
    figs/*.pdf|png     figuras del articulo
    tables/*.tex       tablas del articulo
    numeros.tex        macros con todas las cifras citadas en el texto
    results.json       las mismas cifras en formato legible
Requiere: pandas, numpy, scipy, matplotlib.
"""
import sys, os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
from scipy import stats

CSV = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "salida"
os.makedirs(f"{OUT}/figs", exist_ok=True)
os.makedirs(f"{OUT}/tables", exist_ok=True)

# ----------------------------------------------------------------- estilo
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, GRAY = "#0b0b0b", "#52514e", "#e3e2de", "#a9a8a3"
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "font.size": 7.5, "axes.titlesize": 7.5, "axes.labelsize": 7.5,
    "xtick.labelsize": 6.8, "ytick.labelsize": 6.8, "legend.fontsize": 6.8,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True,
    "grid.color": GRID, "grid.linewidth": 0.5,
    "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight",
    "pdf.fonttype": 42,
})
R = {}        # resultados (json)
M = {}        # macros LaTeX


def num(x, d=2):
    """Formato espanol para LaTeX: coma decimal {,} y espacio fino como separador de miles."""
    t = f"{abs(x):,.{d}f}"
    ip, _, dp = t.partition(".")
    ip = ip.replace(",", "\\,")
    out = ip + ("{,}" + dp if dp else "")
    return ("\\ensuremath{-}" + out) if x < 0 else out


def pfmt(p):
    return "\\ensuremath{<}\\,0{,}001" if p < 1e-3 else "= " + num(p, 3)


def mac(name, val):
    M[name] = val


from matplotlib.ticker import FuncFormatter
CF = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",").replace("-", "\u2212"))


def dc(x):
    return str(x).replace(".", ",")


def ca(ax, axis="y"):
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(CF)


def save(fig, name):
    fig.savefig(f"{OUT}/figs/{name}.pdf")
    fig.savefig(f"{OUT}/figs/{name}.png")
    plt.close(fig)


# ----------------------------------------------------------------- carga
raw = pd.read_csv(CSV, dtype=str, low_memory=False)
N0 = len(raw)
NUM = ["HORAS_VIAJE", "HORAS_ESPERA_CARGUE", "HORAS_CARGUE", "HORAS_ESPERA_DESCARGUE",
       "HORAS_DESCARGUE", "VALOR_PACTADO", "VALOR_PAGADO", "CANTIDAD", "CANTIDAD_REMESAS_VIAJE"]
for c in NUM:
    raw[c] = pd.to_numeric(raw[c].str.replace(",", ""), errors="coerce")
raw["fs"] = pd.to_datetime(raw.FECHASALIDACARGUE, format="%Y %b %d %I:%M:%S %p", errors="coerce")
raw["fl"] = pd.to_datetime(raw.FECHALLEGADADESCARGUE, format="%Y %b %d %I:%M:%S %p", errors="coerce")
TIMES = ["HORAS_ESPERA_CARGUE", "HORAS_CARGUE", "HORAS_ESPERA_DESCARGUE", "HORAS_DESCARGUE"]
LAB = {"HORAS_ESPERA_CARGUE": "Espera para cargue", "HORAS_CARGUE": "Cargue",
       "HORAS_ESPERA_DESCARGUE": "Espera para descargue", "HORAS_DESCARGUE": "Descargue",
       "HORAS_VIAJE": "Horas de viaje", "espera_total": "Espera total (cargue + descargue)"}

R["n_raw"] = N0
R["n_viajes_aprox"] = int(raw.groupby(["PLACA", "FECHASALIDACARGUE", "CODIGO_CARGUE",
                                       "CODIGO_DESCARGUE"]).ngroups)
R["n_placas"] = int(raw.PLACA.nunique())
R["n_empresas"] = int(raw.EMPRESA_TRANSPORTE.nunique())
R["fecha_min"] = str(raw.fs.min().date()); R["fecha_max"] = str(raw.fs.max().date())
R["llegada_max"] = str(raw.fl.max().date())
R["nan_total"] = int(raw[["NATURALEZA", "UNID_MEDIDA", "DESCARGUE", "CONFIGURACION"]].isna().any(axis=1).sum())
R["vacios_actual"] = {c: int(raw[c].isna().sum()) for c in
                      ["NATURALEZA", "UNID_MEDIDA", "DESCARGUE", "CONFIGURACION"]}


def limpiar(d, dedup=True):
    log = {}
    if dedup:
        n = len(d); d = d.drop_duplicates(); log["dup"] = n - len(d)
    n = len(d)
    d = d.dropna(subset=["NATURALEZA", "UNID_MEDIDA", "DESCARGUE", "CONFIGURACION"] + NUM[:5])
    log["faltantes"] = n - len(d)
    n = len(d); d = d[d.HORAS_CARGUE >= 0]; log["negativos"] = n - len(d)
    n = len(d)
    d = d[~((d[TIMES] > 168).any(axis=1) | (d.HORAS_VIAJE > 720))]
    log["extremos"] = n - len(d)
    return d.copy(), log


df, LOG = limpiar(raw)
R["limpieza"] = LOG
R["n_clean"] = len(df)
dfB, _ = limpiar(raw, dedup=False)          # variante: conservar duplicados

# variables derivadas
df["espera_total"] = df.HORAS_ESPERA_CARGUE + df.HORAS_ESPERA_DESCARGUE
df["t_nodo"] = df[TIMES].sum(axis=1)
df["frac_espera"] = np.where(df.t_nodo > 0, df.espera_total / df.t_nodo, np.nan)
df["ec2"] = df.HORAS_ESPERA_CARGUE > 2
df["ed2"] = df.HORAS_ESPERA_DESCARGUE > 2
df["dow_s"] = df.fs.dt.dayofweek
df["dow_l"] = df.fl.dt.dayofweek
df["h_ll"] = df.HORA_LLEGADA_DESCARGUE.str[11:13].astype(int)   # hora de llegada al descargue
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

# ------------------------------------------------- atipicos (regla IQR)
iqr_tab = {}
fences = {}
for c in TIMES:
    q1, q3 = df[c].quantile([.25, .75]); f = q3 + 1.5 * (q3 - q1)
    fences[c] = f
    iqr_tab[c] = {"cerca": float(f), "n": int((df[c] > f).sum()), "pct": float((df[c] > f).mean() * 100)}
R["iqr"] = iqr_tab
out_any = (df[TIMES] > pd.Series(fences)).any(axis=1)
R["iqr_cualquiera_pct"] = float(out_any.mean() * 100)

# ------------------------------------------- estadistica descriptiva
rows = []
for c in TIMES + ["HORAS_VIAJE", "espera_total"]:
    s = df[c]
    rows.append((LAB[c], s.mean(), s.median(), s.mode().iloc[0], s.var(),
                 s.quantile(.25), s.quantile(.75), s.quantile(.95), s.quantile(.99), s.skew()))
desc = pd.DataFrame(rows, columns=["v", "media", "mediana", "moda", "var", "p25", "p75", "p95", "p99", "asim"])
R["desc"] = desc.round(3).to_dict("records")
with open(f"{OUT}/tables/table_desc.tex", "w") as f:
    f.write("\\begin{tabular}{lrrrrrrr}\n\\toprule\n")
    f.write("Variable (h) & Media & Mediana & Moda & Var. & P25 & P75 & P95 \\\\\n\\midrule\n")
    for r in desc.itertuples():
        f.write(f"{r.v} & {num(r.media)} & {num(r.mediana)} & {num(r.moda)} & {num(r.var)} & "
                f"{num(r.p25)} & {num(r.p75)} & {num(r.p95)} \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n")
for r in desc.itertuples():
    key = {"Espera para cargue": "ec", "Cargue": "ca", "Espera para descargue": "ed",
           "Descargue": "de", "Horas de viaje": "vi", "Espera total (cargue + descargue)": "et"}[r.v]
    NOM = {"media": "Media", "mediana": "Mediana", "moda": "Moda", "var": "Varianza", "p25": "QUno",
           "p75": "QTres", "p95": "PNoventaCinco", "p99": "PNoventaNueve", "asim": "Asimetria"}
    for k, nm in NOM.items():
        mac(f"{key}{nm}", num(getattr(r, k)))
# (los nombres usan solo letras: ecMedia, ecMediana, ecPNoventaCinco, ...)

for c, k in [("HORAS_ESPERA_CARGUE", "ec"), ("HORAS_ESPERA_DESCARGUE", "ed"),
             ("HORAS_CARGUE", "ca"), ("HORAS_DESCARGUE", "de")]:
    s = df[c]
    mac(k + "Cero", num((s == 0).mean() * 100, 1))
    mac(k + "MasDos", num((s > 2).mean() * 100, 1))
    mac(k + "MasDoce", num((s > 12).mean() * 100, 2))
    mac(k + "MasDosN", num(int((s > 2).sum()), 0))
    mac(k + "Entero", num(((s % 1) == 0).mean() * 100, 1))
    mac(k + "IqrPct", num(iqr_tab[c]["pct"], 1))
    mac(k + "IqrCerca", num(iqr_tab[c]["cerca"], 2))
mac("iqrCualquiera", num(R["iqr_cualquiera_pct"], 1))
mac("caDoceExacto", num((df.HORAS_CARGUE == 12).mean() * 100, 1))
mac("deDoceExacto", num((df.HORAS_DESCARGUE == 12).mean() * 100, 1))
mac("ningunaEspera", num(((df.HORAS_ESPERA_CARGUE == 0) & (df.HORAS_ESPERA_DESCARGUE == 0)).mean() * 100, 1))
mac("algunaEsperaDos", num(((df.ec2) | (df.ed2)).mean() * 100, 1))
mac("ambasEsperaDos", num(((df.ec2) & (df.ed2)).mean() * 100, 1))
fe = df.frac_espera.dropna()
mac("fracEsperaMedia", num(fe.mean() * 100, 1))
mac("fracEsperaMediana", num(fe.median() * 100, 1))
mac("fracEsperaMitad", num((fe > .5).mean() * 100, 1))

# macros de datos generales
mac("NRaw", num(N0, 0)); mac("NClean", num(len(df), 0))
mac("NViajes", num(R["n_viajes_aprox"], 0)); mac("NPlacas", num(R["n_placas"], 0))
mac("NEmpresas", num(R["n_empresas"], 0))
mac("NDup", num(LOG["dup"], 0)); mac("NFalt", num(LOG["faltantes"], 0))
mac("NNeg", num(LOG["negativos"], 0)); mac("NExt", num(LOG["extremos"], 0))
mac("pctRemovido", num((1 - len(df) / N0) * 100, 1))
mac("NDupPct", num(LOG["dup"] / N0 * 100, 1))
mac("NNaturalezaVacia", num(R["vacios_actual"]["NATURALEZA"], 0))
mac("NDescargueVacio", num(R["vacios_actual"]["DESCARGUE"], 0))
mac("NConfigVacia", num(R["vacios_actual"]["CONFIGURACION"], 0))
mac("llegadaMax", R["llegada_max"])

# -------------------------------------------------------- Figura 1: histogramas
fig, axs = plt.subplots(2, 2, figsize=(3.45, 3.0))
bins = np.arange(0, 12.5, 0.5)
for ax, c in zip(axs.ravel(), TIMES):
    s = df[c]
    w = np.full(len(s[s <= 12]), 100 / len(s))
    ax.hist(s[s <= 12], bins=bins, weights=w, color=BLUE, edgecolor="white", linewidth=0.3)
    ax.axvline(s.median(), color=INK2, ls="--", lw=0.8)
    ax.set_title(LAB[c])
    ax.set_xlim(0, 12)
    ca(ax, "x"); ca(ax, "y")
    ax.text(0.97, 0.93, dc(f"> 12 h: {(s > 12).mean() * 100:.1f} %"), transform=ax.transAxes,
            ha="right", va="top", fontsize=6.3, color=INK2)
    ax.text(0.97, 0.80, dc(f"mediana {s.median():.2f} h"), transform=ax.transAxes,
            ha="right", va="top", fontsize=6.3, color=INK2)
for ax in axs[1]:
    ax.set_xlabel("Horas")
for ax in axs[:, 0]:
    ax.set_ylabel("Registros (%)")
fig.tight_layout(pad=0.4)
save(fig, "fig1_hist")

# --------------------------------------------- tablas por grupo + pruebas
def resumen(g):
    return pd.Series({
        "n": len(g),
        "ec": g.HORAS_ESPERA_CARGUE.mean(), "ec2": g.ec2.mean() * 100,
        "ed": g.HORAS_ESPERA_DESCARGUE.mean(), "ed2": g.ed2.mean() * 100,
        "ca": g.HORAS_CARGUE.median(), "de": g.HORAS_DESCARGUE.median()})


nat = df.groupby("NATURALEZA").apply(resumen, include_groups=False)
nat = nat[nat.n >= 1000].sort_values("n", ascending=False)
cfg = df.groupby("CONFIGURACION").apply(resumen, include_groups=False).sort_values("n", ascending=False).head(6)
R["nat"] = nat.round(3).reset_index().to_dict("records")
R["cfg"] = cfg.round(3).reset_index().to_dict("records")
NAT_ORDER = list(nat.index)
mac("natN", num(nat.n.sum(), 0))
mac("natNormalPct", num(nat.loc["Carga Normal", "n"] / len(df) * 100, 1))
mac("natPelPct", num(nat.loc["Carga Peligrosa", "n"] / len(df) * 100, 1))
mac("natRefPct", num(nat.loc["Refrigerada", "n"] / len(df) * 100, 1))
for k, nm in [("Nor", "Carga Normal"), ("Pel", "Carga Peligrosa"), ("Ref", "Refrigerada")]:
    for col, cn in [("ec", "EC"), ("ec2", "ECDOS"), ("ed", "ED"), ("ed2", "EDDOS"), ("ca", "CA"),
                    ("de", "DE"), ("n", "N")]:
        mac(f"nat{k}{cn}", num(nat.loc[nm, col], 0 if col == "n" else (1 if col.endswith("2") else 2)))

def fila(nombre, r):
    return (f"{nombre} & {num(r.n, 0)} & {num(r.ec)} & {num(r.ec2, 1)} & {num(r.ed)} & "
            f"{num(r.ed2, 1)} & {num(r.ca)} & {num(r.de)} \\\\\n")


with open(f"{OUT}/tables/table_grupos.tex", "w") as f:
    f.write("\\begin{tabular}{lrrrrrrr}\n\\toprule\n")
    f.write("Grupo & Registros & \\shortstack{Esp. carg.\\\\media (h)} & \\shortstack{Esp. carg.\\\\$>2$ h (\\%)} & "
            "\\shortstack{Esp. desc.\\\\media (h)} & \\shortstack{Esp. desc.\\\\$>2$ h (\\%)} & "
            "\\shortstack{Cargue\\\\med. (h)} & \\shortstack{Descargue\\\\med. (h)} \\\\\n\\midrule\n")
    f.write("\\multicolumn{8}{l}{\\textit{Naturaleza de la carga}} \\\\\n")
    for k, r in nat.iterrows():
        f.write(fila(k.replace("Carga ", "").replace("Desechos Peligrosos", "Desechos pelig."), r))
    f.write("\\midrule\n\\multicolumn{8}{l}{\\textit{Configuración del vehículo (6 más frecuentes)}} \\\\\n")
    for k, r in cfg.iterrows():
        f.write(fila(k, r))
    f.write("\\bottomrule\n\\end{tabular}\n")


def kruskal(var, col, d, grupos=None):
    d = d.dropna(subset=[col])
    if grupos is not None:
        d = d[d[col].isin(grupos)]
    gs = [g[var].values for _, g in d.groupby(col)]
    H, p = stats.kruskal(*gs)
    return {"H": float(H), "p": float(p), "eps2": float(H / (len(d) - 1)), "n": int(len(d)), "k": len(gs)}


tests = {}
for var, k in [("HORAS_ESPERA_CARGUE", "ec"), ("HORAS_ESPERA_DESCARGUE", "ed"),
               ("HORAS_CARGUE", "ca"), ("HORAS_DESCARGUE", "de")]:
    tests[f"nat_{k}"] = kruskal(var, "NATURALEZA", df, NAT_ORDER)
    tests[f"cfg_{k}"] = kruskal(var, "CONFIGURACION", df, list(cfg.index))
tests["dow_ec"] = kruskal("HORAS_ESPERA_CARGUE", "dow_s", df)
tests["dow_ed"] = kruskal("HORAS_ESPERA_DESCARGUE", "dow_l", df)
R["kw"] = tests
for k, t in tests.items():
    n = k.replace("_", "")
    mac(f"kw{n}H", num(t["H"], 1)); mac(f"kw{n}P", pfmt(t["p"])); mac(f"kw{n}E", num(t["eps2"], 3))

# domingo/festivo vs resto (espera para cargue segun dia de salida)
dom = df.dow_s == 6
u = stats.mannwhitneyu(df.loc[dom, "HORAS_ESPERA_CARGUE"], df.loc[~dom, "HORAS_ESPERA_CARGUE"],
                       alternative="two-sided", method="asymptotic")
R["mw_dom_ec"] = {"U": float(u.statistic), "p": float(u.pvalue),
                  "cles": float(u.statistic / (dom.sum() * (~dom).sum()))}
mac("domEcCles", num(R["mw_dom_ec"]["cles"], 3)); mac("domEcP", pfmt(u.pvalue))
mac("domEcMedia", num(df.loc[dom, "HORAS_ESPERA_CARGUE"].mean(), 2))
mac("restoEcMedia", num(df.loc[~dom, "HORAS_ESPERA_CARGUE"].mean(), 2))
mac("domEcDos", num(df.loc[dom, "ec2"].mean() * 100, 1))
mac("restoEcDos", num(df.loc[~dom, "ec2"].mean() * 100, 1))
mac("domN", num(int(dom.sum()), 0))
mac("domPct", num(dom.mean() * 100, 1))
wd_dom = df.loc[df.dow_l == 6, "ed2"].mean() * 100
sab = df.dow_l == 5
u2 = stats.mannwhitneyu(df.loc[sab, "HORAS_ESPERA_DESCARGUE"], df.loc[~sab, "HORAS_ESPERA_DESCARGUE"],
                        alternative="two-sided", method="asymptotic")
R["mw_sab_ed"] = {"p": float(u2.pvalue), "cles": float(u2.statistic / (sab.sum() * (~sab).sum()))}
mac("sabEdCles", num(R["mw_sab_ed"]["cles"], 3)); mac("sabEdP", pfmt(u2.pvalue))
mac("domEdDos", num(wd_dom, 1))
mac("sabEdMedia", num(df.loc[sab, "HORAS_ESPERA_DESCARGUE"].mean(), 2))
mac("restoEdMedia", num(df.loc[~sab, "HORAS_ESPERA_DESCARGUE"].mean(), 2))
mac("sabEdDos", num(df.loc[sab, "ed2"].mean() * 100, 1))
mac("restoEdDos", num(df.loc[~sab, "ed2"].mean() * 100, 1))

# ------------------------------------------------- ciudades origen/destino
SUF = ["BOGOTA D. C.", "VALLE DEL CAUCA", "NORTE DE SANTANDER", "LA GUAJIRA", "ANTIOQUIA", "ATLANTICO",
       "BOLIVAR", "CUNDINAMARCA", "SANTANDER", "RISARALDA", "META", "CALDAS", "BOYACA", "MAGDALENA",
       "TOLIMA", "CORDOBA", "HUILA", "CESAR", "NARIÑO", "CAUCA", "QUINDIO", "CASANARE", "SUCRE",
       "CHOCO", "ARAUCA", "PUTUMAYO", "CAQUETA", "GUAVIARE", "VICHADA", "AMAZONAS"]
SUF.sort(key=len, reverse=True)


def corto(s):
    for x in SUF:
        if s.endswith(" " + x):
            s = s[: -len(x) - 1]; break
    s = s.title()
    return {"Medellin": "Medellín", "Bogota": "Bogotá", "Tocancipa": "Tocancipá"}.get(s, s)


top_o = df.CARGUE.value_counts().head(10).index
top_d = df.DESCARGUE.value_counts().head(10).index
go = df[df.CARGUE.isin(top_o)].groupby("CARGUE").agg(n=("ec2", "size"), p=("ec2", "mean"),
                                                     m=("HORAS_ESPERA_CARGUE", "mean"))
gd = df[df.DESCARGUE.isin(top_d)].groupby("DESCARGUE").agg(n=("ed2", "size"), p=("ed2", "mean"),
                                                           m=("HORAS_ESPERA_DESCARGUE", "mean"))
go["p"] *= 100; gd["p"] *= 100
go = go.sort_values("p"); gd = gd.sort_values("p")
R["origen_top"] = go.round(2).reset_index().to_dict("records")
R["destino_top"] = gd.round(2).reset_index().to_dict("records")
mac("origMax", corto(go.index[-1])); mac("origMaxP", num(go.p.iloc[-1], 1))
mac("origMin", corto(go.index[0])); mac("origMinP", num(go.p.iloc[0], 1))
mac("destMax", corto(gd.index[-1])); mac("destMaxP", num(gd.p.iloc[-1], 1))
mac("destMin", corto(gd.index[0])); mac("destMinP", num(gd.p.iloc[0], 1))
mac("topOrigPct", num(df.CARGUE.isin(top_o).mean() * 100, 1))
mac("topDestPct", num(df.DESCARGUE.isin(top_d).mean() * 100, 1))
mac("origNom", ", ".join(corto(x) for x in top_o[:3]))
for nm, col, top, flag in [("orig", "CARGUE", top_o, "ec2"), ("dest", "DESCARGUE", top_d, "ed2")]:
    sub = df[df[col].isin(top)]
    ct = pd.crosstab(sub[col], sub[flag])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    v = float(np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1))))
    R[f"chi_{nm}"] = {"chi2": float(chi2), "p": float(p), "dof": int(dof), "V": v}
    mac(f"chi{nm}X", num(chi2, 0)); mac(f"chi{nm}P", pfmt(p)); mac(f"chi{nm}V", num(v, 3))
    mac(f"chi{nm}Dof", str(dof))
tv = {}
for nm, col, var in [("orig", "CARGUE", "HORAS_ESPERA_CARGUE"), ("dest", "DESCARGUE", "HORAS_ESPERA_DESCARGUE")]:
    top = top_o if nm == "orig" else top_d
    tv[nm] = kruskal(var, col, df, list(top))
    mac(f"kw{nm}H", num(tv[nm]["H"], 1)); mac(f"kw{nm}P", pfmt(tv[nm]["p"]))
    mac(f"kw{nm}E", num(tv[nm]["eps2"], 3))
R["kw_ciudades"] = tv

fig, axs = plt.subplots(2, 1, figsize=(3.45, 3.7))
for ax, g, tit, tot in [(axs[0], go, f"Espera para cargue > 2 h, por origen (--- total {dc(f'{df.ec2.mean() * 100:.1f}')} %)", df.ec2.mean() * 100),
                        (axs[1], gd, f"Espera para descargue > 2 h, por destino (--- total {dc(f'{df.ed2.mean() * 100:.1f}')} %)", df.ed2.mean() * 100)]:
    y = np.arange(len(g))
    ax.barh(y, g.p, color=BLUE, height=0.62)
    ax.set_yticks(y); ax.set_yticklabels([corto(i) for i in g.index])
    ax.axvline(tot, color=INK2, ls="--", lw=0.8)
    ca(ax, "x")
    ax.set_title(tit, loc="left"); ax.grid(axis="y", visible=False)
    for yy, v in zip(y, g.p):
        ax.text(v + 0.15, yy, dc(f"{v:.1f}"), va="center", fontsize=6.2, color=INK2,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
    ax.set_xlim(0, max(g.p.max(), tot) * 1.18)
axs[1].set_xlabel("Registros con espera > 2 h (%)")
fig.tight_layout(pad=0.4)
save(fig, "fig3_ciudades")

# ----------------------------------------------- Figura 2: cajas por naturaleza
fig, axs = plt.subplots(2, 2, figsize=(3.45, 3.0))
grp3 = ["Carga Normal", "Carga Peligrosa", "Refrigerada"]
cols3 = [BLUE, ORANGE, AQUA]
for ax, c in zip(axs.ravel(), TIMES):
    data = [df.loc[df.NATURALEZA == g, c].values for g in grp3]
    bp = ax.boxplot(data, whis=(5, 95), showfliers=False, patch_artist=True, widths=0.55,
                    medianprops=dict(color=INK, lw=1.0), whiskerprops=dict(color=INK2, lw=0.7),
                    capprops=dict(color=INK2, lw=0.7))
    for patch, col in zip(bp["boxes"], cols3):
        patch.set_facecolor(col); patch.set_edgecolor("white"); patch.set_alpha(0.9)
    ax.set_xticks([1, 2, 3]); ax.set_xticklabels(["Normal", "Peligrosa", "Refrig."])
    ax.set_title(LAB[c]); ax.grid(axis="x", visible=False); ca(ax, "y")
    ax.set_ylim(0, max(np.percentile(q, 95) for q in data) * 1.12 + 0.1)
for ax in axs[:, 0]:
    ax.set_ylabel("Horas")
fig.tight_layout(pad=0.4)
save(fig, "fig2_cajas")

# ---------------------------------------- Figura 4: serie diaria (salida)
dia = df.groupby(df.fs.dt.day).agg(n=("ec2", "size"), ec=("ec2", "mean"), ed=("ed2", "mean"))
dia["ec"] *= 100; dia["ed"] *= 100
R["diario"] = dia.round(2).reset_index().to_dict("records")
domingos = [d for d in range(1, 32) if pd.Timestamp(2021, 1, d).dayofweek == 6]
festivos = [1, 11]
fig, axs = plt.subplots(2, 1, figsize=(7.1, 3.1), sharex=True, gridspec_kw={"height_ratios": [1, 1.25]})
for ax in axs:
    for d in domingos:
        ax.axvspan(d - 0.5, d + 0.5, color=GRAY, alpha=0.28, lw=0)
    for d in festivos:
        ax.axvspan(d - 0.5, d + 0.5, color=ORANGE, alpha=0.18, lw=0)
axs[0].bar(dia.index, dia.n / 1000, color=BLUE, width=0.7)
axs[0].set_ylabel("Registros (miles)"); ca(axs[0], "y"); ca(axs[1], "y")
axs[1].plot(dia.index, dia.ec, color=BLUE, lw=1.4, marker="o", ms=3)
axs[1].plot(dia.index, dia.ed, color=ORANGE, lw=1.4, marker="o", ms=3)
axs[1].set_ylabel("Espera > 2 h (%)")
axs[1].set_xlabel("Día de enero de 2021 (fecha de salida del cargue)")
axs[1].set_xlim(0.4, 31.6); axs[1].set_xticks(range(1, 32, 2)); axs[1].set_ylim(0)
axs[1].legend(handles=[plt.Line2D([], [], color=BLUE, lw=1.4, marker="o", ms=3, label="Para cargue"),
                       plt.Line2D([], [], color=ORANGE, lw=1.4, marker="o", ms=3, label="Para descargue"),
                       Patch(color=GRAY, alpha=0.4, label="Domingo"),
                       Patch(color=ORANGE, alpha=0.25, label="Festivo")],
              ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.28), frameon=False)
fig.tight_layout(pad=0.4)
save(fig, "fig4_diario")
wk = df.dow_s.map(lambda x: x < 5)
mac("diaMinN", num(int(dia.n.min()), 0)); mac("diaMaxN", num(int(dia.n.max()), 0))
mac("diaMinD", str(int(dia.n.idxmin()))); mac("diaMaxD", str(int(dia.n.idxmax())))
mac("domMediaDiaN", num(dia.loc[domingos, "n"].mean(), 0))
mac("habMediaDiaN", num(dia.loc[[d for d in range(1, 32) if d not in domingos + festivos], "n"].mean(), 0))
mac("domVolRatio", num(dia.loc[domingos, "n"].mean() / dia.loc[[d for d in range(1, 32) if d not in domingos + festivos], "n"].mean() * 100, 0))

# ------------------------------- Figura 5: dia de la semana y hora de llegada
wc = df.groupby("dow_s").ec2.mean() * 100
wd = df.groupby("dow_l").ed2.mean() * 100
hh = df.groupby("h_ll").agg(n=("ed2", "size"), p=("ed2", "mean"), m=("HORAS_ESPERA_DESCARGUE", "mean"))
hh["p"] *= 100
R["semana"] = {"ec": wc.round(2).to_dict(), "ed": wd.round(2).to_dict()}
R["hora_llegada"] = hh.round(2).reset_index().to_dict("records")
fig, axs = plt.subplots(1, 2, figsize=(7.1, 2.3), gridspec_kw={"width_ratios": [1, 1.55]})
ax = axs[0]
x = np.arange(7); w = 0.38
ax.bar(x - w / 2, wc.values, w, color=BLUE, label="Para cargue (día de salida)")
ax.bar(x + w / 2, wd.values, w, color=ORANGE, label="Para descargue (día de llegada)")
ax.set_xticks(x); ax.set_xticklabels(DIAS); ax.grid(axis="x", visible=False)
ax.set_ylabel("Registros con espera > 2 h (%)")
ax.set_title("(a) Día de la semana", loc="left"); ca(ax, "y")
ax.legend(frameon=False, loc="upper left", fontsize=6.3)
ax.set_ylim(0, max(wc.max(), wd.max()) * 1.38)
ax = axs[1]
tot = df.ed2.mean() * 100
ax.bar(hh.index, hh.p, color=BLUE, width=0.72)
ax.axhline(tot, color=INK2, ls="--", lw=0.8)
ax.text(23.4, tot + 0.25, dc(f"total {tot:.1f} %"), ha="right", fontsize=6.3, color=INK2)
ax.set_xticks(range(0, 24, 2)); ax.set_xlim(-0.7, 23.7)
ax.set_xlabel("Hora de llegada al sitio de descargue"); ax.grid(axis="x", visible=False)
ax.set_ylabel("Espera para descargue > 2 h (%)")
ax.set_title("(b) Hora de llegada", loc="left"); ca(ax, "y")
fig.tight_layout(pad=0.4)
save(fig, "fig5_semana_hora")
H0, H1 = 3, 7
noche = df.h_ll.between(H0, H1)
mac("horaNochePct", num(noche.mean() * 100, 1))
mac("horaNocheDos", num(df.loc[noche, "ed2"].mean() * 100, 1))
mac("horaRestoDos", num(df.loc[~noche, "ed2"].mean() * 100, 1))
mac("horaNocheMedia", num(df.loc[noche, "HORAS_ESPERA_DESCARGUE"].mean(), 2))
mac("horaRestoMedia", num(df.loc[~noche, "HORAS_ESPERA_DESCARGUE"].mean(), 2))
mac("horaMaxH", str(int(hh.p.idxmax()))); mac("horaMaxP", num(hh.p.max(), 1))
mac("horaMinH", str(int(hh.p.idxmin()))); mac("horaMinP", num(hh.p.min(), 1))
u3 = stats.mannwhitneyu(df.loc[noche, "HORAS_ESPERA_DESCARGUE"], df.loc[~noche, "HORAS_ESPERA_DESCARGUE"],
                        alternative="two-sided", method="asymptotic")
cles3 = float(u3.statistic / (noche.sum() * (~noche).sum()))
R["mw_noche_ed"] = {"p": float(u3.pvalue), "cles": cles3}
mac("nocheCles", num(cles3, 3)); mac("nocheP", pfmt(u3.pvalue))
kwh = kruskal("HORAS_ESPERA_DESCARGUE", "h_ll", df)
R["kw_hora_ed"] = kwh
mac("kwhoraH", num(kwh["H"], 1)); mac("kwhoraP", pfmt(kwh["p"])); mac("kwhoraE", num(kwh["eps2"], 3))
# P(espera > 2 h) en las 24 horas: ratio max/min
mac("horaRatio", num(hh.p.max() / hh.p.min(), 1))

# ------------------------------------------- Figura 6: correlacion Spearman
cm = df[["HORAS_ESPERA_CARGUE", "HORAS_CARGUE", "HORAS_ESPERA_DESCARGUE", "HORAS_DESCARGUE",
         "HORAS_VIAJE", "CANTIDAD_REMESAS_VIAJE"]].copy()
cm["CANTIDAD_KG"] = np.where(df.UNID_MEDIDA == "Kilogramos", df.CANTIDAD, np.nan)
corr = cm.corr(method="spearman")
nombres = ["Esp. carg.", "Cargue", "Esp. desc.", "Descargue", "Viaje", "Remesas", "Cant. (kg)"]
R["spearman"] = corr.round(3).values.tolist()
C = corr.values
names_ix = {n: i for i, n in enumerate(nombres)}
def r_(a, b): return C[names_ix[a], names_ix[b]]
mac("rEcEd", num(r_("Esp. carg.", "Esp. desc."), 2))
mac("rEcCa", num(r_("Esp. carg.", "Cargue"), 2))
mac("rEdDe", num(r_("Esp. desc.", "Descargue"), 2))
mac("rCaDe", num(r_("Cargue", "Descargue"), 2))
mac("rEcVi", num(r_("Esp. carg.", "Viaje"), 2))
mac("rEdVi", num(r_("Esp. desc.", "Viaje"), 2))
mac("rCaKg", num(r_("Cargue", "Cant. (kg)"), 2))
mac("rDeKg", num(r_("Descargue", "Cant. (kg)"), 2))
mac("rEcRem", num(r_("Esp. carg.", "Remesas"), 2))
mac("rCaRem", num(r_("Cargue", "Remesas"), 2))
mac("rViKg", num(r_("Viaje", "Cant. (kg)"), 2))
mac("rDeRem", num(r_("Descargue", "Remesas"), 2))
cmap = LinearSegmentedColormap.from_list("div", [BLUE, "#f2f1ee", ORANGE])
fig, ax = plt.subplots(figsize=(3.45, 3.1))
im = ax.imshow(C, cmap=cmap, vmin=-1, vmax=1)
ax.set_xticks(range(7)); ax.set_yticks(range(7))
ax.set_xticklabels(nombres, rotation=45, ha="right"); ax.set_yticklabels(nombres)
ax.grid(False)
for s in ax.spines.values(): s.set_visible(False)
for i in range(7):
    for j in range(7):
        ax.text(j, i, dc(f"{C[i, j]:.2f}"), ha="center", va="center", fontsize=6.2,
                color=INK if abs(C[i, j]) < 0.7 else "white")
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
cb.ax.tick_params(labelsize=6.2); cb.outline.set_visible(False); cb.ax.yaxis.set_major_formatter(CF)
fig.tight_layout(pad=0.4)
save(fig, "fig6_corr")

# dependencia entre esperas
p1 = df.loc[df.ec2, "ed2"].mean() * 100
p0 = df.loc[~df.ec2, "ed2"].mean() * 100
R["cond"] = {"ed2_dado_ec2": p1, "ed2_dado_no_ec2": p0}
mac("pEdDadoEc", num(p1, 1)); mac("pEdDadoNoEc", num(p0, 1))
mac("pEdRazon", num(p1 / p0, 1))

# --------------------------------------------- valor pactado vs pagado
v = df[(df.CANTIDAD_REMESAS_VIAJE == 1) & (df.VALOR_PACTADO >= 100000)].copy()
v["rel"] = v.VALOR_PAGADO / v.VALOR_PACTADO - 1
v["igual"] = v.rel.abs() <= 0.001
v["mas"] = v.rel > 0.001
bins_e = [-0.1, 0, 2, 6, 12, 1e9]
v["bin"] = pd.cut(v.espera_total, bins_e, labels=["0", "0-2", "2-6", "6-12", ">12"])
vt = v.groupby("bin", observed=True).agg(n=("igual", "size"), igual=("igual", "mean"), mas=("mas", "mean"))
R["valor"] = {"n": len(v), "igual": float(v.igual.mean() * 100), "mas": float(v["mas"].mean() * 100),
              "tabla": (vt * [1, 100, 100]).round(2).reset_index().astype(str).to_dict("records")}
mac("vN", num(len(v), 0)); mac("vIgual", num(v.igual.mean() * 100, 1)); mac("vMas", num(v["mas"].mean() * 100, 1))
mac("vMasLargo", num(vt.loc[">12", "mas"] * 100, 1)); mac("vNLargo", num(int(vt.loc[">12", "n"]), 0))
mac("vMasSin", num(vt.loc["0", "mas"] * 100, 1))
mac("pactCero", num((df.VALOR_PACTADO == 0).mean() * 100, 1))
mac("pactBajo", num((df.VALOR_PACTADO < 1000).mean() * 100, 1))

# ------------------------------------------ concentracion por empresa
for nm, flag, lab in [("ed", "ed2", "descargue"), ("ec", "ec2", "cargue")]:
    e = df.groupby("EMPRESA_TRANSPORTE").agg(n=(flag, "size"), k=(flag, "sum")).sort_values("k", ascending=False)
    top = e.head(20)
    sh_k = top.k.sum() / e.k.sum() * 100
    sh_n = top.n.sum() / e.n.sum() * 100
    gran = e[e.n >= 100]
    todos = int(((gran.k / gran.n) >= 0.9).sum())
    R[f"empresas_{nm}"] = {"top20_share_largas": sh_k, "top20_share_registros": sh_n,
                           "empresas_ge100": int(len(gran)), "empresas_90pct_largas": todos,
                           "n_empresas_con_alguna": int((e.k > 0).sum())}
    mac(f"emp{nm}TopLargas", num(sh_k, 1)); mac(f"emp{nm}TopReg", num(sh_n, 1))
    mac(f"emp{nm}Todos", num(todos, 0)); mac(f"emp{nm}Gran", num(len(gran), 0))
dv0 = df.drop_duplicates(subset=["PLACA", "FECHASALIDACARGUE", "CODIGO_CARGUE", "CODIGO_DESCARGUE"])
rv = dv0[["HORAS_ESPERA_CARGUE", "HORAS_ESPERA_DESCARGUE"]].corr(method="spearman").iloc[0, 1]
R["spearman_ec_ed_viaje"] = float(rv)
mac("rEcEdViaje", num(rv, 2))

# -------------------------------------------------------- sensibilidad
def resumen_s(d):
    return {"n": len(d),
            "ec_media": d.HORAS_ESPERA_CARGUE.mean(), "ec2": (d.HORAS_ESPERA_CARGUE > 2).mean() * 100,
            "ed_media": d.HORAS_ESPERA_DESCARGUE.mean(), "ed2": (d.HORAS_ESPERA_DESCARGUE > 2).mean() * 100,
            "ca_med": d.HORAS_CARGUE.median(), "de_med": d.HORAS_DESCARGUE.median()}


base = resumen_s(df)
dB = resumen_s(dfB)
dv = df.drop_duplicates(subset=["PLACA", "FECHASALIDACARGUE", "CODIGO_CARGUE", "CODIGO_DESCARGUE"])
dV = resumen_s(dv)
dI = df[~out_any]
dIq = resumen_s(dI)
dN = resumen_s(df[(df.HORAS_ESPERA_CARGUE <= df.HORAS_ESPERA_CARGUE.quantile(.99)) &
                  (df.HORAS_ESPERA_DESCARGUE <= df.HORAS_ESPERA_DESCARGUE.quantile(.99)) &
                  (df.HORAS_CARGUE <= df.HORAS_CARGUE.quantile(.99)) &
                  (df.HORAS_DESCARGUE <= df.HORAS_DESCARGUE.quantile(.99))])
R["sens"] = {"base": base, "con_duplicados": dB, "nivel_viaje": dV, "sin_iqr": dIq, "sin_p99": dN}
with open(f"{OUT}/tables/table_sens.tex", "w") as f:
    f.write("\\begin{tabular}{lrrrrrr}\n\\toprule\n")
    f.write("Variante & Registros & \\shortstack{Esp. carg.\\\\media (h)} & \\shortstack{Esp. carg.\\\\$>2$ h (\\%)} & "
            "\\shortstack{Esp. desc.\\\\media (h)} & \\shortstack{Esp. desc.\\\\$>2$ h (\\%)} & "
            "\\shortstack{Cargue/desc.\\\\med. (h)} \\\\\n\\midrule\n")
    for nm, d in [("Base (limpia)", base), ("Con duplicados", dB), ("Un registro por viaje", dV),
                  ("Sin atípicos $>$ P99", dN), ("Sin atípicos IQR", dIq)]:
        f.write(f"{nm} & {num(d['n'], 0)} & {num(d['ec_media'])} & {num(d['ec2'], 1)} & {num(d['ed_media'])} & "
                f"{num(d['ed2'], 1)} & {num(d['ca_med'])}/{num(d['de_med'])} \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n")
mac("sensIqrN", num(dIq["n"], 0)); mac("sensIqrPct", num((1 - dIq["n"] / len(df)) * 100, 1))
mac("sensPNN", num(dN["n"], 0)); mac("sensPPct", num((1 - dN["n"] / len(df)) * 100, 1))
mac("sensViajeN", num(dV["n"], 0))
mac("sensIqrEcMedia", num(dIq["ec_media"], 2)); mac("sensIqrEdMedia", num(dIq["ed_media"], 2))
mac("sensPEcMedia", num(dN["ec_media"], 2)); mac("sensPEdMedia", num(dN["ed_media"], 2))
mac("sensViajeEcMedia", num(dV["ec_media"], 2)); mac("sensViajeEdMedia", num(dV["ed_media"], 2))
mac("sensViajeEcDos", num(dV["ec2"], 1)); mac("sensViajeEdDos", num(dV["ed2"], 1))
mac("sensDupEcMedia", num(dB["ec_media"], 2)); mac("sensDupEdMedia", num(dB["ed_media"], 2))
mac("sensDupN", num(dB["n"], 0))

# Kruskal por naturaleza tambien sin atipicos IQR (estabilidad del hallazgo)
tk = {}
for var, k in [("HORAS_ESPERA_CARGUE", "ec"), ("HORAS_ESPERA_DESCARGUE", "ed"),
               ("HORAS_CARGUE", "ca"), ("HORAS_DESCARGUE", "de")]:
    tk[k] = kruskal(var, "NATURALEZA", dI, NAT_ORDER)
    mac(f"kwIqr{k}E", num(tk[k]["eps2"], 3)); mac(f"kwIqr{k}P", pfmt(tk[k]["p"]))
R["kw_nat_sin_iqr"] = tk

# ---------------------------------------------------------------- salida
with open(f"{OUT}/results.json", "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=float)
with open(f"{OUT}/numeros.tex", "w", encoding="utf-8") as f:
    f.write("% Generado por eda_tiempos_logisticos.py; no editar a mano.\n")
    for k, v_ in M.items():
        assert k.isalpha(), k
        f.write(f"\\newcommand{{\\{k}}}{{{v_}}}\n")
print(json.dumps(R, ensure_ascii=False, indent=1, default=float)[:12000])
print("OK", len(M), "macros")
