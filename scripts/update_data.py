"""
MLB Predictor - Script de actualizacion diaria
Corre automaticamente via GitHub Actions cada dia a las 9 AM CST
v2.0 - Bullpen stats, forma reciente, park factors, historial limpio
"""

import requests
import json
from datetime import datetime, timedelta
import pytz
import os

# Configuracion
MLB_API      = "https://statsapi.mlb.com/api/v1"
ODDS_API     = "https://api.the-odds-api.com/v4"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
MEXICO_TZ    = pytz.timezone("America/Mexico_City")
TODAY        = datetime.now(MEXICO_TZ).strftime("%Y-%m-%d")
YESTERDAY    = (datetime.now(MEXICO_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

print(f"Actualizando datos para: {TODAY}")
print(f"Resultados de ayer: {YESTERDAY}")

# Cargar pesos del modelo entrenado (regresion logistica)
import math
MODEL_WEIGHTS = None
try:
    with open("public/model_weights.json") as f:
        MODEL_WEIGHTS = json.load(f)
    print(f"   Modelo cargado: {MODEL_WEIGHTS['n_games']} partidos, "
          f"{round(MODEL_WEIGHTS['cv_accuracy']*100,1)}% cross-val")
except Exception as e:
    print(f"   model_weights.json no disponible, usando modelo heuristico: {e}")

NAME_TO_ABBR = {
    "Arizona Diamondbacks": "AZ",   "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",     "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",          "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",       "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",      "Detroit Tigers": "DET",
    "Houston Astros": "HOU",        "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",         "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",       "New York Mets": "NYM",
    "New York Yankees": "NYY",      "Athletics": "ATH",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",       "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",      "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",         "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",     "Washington Nationals": "WSH",
    # Nombres cortos (standings API)
    "D-backs": "AZ",    "Braves": "ATL",    "Orioles": "BAL",
    "Red Sox": "BOS",   "Cubs": "CHC",      "White Sox": "CWS",
    "Reds": "CIN",      "Guardians": "CLE", "Rockies": "COL",
    "Tigers": "DET",    "Astros": "HOU",    "Royals": "KC",
    "Angels": "LAA",    "Dodgers": "LAD",   "Marlins": "MIA",
    "Brewers": "MIL",   "Twins": "MIN",     "Mets": "NYM",
    "Yankees": "NYY",   "Phillies": "PHI",  "Pirates": "PIT",
    "Padres": "SD",     "Giants": "SF",     "Mariners": "SEA",
    "Cardinals": "STL", "Rays": "TB",       "Rangers": "TEX",
    "Blue Jays": "TOR", "Nationals": "WSH",
    # The Odds API
    "Oakland Athletics": "ATH",
}

TEAM_IDS = {
    "AZ":133,"ATL":144,"BAL":110,"BOS":111,"CHC":112,
    "CWS":145,"CIN":113,"CLE":114,"COL":115,"DET":116,
    "HOU":117,"KC":118,"LAA":108,"LAD":119,"MIA":146,
    "MIL":158,"MIN":142,"NYM":121,"NYY":147,"ATH":133,
    "PHI":143,"PIT":134,"SD":135,"SF":137,"SEA":136,
    "STL":138,"TB":139,"TEX":140,"TOR":141,"WSH":120,
}

# Park factors — multplicador de runs en ese estadio (1.0 = neutro)
# >1.0 = favorece la ofensiva (mas runs), <1.0 = favorece pitcheo
PARK_FACTORS = {
    "COL": 1.18,  # Coors Field - el mas extremo de MLB
    "BOS": 1.08,  # Fenway Park - el monstruo verde
    "CIN": 1.06,  # Great American Ball Park
    "TEX": 1.05,  # Globe Life Field
    "PHI": 1.04,  # Citizens Bank Park
    "CHC": 1.03,  # Wrigley Field
    "MIL": 1.02,  # American Family Field
    "NYY": 1.02,  # Yankee Stadium
    "ATL": 1.01,  # Truist Park
    "HOU": 1.00,  # Minute Maid Park
    "STL": 1.00,  # Busch Stadium
    "TOR": 1.00,  # Rogers Centre
    "MIN": 0.99,  # Target Field
    "AZ":  0.99,  # Chase Field
    "DET": 0.99,  # Comerica Park
    "LAD": 0.98,  # Dodger Stadium
    "ATH": 0.98,  # Oakland Coliseum
    "MIA": 0.97,  # loanDepot park
    "CLE": 0.97,  # Progressive Field
    "WSH": 0.97,  # Nationals Park
    "BAL": 0.97,  # Camden Yards
    "PIT": 0.97,  # PNC Park
    "CWS": 0.96,  # Guaranteed Rate Field
    "KC":  0.96,  # Kauffman Stadium
    "TB":  0.96,  # Tropicana Field
    "NYM": 0.96,  # Citi Field
    "SF":  0.95,  # Oracle Park
    "LAA": 0.95,  # Angel Stadium
    "SEA": 0.94,  # T-Mobile Park
    "SD":  0.94,  # Petco Park
}

def get_abbr(team_dict):
    name = team_dict.get("name", "UNK")
    return NAME_TO_ABBR.get(name, name[:3].upper())

# 1. Obtener partidos
def get_games(date):
    url = f"{MLB_API}/schedule?sportId=1&date={date}&hydrate=probablePitcher(note),linescore"
    r = requests.get(url, timeout=10)
    data = r.json()
    games = []
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            home = g["teams"]["home"]
            away = g["teams"]["away"]
            status = g["status"]["abstractGameState"]
            game = {
                "id":         g["gamePk"],
                "status":     status,
                "home":       get_abbr(home.get("team", {})),
                "away":       get_abbr(away.get("team", {})),
                "home_name":  home.get("team", {}).get("name", ""),
                "away_name":  away.get("team", {}).get("name", ""),
                "time":       g.get("gameDate", ""),
                "home_score": home.get("score", 0) if status == "Final" else None,
                "away_score": away.get("score", 0) if status == "Final" else None,
            }
            for side in ["home", "away"]:
                pp = g["teams"][side].get("probablePitcher", {})
                game[f"{side}_pitcher"]    = pp.get("fullName", None)
                game[f"{side}_pitcher_id"] = pp.get("id", None)
            games.append(game)
    return games

# 2. Obtener ERA del pitcher abridor
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

# 3. Obtener standings
def get_standings():
    url = f"{MLB_API}/standings?leagueId=103,104&season=2026&standingsTypes=regularSeason"
    r = requests.get(url, timeout=10)
    data = r.json()
    teams = {}
    for record in data.get("records", []):
        for tr in record.get("teamRecords", []):
            team = tr.get("team", {})
            name = team.get("name", "UNK")
            abbr = NAME_TO_ABBR.get(name, name[:3].upper())
            w  = tr.get("wins", 0)
            l  = tr.get("losses", 0)
            rs = tr.get("runsScored", 0)
            ra = tr.get("runsAllowed", 0)
            # Forma reciente: record de ultimos 10 juegos
            streak_info = tr.get("streak", {})
            last10      = tr.get("records", {}).get("splitRecords", [])
            last10_w = last10_l = None
            for rec in last10:
                if rec.get("type") == "lastTen":
                    last10_w = rec.get("wins", 0)
                    last10_l = rec.get("losses", 0)
                    break
            teams[abbr] = {
                "name":    name,
                "w":       w,
                "l":       l,
                "pct":     round(w / (w + l), 3) if (w + l) > 0 else 0.500,
                "div":     record.get("division", {}).get("name", ""),
                "conf":    record.get("league", {}).get("name", ""),
                "rdiff":   rs - ra if (rs or ra) else 0,
                "last10_w": last10_w,
                "last10_l": last10_l,
                "last10_pct": round(last10_w / 10, 3) if last10_w is not None else None,
            }
    return teams

# 4. Obtener stats de pitcheo y bateo (abridor + bullpen)
def get_team_stats():
    team_stats = {}

    # ERA del staff completo (incluye bullpen)
    try:
        url = f"{MLB_API}/teams/stats?season=2026&group=pitching&stats=season&sportId=1"
        r = requests.get(url, timeout=10)
        data = r.json()
        for split in data.get("stats", [{}])[0].get("splits", []):
            team = split.get("team", {})
            abbr = NAME_TO_ABBR.get(team.get("name", ""), team.get("name", "")[:3].upper())
            stat = split.get("stat", {})
            try:
                era = round(float(stat.get("era", "4.00")), 2)
            except:
                era = 4.00
            try:
                whip = round(float(stat.get("whip", "1.30")), 3)
            except:
                whip = 1.30
            try:
                k9 = round(float(stat.get("strikeoutsPer9Inn", "8.0")), 2)
            except:
                k9 = 8.0
            if abbr not in team_stats:
                team_stats[abbr] = {}
            team_stats[abbr]["era"]  = era
            team_stats[abbr]["whip"] = whip
            team_stats[abbr]["k9"]   = k9
        print(f"   Pitching stats: {len(team_stats)} equipos")
    except Exception as e:
        print(f"   Error pitching stats: {e}")

    # Bullpen especifico (pitchers en relevo)
    try:
        url = f"{MLB_API}/teams/stats?season=2026&group=pitching&stats=season&sportId=1&pitchingType=bullpen"
        r = requests.get(url, timeout=10)
        data = r.json()
        splits = data.get("stats", [{}])[0].get("splits", [])
        for split in splits:
            team = split.get("team", {})
            abbr = NAME_TO_ABBR.get(team.get("name", ""), team.get("name", "")[:3].upper())
            stat = split.get("stat", {})
            try:
                bp_era = round(float(stat.get("era", "4.00")), 2)
            except:
                bp_era = 4.00
            try:
                bp_whip = round(float(stat.get("whip", "1.30")), 3)
            except:
                bp_whip = 1.30
            if abbr in team_stats:
                team_stats[abbr]["bullpen_era"]  = bp_era
                team_stats[abbr]["bullpen_whip"] = bp_whip
        print(f"   Bullpen stats: {len([t for t in team_stats if 'bullpen_era' in team_stats[t]])} equipos")
    except Exception as e:
        print(f"   Error bullpen stats: {e}")

    # Bateo (OBP, SLG, ISO)
    try:
        url = f"{MLB_API}/teams/stats?season=2026&group=hitting&stats=season&sportId=1"
        r = requests.get(url, timeout=10)
        data = r.json()
        for split in data.get("stats", [{}])[0].get("splits", []):
            team = split.get("team", {})
            abbr = NAME_TO_ABBR.get(team.get("name", ""), team.get("name", "")[:3].upper())
            stat = split.get("stat", {})
            try:
                obp = round(float(stat.get("obp", ".310")), 3)
            except:
                obp = 0.310
            try:
                slg = round(float(stat.get("slg", ".410")), 3)
            except:
                slg = 0.410
            try:
                avg = round(float(stat.get("avg", ".245")), 3)
            except:
                avg = 0.245
            if abbr not in team_stats:
                team_stats[abbr] = {}
            team_stats[abbr]["obp"] = obp
            team_stats[abbr]["slg"] = slg
            team_stats[abbr]["avg"] = avg
            team_stats[abbr]["ops"] = round(obp + slg, 3)
        print(f"   Batting stats: {len(team_stats)} equipos")
    except Exception as e:
        print(f"   Error batting stats: {e}")

    return team_stats

# 5. Obtener momios + consensus de sportsbooks
def get_odds():
    if not ODDS_API_KEY:
        print("   ODDS_API_KEY no configurada, omitiendo momios")
        return {}

    def ml_to_prob(ml):
        return abs(ml) / (abs(ml) + 100) if ml < 0 else 100 / (ml + 100)

    try:
        url = (
            f"{ODDS_API}/sports/baseball_mlb/odds"
            f"?apiKey={ODDS_API_KEY}&regions=us&markets=h2h"
            f"&oddsFormat=american&dateFormat=iso"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        SHARP_BOOKS = ["draftkings","fanduel","betmgm","caesars","betrivers","pointsbet","bovada"]
        odds_map = {}

        for event in data:
            home_name = event.get("home_team", "")
            away_name = event.get("away_team", "")
            home_abbr = NAME_TO_ABBR.get(home_name, home_name[:3].upper())
            away_abbr = NAME_TO_ABBR.get(away_name, away_name[:3].upper())
            bookmakers = event.get("bookmakers", [])
            if not bookmakers:
                continue

            home_probs, away_probs, book_names = [], [], []
            best_home_ml = best_away_ml = best_book = None

            for bk in bookmakers:
                if bk["key"] not in SHARP_BOOKS:
                    continue
                for market in bk.get("markets", []):
                    if market["key"] != "h2h":
                        continue
                    h_ml = a_ml = None
                    for outcome in market.get("outcomes", []):
                        if outcome["name"] == home_name:
                            h_ml = outcome["price"]
                        elif outcome["name"] == away_name:
                            a_ml = outcome["price"]
                    if h_ml is not None and a_ml is not None:
                        home_probs.append(ml_to_prob(h_ml) * 100)
                        away_probs.append(ml_to_prob(a_ml) * 100)
                        book_names.append(bk["title"])
                        if bk["key"] == "draftkings" or best_home_ml is None:
                            best_home_ml = h_ml
                            best_away_ml = a_ml
                            best_book    = bk["title"]

            if not home_probs:
                continue

            avg_home = sum(home_probs) / len(home_probs)
            avg_away = sum(away_probs) / len(away_probs)
            total    = avg_home + avg_away
            consensus_home = round(avg_home / total * 100, 1)
            consensus_away = round(avg_away / total * 100, 1)
            spread    = round(max(home_probs) - min(home_probs), 1) if len(home_probs) > 1 else 0
            agreement = "Alta" if spread < 3 else ("Media" if spread < 6 else "Baja")

            key = f"{away_abbr}@{home_abbr}"
            odds_map[key] = {
                "home_ml":        best_home_ml,
                "away_ml":        best_away_ml,
                "bookmaker":      best_book,
                "consensus_home": consensus_home,
                "consensus_away": consensus_away,
                "books_count":    len(home_probs),
                "books":          book_names,
                "spread":         spread,
                "agreement":      agreement,
            }

        print(f"   Momios: {len(odds_map)} partidos ({sum(o['books_count'] for o in odds_map.values())} lineas)")
        return odds_map

    except Exception as e:
        print(f"   Error momios: {e}")
        return {}

# 6. Modelo de prediccion v2.0
def calc_model(h_abbr, a_abbr, standings, team_stats, h_sera=None, a_sera=None):
    """
    Modelo v3.0 — usa pesos de regresion logistica entrenada (model_weights.json).
    Si no hay pesos disponibles, cae al modelo heuristico v2.0.
    """
    hs_data = standings.get(h_abbr, {})
    as_data = standings.get(a_abbr, {})

    DEFAULT = {
        "era": 4.00, "whip": 1.30, "k9": 8.0,
        "bullpen_era": 4.00, "bullpen_whip": 1.30,
        "obp": .310, "slg": .410, "ops": .720,
    }
    ht = {**DEFAULT, **team_stats.get(h_abbr, {})}
    at = {**DEFAULT, **team_stats.get(a_abbr, {})}

    h_w  = hs_data.get("w", 40); h_l = hs_data.get("l", 40)
    a_w  = as_data.get("w", 40); a_l = as_data.get("l", 40)
    h_wp = h_w / (h_w + h_l) if (h_w + h_l) > 0 else 0.5
    a_wp = a_w / (a_w + a_l) if (a_w + a_l) > 0 else 0.5

    h_rdiff = hs_data.get("rdiff", 0)
    a_rdiff = as_data.get("rdiff", 0)

    pf = PARK_FACTORS.get(h_abbr, 1.0)
    pf_pitch = 2.0 - pf
    mixed = h_sera is not None and a_sera is not None

    # === MODELO v3.0: Regresion logistica ===
    if MODEL_WEIGHTS:
        # Construir las MISMAS features que en train_model.py (mismo orden)
        # Si hay abridor confirmado, mezclar su ERA con la del staff
        h_era_eff = (ht["era"] * 0.4 + h_sera * 0.6) if mixed else ht["era"]
        a_era_eff = (at["era"] * 0.4 + a_sera * 0.6) if mixed else at["era"]

        features = [
            h_wp - a_wp,                              # dif_winpct
            (h_rdiff - a_rdiff) / 100.0,              # dif_rundiff
            (a_era_eff - h_era_eff) * pf_pitch,       # dif_era
            (at["bullpen_era"] - ht["bullpen_era"]) * pf_pitch,  # dif_bullpen
            (ht["ops"] - at["ops"]) * pf,             # dif_ops
            ht["obp"] - at["obp"],                    # dif_obp
            pf - 1.0,                                 # park_factor
            1.0,                                      # home_advantage
        ]

        # Estandarizar con los parametros del scaler
        mean  = MODEL_WEIGHTS["scaler_mean"]
        scale = MODEL_WEIGHTS["scaler_scale"]
        coef  = MODEL_WEIGHTS["coefficients"]
        intercept = MODEL_WEIGHTS["intercept"]

        z = intercept
        for i, fv in enumerate(features):
            standardized = (fv - mean[i]) / scale[i] if scale[i] != 0 else 0
            z += standardized * coef[i]

        # Sigmoide -> probabilidad de que gane el local
        prob_home = 1.0 / (1.0 + math.exp(-z))
        hp = round(prob_home * 100)
        hp = max(25, min(75, hp))  # Cap razonable
    else:
        # Fallback heuristico v2.0
        hs = h_wp * 20 + a_wp * 0
        as_ = a_wp * 20
        hs += (5.0 - min(ht["era"] * pf_pitch, 5.5)) * 5
        as_ += (5.0 - min(at["era"] * pf_pitch, 5.5)) * 5
        total = max(hs + as_, 1)
        hp = max(30, min(70, round(hs / total * 100)))

    diff = abs(hp - 50)
    # Umbrales recalibrados v3.0: con regresion el modelo es mas conservador
    conf = "Alta" if diff > 12 else ("Media" if diff > 6 else "Baja")

    return {
        "hp": hp, "ap": 100 - hp,
        "conf": conf, "mixed": mixed, "diff": diff,
        "park_factor": pf,
    }

# 7. Value bet
def calc_value_bet(hp, ap, odds):
    if not odds:
        return False, None
    consensus_home = odds.get("consensus_home")
    consensus_away = odds.get("consensus_away")
    if consensus_home is None:
        home_ml = odds.get("home_ml")
        away_ml = odds.get("away_ml")
        if home_ml is None:
            return False, None
        def ml_to_p(ml):
            return abs(ml)/(abs(ml)+100)*100 if ml < 0 else 100/(ml+100)*100
        consensus_home = ml_to_p(home_ml)
        consensus_away = ml_to_p(away_ml)
    model_favors_home  = hp >= 50
    market_favors_home = consensus_home >= consensus_away
    is_value = model_favors_home != market_favors_home
    edge = round(hp - consensus_home, 1) if model_favors_home else round(ap - consensus_away, 1)
    return is_value, edge

# 8. Historial
HISTORY_FILE = "public/history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def clean_history(history):
    """Elimina entradas con equipos UNK (datos corruptos del bug inicial)."""
    before = len(history)
    history = [h for h in history if h.get("home") != "UNK" and h.get("away") != "UNK"
               and h.get("pred") != "UNK"]
    after = len(history)
    if before != after:
        print(f"   Historial limpiado: {before - after} entradas UNK eliminadas")
    return history

# 9. Actualizar historial — guarda solo el Top 5 (mismos criterios que las predicciones de hoy)
def update_history(history, yesterday_games, standings, team_stats):
    existing = {f"{h['home']}-{h['away']}-{h['date']}" for h in history}

    # 1. Calcular prediccion de TODOS los partidos de ayer
    preds = []
    for g in yesterday_games:
        if g["status"] != "Final":
            continue
        if g["home_score"] is None:
            continue
        if g["home"] == "UNK" or g["away"] == "UNK":
            continue
        pred = calc_model(g["home"], g["away"], standings, team_stats)
        preds.append({**g, **pred})

    # 2. Ordenar por conviccion (diff) y tomar el Top 5 — IGUAL que el Top 5 de hoy
    top5_ayer = sorted(preds, key=lambda x: x["diff"], reverse=True)[:5]

    # 3. Guardar solo esos 5 en el historial
    added = 0
    for g in top5_ayer:
        key = f"{g['home']}-{g['away']}-{YESTERDAY}"
        if key in existing:
            continue
        fav = g["home"] if g["hp"] >= 50 else g["away"]
        win = g["home"] if g["home_score"] > g["away_score"] else g["away"]
        hit = fav == win
        score = (
            f"{g['away']} {g['away_score']}-{g['home_score']} {g['home']}"
            if g["away_score"] > g["home_score"]
            else f"{g['home']} {g['home_score']}-{g['away_score']} {g['away']}"
        )
        history.append({
            "date":   YESTERDAY,
            "home":   g["home"],
            "away":   g["away"],
            "hp":     g["hp"],
            "pred":   fav,
            "actual": score,
            "hit":    hit,
        })
        added += 1
    print(f"   {added} predicciones del Top 5 de ayer agregadas al historial")
    return history

# 10. Main
def main():
    print("\nObteniendo standings + forma reciente...")
    standings = get_standings()
    print(f"   {len(standings)} equipos cargados")

    print("\nObteniendo stats de equipos (pitching + bullpen + bateo)...")
    team_stats = get_team_stats()
    print(f"   {len(team_stats)} equipos con stats")

    print("\nObteniendo partidos de hoy...")
    today_games = get_games(TODAY)
    print(f"   {len(today_games)} partidos hoy")

    print("\nObteniendo ERAs de abridores...")
    for g in today_games:
        g["home_era"] = get_pitcher_era(g.get("home_pitcher_id"))
        g["away_era"] = get_pitcher_era(g.get("away_pitcher_id"))
        if g["home_pitcher"]:
            era_str = f"ERA {g['home_era']}" if g["home_era"] else "N/A"
            print(f"   {g['home_pitcher']} ({g['home']}) - {era_str}")

    print("\nObteniendo momios + consensus...")
    odds_map = get_odds()

    print("\nCalculando Top 5...")
    predictions = []
    for g in today_games:
        if g["status"] == "Final":
            continue
        pred = calc_model(
            g["home"], g["away"], standings, team_stats,
            g.get("home_era"), g.get("away_era")
        )
        odds_key  = f"{g['away']}@{g['home']}"
        game_odds = odds_map.get(odds_key, {})
        is_value, edge = calc_value_bet(pred["hp"], pred["ap"], game_odds)
        predictions.append({**g, **pred, "odds": game_odds, "value": is_value, "edge": edge})

    if not predictions:
        print("   No hay partidos pendientes hoy")
        top5 = []
    else:
        top5 = sorted(predictions, key=lambda x: x["diff"], reverse=True)[:5]
        print(f"   Lider: {top5[0]['away']} @ {top5[0]['home']} ({top5[0]['conf']} confianza)")
        value_bets = [p for p in top5 if p.get("value")]
        if value_bets:
            print(f"   Value bets: {len(value_bets)}")

    print("\nActualizando historial...")
    yesterday_games = get_games(YESTERDAY)
    history = load_history()
    history = clean_history(history)
    history = update_history(history, yesterday_games, standings, team_stats)
    save_history(history)

    hits  = sum(1 for h in history if h["hit"])
    total = len(history)
    pct   = round(hits / total * 100) if total > 0 else 0
    streak = 0
    if history:
        st = "W" if history[-1]["hit"] else "L"
        for h in reversed(history):
            if h["hit"] == (st == "W"):
                streak += 1
            else:
                break

    # Resumen de forma reciente por equipo para el output
    form_summary = {
        abbr: {
            "last10_w":   s.get("last10_w"),
            "last10_l":   s.get("last10_l"),
            "last10_pct": s.get("last10_pct"),
        }
        for abbr, s in standings.items()
        if s.get("last10_pct") is not None
    }

    output = {
        "date":       TODAY,
        "updated":    datetime.now(MEXICO_TZ).strftime("%d/%m/%Y %H:%M CST"),
        "model_info": {
            "version":      "3.0",
            "type":         "Regresion logistica" if MODEL_WEIGHTS else "Heuristico",
            "cv_accuracy":  round(MODEL_WEIGHTS["cv_accuracy"] * 100, 1) if MODEL_WEIGHTS else None,
            "n_games":      MODEL_WEIGHTS["n_games"] if MODEL_WEIGHTS else None,
            "trained_at":   MODEL_WEIGHTS["trained_at"] if MODEL_WEIGHTS else None,
        },
        "standings":  standings,
        "team_stats": team_stats,
        "form":       form_summary,
        "top5":       top5,
        "history":    history[-1000:],
        "stats": {
            "hits":        hits,
            "total":       total,
            "pct":         pct,
            "streak":      streak,
            "streak_type": "W" if (history and history[-1]["hit"]) else "L",
        }
    }

    with open("public/data.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Listo: {total} predicciones historicas, {pct}% precision")
    print(f"  Bullpen stats incluidos para {len([t for t in team_stats if 'bullpen_era' in team_stats[t]])} equipos")
    print(f"  Park factors activos para 30 estadios")
    if odds_map:
        print(f"  Momios: {len(odds_map)} partidos")

if __name__ == "__main__":
    main()
