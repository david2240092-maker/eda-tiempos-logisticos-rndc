# eda-tiempos-logisticos-rndc
# Esperas y operaciones de cargue y descargue en el transporte de carga en Colombia

Análisis exploratorio de datos (EDA) de los tiempos logísticos de cada viaje de vehículos de carga en Colombia, con datos de enero de 2021 del Registro Nacional de Despacho de Carga (RNDC) del Ministerio de Transporte.

Proyecto de la asignatura Estadística I, Ingeniería Industrial, Universidad Industrial de Santander (UIS).

**Autores:** David Alejandro Mateus, Luis Felipe Acuña Uribe y Miguel Angello Velandia Leon.

## Datos

- Conjunto: *Tiempos Logísticos de cada viaje de vehículos de carga* (RNDC, MinTransporte).
- Fuente: https://www.datos.gov.co/d/tfrd-amb4
- Descarga del CSV: botón **Exportar → CSV** en esa página.
- El archivo no se incluye en este repositorio por su tamaño (836 013 registros).

## Cómo ejecutarlo

### Opción 1: en Colab (no requiere instalar nada)

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/david2240092-maker/eda-tiempos-logisticos-rndc/blob/main/EDA_Tiempos_Logisticos_Colab.ipynb)

1. Abre el cuaderno con el botón de arriba.
2. En el menú, elige **Entorno de ejecución → Ejecutar todas**.
3. El cuaderno descarga los datos solo. Si el portal lo bloquea, pide subir el archivo CSV.
4. La ejecución tarda varios minutos.

### Opción 2: en tu computador

Requiere Python 3 con `pandas`, `numpy`, `scipy` y `matplotlib`:

```bash
pip install pandas numpy scipy matplotlib
python3 eda_tiempos_logisticos.py tiempos_logisticos.csv salida
```

El segundo argumento (`salida`) es la carpeta donde se guardan los resultados.

## Qué contiene

| Archivo | Descripción |
|---|---|
| `EDA_Tiempos_Logisticos_Colab.ipynb` | Cuaderno con el análisis completo, explicado paso a paso |
| `eda_tiempos_logisticos.py` | Script que reproduce todas las cifras, figuras y tablas del artículo |
| `salida/figs/` | Figuras del artículo (PDF y PNG) |
| `salida/tables/` | Tablas del artículo (LaTeX) |
| `salida/results.json` | Todas las cifras citadas en el texto, en formato legible |

## Qué hace el análisis

1. Limpia los datos: elimina duplicados, campos vacíos y tiempos imposibles (7,6 % de los registros).
2. Describe las esperas y la duración de las operaciones de cargue y descargue.
3. Compara por tipo de carga, municipio, día de la semana y hora de llegada con pruebas no paramétricas (Kruskal–Wallis, Mann–Whitney, chi-cuadrado, Spearman) y tamaños de efecto.
4. Verifica que los resultados se sostienen con otras reglas de limpieza.
