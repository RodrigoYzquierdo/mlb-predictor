"""
MLB Predictor - Script de actualización diaria
Corre automáticamente via GitHub Actions cada día a las 9 AM CST
"""

import requests
import json
from datetime import datetime, timedelta
import pytz
import os

# ── Configuración ──────────────────────────────────────────────────────────────
MLB_API   = "https://statsapi.mlb.com/api/v1"
MEXICO_TZ = pytz.timezone("America/Mexico_City")
TODAY     = datetime.now(MEXICO_TZ).strftime("%Y-%m-%d")
YESTERDAY = (datetime.now(MEXICO_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

print(f"📅 Actualizando datos para: {TODAY}")
print(f"📊 Resultados de ayer: {YESTERDAY}")

# ── 1. Obtener partidos de hoy ────────────────────────────────────────────────
def get_games(date):
    url = f"{MLB_API}/schedule?sportId=1&date={date}&hydrate=probablePitcher(note),linescore"
    r = requests.get(url, timeout=10)
    data = r.json()
    games = []
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            home = g["teams"]["home"]
            away = g["teams"]["away"]
            game = {
                "id":       g["gamePk"],
                "status":   g["status"]["abstractGameState"],  # Preview / Live / Final
                "home":     (home.get("team",{}).get("abbreviation") or home.get("team",{}).get("teamCode","UNK")).upper(),
                "away":     (away.get("team",{}).get("abbreviation") or away.get("team",{}).get("teamCode","UNK")).upper(),
                "home_name":home["team"]["name"],
                "away_name":away["team"]["name"],
                "time":     g.get("gameDate", ""),
                "home_score": home.get("score", 0) if g["status"]["abstractGameState"] == "Final" else None,
                "away_score": away.get("score", 0) if g["status"]["abstractGameState"] == "Final" else None,
            }
            # Pitcher abridor confirmado
            for side in ["home", "away"]:
                pp = g["teams"][side].get("probablePitcher", {})
                game[f"{side}_pitcher"] = pp.get("fullName", None)
                game[f"{side}_pitcher_id"] = pp.get("id", None)
            games.append(game)
    return games

# ── 2. Obtener ERA del pitcher ────────────────────────────────────────────────
def get_pitcher_era(pitcher_id):
    if not pitcher_id:
        return None
    try:
        url = f"{MLB_API}/people/{pitcher_id}/stats?stats=season&group=pitching&season=2026"
        r = requests.get(url, timeout=5)
        stats = r.json().get("stats", [])
        for s in stats:
            splits = s.get("splits", [])
            if splits:
                return round(float(splits[0]["stat"].get("era", 0)), 2)
    except:
        pass
    return None

# ── 3. Obtener standings ──────────────────────────────────────────────────────
def get_standings():
    url = f"{MLB_API}/standings?leagueId=103,104&season=2026&standingsTypes=regularSeason"
    r = requests.get(url, timeout=10)
    data = r.json()
    teams = {}
    for record in data.get("records", []):
        for tr in record.get("teamRecords", []):
            # La API puede devolver 'abbreviation' o 'teamCode' según la versión
            team_info = tr.get("team", {})
            abbr = (team_info.get("abbreviation") or
                    team_info.get("teamCode") or
                    team_info.get("clubName", "UNK")).upper()
            w = tr.get("wins", 0)
            l = tr.get("losses", 0)
            pct_raw = tr.get("winningPercentage", "0.000")
            try:
                pct = round(float(pct_raw), 3)
            except (ValueError, TypeError):
                pct = round(w / (w + l), 3) if (w + l) > 0 else 0.500
            teams[abbr] = {
                "name": team_info.get("name", abbr),
                "w":    w,
                "l":    l,
                "pct":  pct,
                "div":  record.get("division", {}).get("name", ""),
                "conf": record.get("league", {}).get("name", ""),
            }
    return teams

# ── 4. Calcular predicción del modelo ────────────────────────────────────────
TEAM_STATS = {
    # ERA equipo y OPS aproximados (se actualizan semanalmente aquí)
    # formato: abbr: {era, obp, slg, rdiff}
    "TB":  {"era":3.42,"obp":.318,"slg":.422,"rdiff":82},
    "NYY": {"era":3.61,"obp":.325,"slg":.441,"rdiff":62},
    "TOR": {"era":4.05,"obp":.308,"slg":.408,"rdiff":3},
    "BAL": {"era":4.21,"obp":.305,"slg":.399,"rdiff":-4},
    "BOS": {"era":4.58,"obp":.310,"slg":.403,"rdiff":-36},
    "CLE": {"era":3.55,"obp":.315,"slg":.415,"rdiff":55},
    "CWS": {"era":3.88,"obp":.312,"slg":.418,"rdiff":35},
    "MIN": {"era":4.12,"obp":.309,"slg":.405,"rdiff":0},
    "DET": {"era":4.72,"obp":.298,"slg":.382,"rdiff":-74},
    "KC":  {"era":4.65,"obp":.300,"slg":.388,"rdiff":-60},
    "SEA": {"era":3.48,"obp":.311,"slg":.410,"rdiff":30},
    "TEX": {"era":4.02,"obp":.312,"slg":.420,"rdiff":12},
    "ATH": {"era":3.98,"obp":.307,"slg":.401,"rdiff":15},
    "HOU": {"era":4.28,"obp":.308,"slg":.408,"rdiff":-5},
    "LAA": {"era":4.88,"obp":.295,"slg":.375,"rdiff":-80},
    "MIL": {"era":3.38,"obp":.320,"slg":.435,"rdiff":95},
    "STL": {"era":3.82,"obp":.314,"slg":.418,"rdiff":40},
    "PIT": {"era":3.95,"obp":.310,"slg":.405,"rdiff":25},
    "CHC": {"era":3.91,"obp":.316,"slg":.422,"rdiff":22},
    "CIN": {"era":4.18,"obp":.308,"slg":.400,"rdiff":5},
    "ATL": {"era":3.25,"obp":.332,"slg":.458,"rdiff":145},
    "PHI": {"era":3.88,"obp":.318,"slg":.430,"rdiff":42},
    "WSH": {"era":4.10,"obp":.311,"slg":.410,"rdiff":18},
    "MIA": {"era":4.45,"obp":.302,"slg":.392,"rdiff":-22},
    "NYM": {"era":4.30,"obp":.306,"slg":.398,"rdiff":-20},
    "LAD": {"era":3.18,"obp":.335,"slg":.462,"rdiff":118},
    "AZ":  {"era":3.78,"obp":.315,"slg":.420,"rdiff":38},
    "SD":  {"era":3.65,"obp":.320,"slg":.428,"rdiff":50},
    "SF":  {"era":4.55,"obp":.302,"slg":.388,"rdiff":-40},
    "COL": {"era":5.12,"obp":.298,"slg":.380,"rdiff":-98},
}

def calc_model(h_abbr, a_abbr, standings, h_sera=None, a_sera=None):
    hs_data = standings.get(h_abbr, {})
    as_data = standings.get(a_abbr, {})
    ht = TEAM_STATS.get(h_abbr, {"era":4.0,"obp":.310,"slg":.410,"rdiff":0})
    at = TEAM_STATS.get(a_abbr, {"era":4.0,"obp":.310,"slg":.410,"rdiff":0})

    h_w, h_l = hs_data.get("w", 40), hs_data.get("l", 40)
    a_w, a_l = as_data.get("w", 40), as_data.get("l", 40)
    h_wp = h_w / (h_w + h_l) if (h_w + h_l) > 0 else 0.5
    a_wp = a_w / (a_w + a_l) if (a_w + a_l) > 0 else 0.5

    mixed = h_sera is not None and a_sera is not None
    hs, as_ = 0, 0

    hs  += h_wp * 35;  as_ += a_wp * 35
    if mixed:
        h_pitch = ht["era"] * 0.4 + h_sera * 0.6
        a_pitch = at["era"] * 0.4 + a_sera * 0.6
        hs  += (5.0 - min(h_pitch, 5.5)) * 8
        as_ += (5.0 - min(a_pitch, 5.5)) * 8
    else:
        hs  += (5.0 - min(ht["era"], 5.5)) * 6
        as_ += (5.0 - min(at["era"], 5.5)) * 6

    hs  += (ht["obp"] - 0.280) * 80;  as_ += (at["obp"] - 0.280) * 80
    hs  += (ht["slg"] - 0.380) * 50;  as_ += (at["slg"] - 0.380) * 50
    hs  += max(-1, min(1, ht["rdiff"] / 150)) * 8
    as_ += max(-1, min(1, at["rdiff"] / 150)) * 8
    hs  *= 1.055

    total = hs + as_
    hp    = round(hs / total * 100)
    diff  = abs(hp - 50)
    conf  = "Alta" if diff > 18 else ("Media" if diff > 10 else "Baja")
    return {"hp": hp, "ap": 100 - hp, "conf": conf, "mixed": mixed, "diff": diff}

# ── 5. Cargar historial existente ─────────────────────────────────────────────
HISTORY_FILE = "public/history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# ── 6. Actualizar historial con resultados de ayer ────────────────────────────
def update_history_with_yesterday(history, yesterday_games, standings):
    existing_keys = {f"{h['home']}-{h['away']}-{h['date']}" for h in history}
    added = 0
    for g in yesterday_games:
        if g["status"] != "Final":
            continue
        if g["home_score"] is None:
            continue
        key = f"{g['home']}-{g['away']}-{YESTERDAY}"
        if key in existing_keys:
            continue
        pred = calc_model(g["home"], g["away"], standings)
        fav  = g["home"] if pred["hp"] >= 50 else g["away"]
        win  = g["home"] if g["home_score"] > g["away_score"] else g["away"]
        hit  = fav == win
        history.append({
            "date":   YESTERDAY,
            "home":   g["home"],
            "away":   g["away"],
            "hp":     pred["hp"],
            "pred":   fav,
            "actual": f"{g['away']} {g['away_score']}-{g['home_score']} {g['home']}" if g["away_score"] > g["home_score"] else f"{g['home']} {g['home_score']}-{g['away_score']} {g['away']}",
            "hit":    hit,
        })
        added += 1
    print(f"✅ {added} resultados de ayer agregados al historial")
    return history

# ── 7. Main ───────────────────────────────────────────────────────────────────
def main():
    print("\n🔄 Obteniendo standings...")
    standings = get_standings()
    print(f"   {len(standings)} equipos cargados")

    print("\n🔄 Obteniendo partidos de hoy...")
    today_games = get_games(TODAY)
    print(f"   {len(today_games)} partidos hoy")

    print("\n🔄 Obteniendo ERAs de abridores confirmados...")
    for g in today_games:
        g["home_era"] = get_pitcher_era(g.get("home_pitcher_id"))
        g["away_era"] = get_pitcher_era(g.get("away_pitcher_id"))
        if g["home_pitcher"]:
            era_str = f"ERA {g['home_era']}" if g["home_era"] else "ERA N/A"
            print(f"   {g['home_pitcher']} ({g['home']}) — {era_str}")

    print("\n🔄 Calculando Top 5...")
    predictions = []
    for g in today_games:
        if g["status"] == "Final":
            continue
        pred = calc_model(g["home"], g["away"], standings, g.get("home_era"), g.get("away_era"))
        predictions.append({**g, **pred})

    top5 = sorted(predictions, key=lambda x: x["diff"], reverse=True)[:5]
    print(f"   Top 5 calculado. Líder: {top5[0]['away']} @ {top5[0]['home']} ({top5[0]['conf']} confianza)")

    print("\n🔄 Actualizando historial...")
    yesterday_games = get_games(YESTERDAY)
    history = load_history()
    history = update_history_with_yesterday(history, yesterday_games, standings)
    save_history(history)

    # Calcular stats del historial
    hits  = sum(1 for h in history if h["hit"])
    total = len(history)
    pct   = round(hits / total * 100) if total > 0 else 0
    streak = 0
    if history:
        st = "W" if history[-1]["hit"] else "L"
        for h in reversed(history):
            if h["hit"] == (st == "W"): streak += 1
            else: break

    # Guardar JSON con todos los datos del día
    output = {
        "date":      TODAY,
        "updated":   datetime.now(MEXICO_TZ).strftime("%d/%m/%Y %H:%M CST"),
        "standings": standings,
        "top5":      top5,
        "history":   history[-50:],  # últimos 50 para el HTML
        "stats": {
            "hits":    hits,
            "total":   total,
            "pct":     pct,
            "streak":  streak,
            "streak_type": "W" if (history and history[-1]["hit"]) else "L",
        }
    }

    with open("public/data.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n✅ public/data.json generado — {total} predicciones históricas, {pct}% precisión")
    print("🚀 Listo para deploy en Netlify\n")

if __name__ == "__main__":
    main()
