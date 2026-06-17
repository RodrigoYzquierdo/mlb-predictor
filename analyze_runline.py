"""
MLB Predictor - Análisis de Run Line
Analiza el historial Top 5 para evaluar si apostar al spread de 1.5 carreras
es más rentable que el moneyline simple.

Uso: python analyze_runline.py
Corre desde la raíz del repo (necesita public/history.json)
"""

import json
import os

HISTORY_FILE = "public/history.json"

# Cuotas promedio (referencia para cálculo de ROI simulado)
ODDS_FAVE_ML    = 1.50  # favorito gana (moneyline)
ODDS_UPSET_ML   = 2.10  # no favorito gana (moneyline)
ODDS_RUNLINE    = 2.50  # favorito gana por 2+ carreras (run line -1.5)

def parse_score(actual, home, away):
    """
    Extrae margen de victoria del campo 'actual'.
    Formato: "AWAY X-Y HOME" o "HOME X-Y AWAY"
    Retorna (ganador, margen)
    """
    try:
        parts  = actual.split()
        # Formato: TEAM score-score TEAM
        # Ej: "NYY 5-3 BOS" o "BOS 3-5 NYY"
        winner_team = parts[0]
        scores      = parts[1].split("-")
        score_w     = int(scores[0])
        score_l     = int(scores[1])
        margin      = score_w - score_l
        return winner_team, margin
    except:
        return None, None

def main():
    if not os.path.exists(HISTORY_FILE):
        print(f"ERROR: No se encontró {HISTORY_FILE}")
        return

    with open(HISTORY_FILE) as f:
        history = json.load(f)

    print(f"Partidos en historial: {len(history)}")
    print()

    # Contadores
    total          = 0
    model_correct  = 0  # modelo acertó el ganador
    model_wrong    = 0  # modelo falló

    # Cuando el modelo acierta:
    won_by_1       = 0  # ganó por exactamente 1 carrera (no cubre run line)
    won_by_2plus   = 0  # ganó por 2+ carreras (cubre run line -1.5)

    # Simulación de ROI con apuesta de $100 por partido
    bankroll_ml        = 0.0  # solo moneyline del favorito del modelo
    bankroll_rl        = 0.0  # run line cuando modelo acierta
    bankroll_combined  = 0.0  # moneyline si margen esperado alto, RL si muy alto

    margins = []  # todos los márgenes cuando el modelo acierta

    for h in history:
        total += 1
        winner, margin = parse_score(h["actual"], h["home"], h["away"])

        if winner is None:
            continue

        hit = h["hit"]

        # Simulación moneyline: apostamos $100 al favorito del modelo siempre
        if hit:
            model_correct += 1
            bankroll_ml += 50   # ganamos $50 (cuota 1.5 → $100 × 0.5 profit)
            margins.append(margin)

            if margin == 1:
                won_by_1     += 1
                bankroll_rl  -= 100  # perdemos el run line
            elif margin >= 2:
                won_by_2plus += 1
                bankroll_rl  += 150  # ganamos $150 (cuota 2.5 → $100 × 1.5 profit)
            # En caso de empate técnico (no debería existir en MLB)
        else:
            model_wrong   += 1
            bankroll_ml   -= 100  # perdemos moneyline
            bankroll_rl   -= 100  # perdemos run line también

    # Estadísticas de márgenes
    avg_margin    = sum(margins) / len(margins) if margins else 0
    median_margin = sorted(margins)[len(margins)//2] if margins else 0

    margin_dist = {}
    for m in margins:
        margin_dist[m] = margin_dist.get(m, 0) + 1

    pct_correct    = round(model_correct / total * 100, 1) if total else 0
    pct_by_1       = round(won_by_1 / model_correct * 100, 1) if model_correct else 0
    pct_by_2plus   = round(won_by_2plus / model_correct * 100, 1) if model_correct else 0
    pct_covers_rl  = round(won_by_2plus / total * 100, 1) if total else 0

    # ROI por partido
    roi_ml = round(bankroll_ml / (total * 100) * 100, 1)
    roi_rl = round(bankroll_rl / (total * 100) * 100, 1)

    print("=" * 55)
    print("ANÁLISIS RUN LINE — MLB Predictor Top 5")
    print("=" * 55)

    print(f"\n📊 RESUMEN GENERAL")
    print(f"   Total partidos Top 5:      {total}")
    print(f"   Modelo acertó ganador:     {model_correct} ({pct_correct}%)")
    print(f"   Modelo falló:              {model_wrong}")

    print(f"\n🏆 CUANDO EL MODELO ACIERTA ({model_correct} partidos)")
    print(f"   Ganó por 1 carrera exacta: {won_by_1} ({pct_by_1}%)  ← NO cubre run line")
    print(f"   Ganó por 2+ carreras:      {won_by_2plus} ({pct_by_2plus}%)  ← SÍ cubre run line")
    print(f"   Margen promedio:           {round(avg_margin, 2)} carreras")
    print(f"   Margen mediano:            {median_margin} carreras")

    print(f"\n📈 DISTRIBUCIÓN DE MÁRGENES (cuando acierta)")
    for margin in sorted(margin_dist.keys()):
        pct = round(margin_dist[margin] / model_correct * 100, 1)
        bar = "█" * int(pct / 2)
        print(f"   {margin:2d} carrera(s): {margin_dist[margin]:3d} partidos ({pct:4.1f}%) {bar}")

    print(f"\n💰 SIMULACIÓN ROI (apuesta $100 por partido)")
    print(f"   Cuotas usadas: ML favorito={ODDS_FAVE_ML}x | Run line={ODDS_RUNLINE}x")
    print(f"")
    print(f"   Estrategia A — Solo moneyline:")
    print(f"     Resultado: ${bankroll_ml:+.0f}  |  ROI: {roi_ml:+.1f}%")
    print(f"")
    print(f"   Estrategia B — Solo run line (-1.5):")
    print(f"     Resultado: ${bankroll_rl:+.0f}  |  ROI: {roi_rl:+.1f}%")
    print(f"")

    # Estrategia C: run line solo cuando prob > umbral
    for threshold in [60, 62, 65]:
        bank_c = 0.0
        bets_c = 0
        hits_c = 0
        for h in history:
            prob = max(h["hp"], 100 - h["hp"])
            if prob < threshold:
                continue
            bets_c += 1
            winner, margin = parse_score(h["actual"], h["home"], h["away"])
            if h["hit"] and margin and margin >= 2:
                bank_c += 150
                hits_c += 1
            else:
                bank_c -= 100
        roi_c = round(bank_c / (bets_c * 100) * 100, 1) if bets_c else 0
        cover_pct = round(hits_c / bets_c * 100, 1) if bets_c else 0
        print(f"   Estrategia C — Run line solo si prob ≥{threshold}%:")
        print(f"     Partidos: {bets_c} | Cubren RL: {hits_c} ({cover_pct}%) | ROI: {roi_c:+.1f}%")

    print(f"\n🎯 CONCLUSIÓN")
    cover_rate = round(won_by_2plus / total * 100, 1)
    print(f"   De todos los Top 5, el favorito cubre RL en {cover_rate}% de casos")
    print(f"   Para que run line sea rentable con cuota 2.5x se necesita ≥40% de cobertura")
    if cover_rate >= 40:
        print(f"   ✅ El run line ES viable estadísticamente ({cover_rate}% ≥ 40%)")
    else:
        print(f"   ❌ El run line NO es viable aún ({cover_rate}% < 40%)")
    print("=" * 55)

if __name__ == "__main__":
    main()
