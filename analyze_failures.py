"""
MLB Predictor - Analisis de fallos del modelo
Analiza el historial para encontrar sesgos sistematicos:
calibracion, sesgo local/visitante, equipos problematicos, efecto estadio.

Uso: corre via GitHub Actions (analyze.yml). Solo imprime un reporte, no modifica nada.
"""

import json

HISTORY_FILE = "public/history.json"

PARK_FACTORS = {
    "COL": 1.18, "BOS": 1.08, "CIN": 1.06, "TEX": 1.05, "PHI": 1.04,
    "CHC": 1.03, "MIL": 1.02, "NYY": 1.02, "ATL": 1.01, "HOU": 1.00,
    "STL": 1.00, "TOR": 1.00, "MIN": 0.99, "AZ": 0.99, "DET": 0.99,
    "LAD": 0.98, "ATH": 0.98, "MIA": 0.97, "CLE": 0.97, "WSH": 0.97,
    "BAL": 0.97, "PIT": 0.97, "CWS": 0.96, "KC": 0.96, "TB": 0.96,
    "NYM": 0.96, "SF": 0.95, "LAA": 0.95, "SEA": 0.94, "SD": 0.94,
}

def pct(h, t):
    return f"{round(h/t*100)}% ({h}/{t})" if t > 0 else "— (0)"

def main():
    with open(HISTORY_FILE) as f:
        history = json.load(f)

    # Enriquecer cada registro
    for r in history:
        r["pick_is_home"] = r["pred"] == r["home"]
        r["pick_prob"]    = r["hp"] if r["pick_is_home"] else 100 - r["hp"]
        r["park"]         = PARK_FACTORS.get(r["home"], 1.0)

    total = len(history)
    hits  = sum(1 for r in history if r["hit"])
    print(f"{'='*60}")
    print(f"ANALISIS DE FALLOS — {total} predicciones, {pct(hits, total)} global")
    print(f"{'='*60}")

    # ── 1. CALIBRACION ──────────────────────────────────────────
    print(f"\n1. CALIBRACION (prob. predicha vs realidad)")
    print(f"   Si 'Real' < 'Predicho', el modelo esta sobreconfiado en ese rango\n")
    buckets = [(50,55),(55,60),(60,65),(65,70),(70,76)]
    for lo, hi in buckets:
        sub = [r for r in history if lo <= r["pick_prob"] < hi]
        if not sub:
            continue
        h = sum(1 for r in sub if r["hit"])
        avg_pred = sum(r["pick_prob"] for r in sub) / len(sub)
        real = h / len(sub) * 100
        gap = real - avg_pred
        flag = "SOBRECONFIADO" if gap < -5 else ("SUBCONFIADO" if gap > 5 else "OK")
        print(f"   Predicho {lo}-{hi}%: promedio {avg_pred:.0f}% | Real {real:.0f}% "
              f"({h}/{len(sub)}) | Gap {gap:+.0f}pp [{flag}]")

    # ── 2. SESGO LOCAL / VISITANTE ──────────────────────────────
    print(f"\n2. SESGO LOCAL vs VISITANTE")
    home_picks = [r for r in history if r["pick_is_home"]]
    away_picks = [r for r in history if not r["pick_is_home"]]
    hh = sum(1 for r in home_picks if r["hit"])
    ah = sum(1 for r in away_picks if r["hit"])
    print(f"   Cuando elige al LOCAL:     {pct(hh, len(home_picks))}")
    print(f"   Cuando elige al VISITANTE: {pct(ah, len(away_picks))}")

    # ── 3. EFECTO ESTADIO ───────────────────────────────────────
    print(f"\n3. EFECTO ESTADIO (park factor del estadio donde se jugo)")
    for label, cond in [
        ("Ofensivos (>=1.04, Coors/Fenway/etc)", lambda r: r["park"] >= 1.04),
        ("Neutros (0.98-1.03)",                  lambda r: 0.98 <= r["park"] < 1.04),
        ("De pitcheo (<0.98)",                   lambda r: r["park"] < 0.98),
    ]:
        sub = [r for r in history if cond(r)]
        h = sum(1 for r in sub if r["hit"])
        print(f"   {label}: {pct(h, len(sub))}")

    # ── 4. EQUIPOS QUE TRAICIONAN AL MODELO ────────────────────
    print(f"\n4. EQUIPOS MAS ELEGIDOS Y SU RENDIMIENTO (min. 10 elecciones)")
    team_stats = {}
    for r in history:
        t = r["pred"]
        if t not in team_stats:
            team_stats[t] = {"h": 0, "t": 0}
        team_stats[t]["t"] += 1
        if r["hit"]:
            team_stats[t]["h"] += 1
    ranked = sorted(
        [(t, s) for t, s in team_stats.items() if s["t"] >= 10],
        key=lambda x: x[1]["h"] / x[1]["t"]
    )
    print(f"   Peores (el modelo los elige y pierden):")
    for t, s in ranked[:5]:
        print(f"     {t}: {pct(s['h'], s['t'])}")
    print(f"   Mejores (elecciones confiables):")
    for t, s in ranked[-5:]:
        print(f"     {t}: {pct(s['h'], s['t'])}")

    # ── 5. EQUIPOS QUE DAN LA SORPRESA ──────────────────────────
    print(f"\n5. EQUIPOS QUE MAS SORPRENDEN (ganan cuando el modelo los descarta, min. 8)")
    upset_stats = {}
    for r in history:
        underdog = r["away"] if r["pred"] == r["home"] else r["home"]
        if underdog not in upset_stats:
            upset_stats[underdog] = {"w": 0, "t": 0}
        upset_stats[underdog]["t"] += 1
        if not r["hit"]:
            upset_stats[underdog]["w"] += 1
    ranked_u = sorted(
        [(t, s) for t, s in upset_stats.items() if s["t"] >= 8],
        key=lambda x: x[1]["w"] / x[1]["t"], reverse=True
    )
    for t, s in ranked_u[:5]:
        print(f"     {t}: gana {pct(s['w'], s['t'])} de las veces que el modelo lo descarta")

    # ── 6. TENDENCIA MENSUAL ────────────────────────────────────
    print(f"\n6. TENDENCIA MENSUAL")
    months = {}
    for r in history:
        m = r["date"][:7]
        if m not in months:
            months[m] = {"h": 0, "t": 0}
        months[m]["t"] += 1
        if r["hit"]:
            months[m]["h"] += 1
    for m in sorted(months):
        s = months[m]
        print(f"   {m}: {pct(s['h'], s['t'])}")

    print(f"\n{'='*60}")
    print(f"FIN DEL ANALISIS")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
