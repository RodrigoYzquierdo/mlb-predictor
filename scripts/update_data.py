"""
MLB Predictor - Script de actualizacion diaria
Corre automaticamente via GitHub Actions cada dia a las 9 AM CST
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

NAME_TO_ABBR = {
    # Nombres completos (schedule, team stats, pitchers)
    "Arizona Diamondbacks": "AZ",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Athletics": "ATH",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
    # Nombres cortos (standings API usa teamName en lugar de name completo)
    "D-backs": "AZ",
    "Braves": "ATL",
    "Orioles": "BAL",
    "Red Sox": "BOS",
    "Cubs": "CHC",
    "White Sox": "CWS",
    "Reds": "CIN",
    "Guardians": "CLE",
    "Rockies": "COL",
    "Tigers": "DET",
    "Astros": "HOU",
    "Royals": "KC",
    "Angels": "LAA",
    "Dodgers": "LAD",
    "Marlins": "MIA",
    "Brewers": "MIL",
    "Twins": "MIN",
    "Mets": "NYM",
    "Yankees": "NYY",
    "Phillies": "PHI",
    "Pirates": "PIT",
    "Padres": "SD",
    "Giants": "SF",
    "Mariners": "SEA",
    "Cardinals": "STL",
    "Rays": "TB",
    "Rangers": "TEX",
    "Blue Jays": "TOR",
    "Nationals": "WSH",
    # Nombres The Odds API
    "Arizona Diamondbacks": "AZ",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "ATH",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}

# IDs oficiales de MLB por equipo
TEAM_IDS = {
    "AZ":133,"ATL":144,"BAL":110,"BOS":111,"CHC":112,
    "CWS":145,"CIN":113,"CLE":114,"COL":115,"DET":116,
    "HOU":117,"KC":118,"LAA":108,"LAD":119,"MIA":146,
    "MIL":158,"MIN":142,"NYM":121,"NYY":147,"ATH":133,
    "PHI":143,"PIT":134,"SD":135,"SF":137,"SEA":136,
    "STL":138,"TB":139,"TEX":140,"TOR":141,"WSH":120,
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

# 2. Obtener ERA del pitcher
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
            w = tr.get("wins", 0)
            l = tr.get("losses", 0)
            rs = tr.get("runsScored", 0)
            ra = tr.get("runsAllowed", 0)
            rdiff = rs - ra if (rs or ra) else 0
            teams[abbr] = {
                "name": name,
                "w":    w,
                "l":    l,
                "pct":  round(w / (w + l), 3) if (w + l) > 0 else 0.500,
                "div":  record.get("division", {}).get("name", ""),
                "conf": record.get("league", {}).get("name", ""),
                "rdiff": rdiff,
            }
    return teams

# 4. Obtener estadisticas de pitcheo y bateo por equipo (DINAMICO)
def get_team_stats():
    team_stats = {}

    try:
        url = f"{MLB_API}/teams/stats?season=2026&group=pitching&stats=season&sportId=1"
        r = requests.get(url, timeout=10)
        data = r.json()
        for split in data.get("stats", [{}])[0].get("splits", []):
            team = split.get("team", {})
            name = team.get("name", "")
            abbr = NAME_TO_ABBR.get(name, name[:3].upper())
            stat = split.get("stat", {})
            era_raw = stat.get("era", "4.00")
            try:
                era = round(float(era_raw), 2)
            except:
                era = 4.00
            if abbr not in team_stats:
                team_stats[abbr] = {}
            team_stats[abbr]["era"] = era
        print(f"   ERA de pitcheo: {len(team_stats)} equipos")
    except Exception as e:
        print(f"   Error obteniendo ERA: {e}")

    try:
        url = f"{MLB_API}/teams/stats?season=2026&group=hitting&stats=season&sportId=1"
        r = requests.get(url, timeout=10)
        data = r.json()
        for split in data.get("stats", [{}])[0].get("splits", []):
            team = split.get("team", {})
            name = team.get("name", "")
            abbr = NAME_TO_ABBR.get(name, name[:3].upper())
            stat = split.get("stat", {})
            try:
                obp = round(float(stat.get("obp", ".310")), 3)
            except:
                obp = 0.310
            try:
                slg = round(float(stat.get("slg", ".410")), 3)
            except:
                slg = 0.410
            if abbr not in team_stats:
                team_stats[abbr] = {}
            team_stats[abbr]["obp"] = obp
            team_stats[abbr]["slg"] = slg
        print(f"   OBP/SLG de bateo: {len(team_stats)} equipos")
    except Exception as e:
        print(f"   Error obteniendo OBP/SLG: {e}")

    return team_stats

# 5. Obtener momios de The Odds API
def get_odds():
    """
    Obtiene momios moneyline de MLB para hoy.
    Retorna dict keyed por "AWAY@HOME" -> {home_ml, away_ml, bookmaker}
    """
    if not ODDS_API_KEY:
        print("   ODDS_API_KEY no configurada, omitiendo momios")
        return {}
    try:
        url = (
            f"{ODDS_API}/sports/baseball_mlb/odds"
            f"?apiKey={ODDS_API_KEY}"
            f"&regions=us"
            f"&markets=h2h"
            f"&oddsFormat=american"
            f"&dateFormat=iso"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        odds_map = {}
        for event in data:
            home_name = event.get("home_team", "")
            away_name = event.get("away_team", "")
            home_abbr = NAME_TO_ABBR.get(home_name, home_name[:3].upper())
            away_abbr = NAME_TO_ABBR.get(away_name, away_name[:3].upper())

            # Preferir DraftKings > FanDuel > BetMGM > cualquier otro
            bookmakers = event.get("bookmakers", [])
            preferred  = ["draftkings", "fanduel", "betmgm"]
            chosen     = None
            for pref in preferred:
                for bk in bookmakers:
                    if bk["key"] == pref:
                        chosen = bk
                        break
                if chosen:
                    break
            if not chosen and bookmakers:
                chosen = bookmakers[0]
            if not chosen:
                continue

            home_ml = away_ml = None
            for market in chosen.get("markets", []):
                if market["key"] == "h2h":
                    for outcome in market.get("outcomes", []):
                        if outcome["name"] == home_name:
                            home_ml = outcome["price"]
                        elif outcome["name"] == away_name:
                            away_ml = outcome["price"]

            if home_ml is not None and away_ml is not None:
                key = f"{away_abbr}@{home_abbr}"
                odds_map[key] = {
                    "home_ml":   home_ml,
                    "away_ml":   away_ml,
                    "bookmaker": chosen["title"],
                }

        print(f"   Momios obtenidos: {len(odds_map)} partidos")
        return odds_map

    except Exception as e:
        print(f"   Error obteniendo momios: {e}")
        return {}

# 6. Obtener probabilidades de Polymarket
def get_polymarket(today_games):
    """
    Obtiene probabilidades implícitas de Polymarket para los partidos de hoy.
    Construye el slug directamente: mlb-{away_lower}-{home_lower}-{yyyy}-{mm}-{dd}
    Ejemplo: mlb-col-chc-2026-06-15
    Retorna dict keyed por "AWAY@HOME" -> {home_prob, away_prob, volume, question}
    """
    GAMMA_API = "https://gamma-api.polymarket.com"

    # Polymarket usa abreviaciones en minúsculas en el slug
    ABBR_TO_POLY = {
        "AZ":  "ari", "ATL": "atl", "BAL": "bal", "BOS": "bos",
        "CHC": "chc", "CWS": "cws", "CIN": "cin", "CLE": "cle",
        "COL": "col", "DET": "det", "HOU": "hou", "KC":  "kc",
        "LAA": "laa", "LAD": "lad", "MIA": "mia", "MIL": "mil",
        "MIN": "min", "NYM": "nym", "NYY": "nyy", "ATH": "oak",
        "PHI": "phi", "PIT": "pit", "SD":  "sd",  "SF":  "sf",
        "SEA": "sea", "STL": "stl", "TB":  "tb",  "TEX": "tex",
        "TOR": "tor", "WSH": "wsh",
    }

    date_parts = TODAY.split("-")
    yyyy, mm, dd = date_parts[0], date_parts[1], date_parts[2]

    # Polymarket usa fecha UTC — partidos nocturnos CST pueden tener fecha +1
    tomorrow   = (datetime.now(MEXICO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
    t_parts    = tomorrow.split("-")
    t_yyyy, t_mm, t_dd = t_parts[0], t_parts[1], t_parts[2]

    poly_map = {}
    headers  = {"User-Agent": "Mozilla/5.0"}

    for g in today_games:
        if g["status"] == "Final":
            continue

        away_poly = ABBR_TO_POLY.get(g["away"])
        home_poly = ABBR_TO_POLY.get(g["home"])
        if not away_poly or not home_poly:
            continue

        # Intentar con fecha de hoy y mañana (UTC offset)
        slugs_to_try = [
            f"mlb-{home_poly}-{away_poly}-{yyyy}-{mm}-{dd}",
            f"mlb-{home_poly}-{away_poly}-{t_yyyy}-{t_mm}-{t_dd}",
        ]

        for slug in slugs_to_try:
            url = f"{GAMMA_API}/events?slug={slug}"
            try:
                r = requests.get(url, timeout=8, headers=headers)
                r.raise_for_status()
                events = r.json()
                if not events:
                    continue

                event   = events[0]
                markets = event.get("markets", [])

                for m in markets:
                    q = m.get("question", "").lower()
                    if not any(kw in q for kw in ["win", "beat", "defeat", "winner"]):
                        continue
                    if any(kw in q for kw in ["series", "inning", "run", "score", "total", "hits"]):
                        continue

                    prices_raw = m.get("outcomePrices", "[]")
                    try:
                        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                        p_yes  = float(prices[0])
                        p_no   = float(prices[1])
                    except:
                        continue

                    if len(prices) != 2:
                        continue

                    volume = float(m.get("volumeNum", 0) or 0)
                    key    = f"{g['away']}@{g['home']}"
                    poly_map[key] = {
                        "home_prob": round(p_yes * 100),
                        "away_prob": round(p_no  * 100),
                        "volume":    round(volume),
                        "question":  m.get("question", ""),
                        "slug":      slug,
                    }
                    break

                if f"{g['away']}@{g['home']}" in poly_map:
                    break  # Ya encontramos este partido, no intentar fecha +1

            except Exception:
                pass

    print(f"   Polymarket: {len(poly_map)}/{len([g for g in today_games if g['status'] != 'Final'])} partidos con mercado")
    return poly_map


def match_polymarket(away, home, poly_map):
    """Busca el mercado Polymarket para este partido."""
    return poly_map.get(f"{away}@{home}", {})


# 7. Modelo de prediccion
def calc_model(h_abbr, a_abbr, standings, team_stats, h_sera=None, a_sera=None):
    hs_data = standings.get(h_abbr, {})
    as_data = standings.get(a_abbr, {})

    DEFAULT = {"era":4.00,"obp":.310,"slg":.410}
    ht = {**DEFAULT, **team_stats.get(h_abbr, {})}
    at = {**DEFAULT, **team_stats.get(a_abbr, {})}

    h_w = hs_data.get("w", 40)
    h_l = hs_data.get("l", 40)
    a_w = as_data.get("w", 40)
    a_l = as_data.get("l", 40)
    h_wp = h_w / (h_w + h_l) if (h_w + h_l) > 0 else 0.5
    a_wp = a_w / (a_w + a_l) if (a_w + a_l) > 0 else 0.5

    h_rdiff = hs_data.get("rdiff", 0)
    a_rdiff = as_data.get("rdiff", 0)

    mixed = h_sera is not None and a_sera is not None
    hs, as_ = 0, 0

    hs  += h_wp * 35
    as_ += a_wp * 35

    if mixed:
        hs  += (5.0 - min(ht["era"] * 0.4 + h_sera * 0.6, 5.5)) * 8
        as_ += (5.0 - min(at["era"] * 0.4 + a_sera * 0.6, 5.5)) * 8
    else:
        hs  += (5.0 - min(ht["era"], 5.5)) * 6
        as_ += (5.0 - min(at["era"], 5.5)) * 6

    hs  += (ht["obp"] - 0.280) * 80
    as_ += (at["obp"] - 0.280) * 80
    hs  += (ht["slg"] - 0.380) * 50
    as_ += (at["slg"] - 0.380) * 50

    hs  += max(-1, min(1, h_rdiff / 150)) * 8
    as_ += max(-1, min(1, a_rdiff / 150)) * 8

    hs *= 1.055

    total = hs + as_
    hp    = round(hs / total * 100)
    diff  = abs(hp - 50)
    conf  = "Alta" if diff > 18 else ("Media" if diff > 10 else "Baja")
    return {"hp": hp, "ap": 100 - hp, "conf": conf, "mixed": mixed, "diff": diff}

# 7. Calcular si hay value bet (modelo contradice al mercado)
def calc_value_bet(hp, ap, odds):
    """
    Compara la probabilidad del modelo vs la probabilidad implícita del mercado.
    Retorna True si el modelo favorece al equipo que el mercado tiene como underdog.
    """
    if not odds:
        return False, None

    home_ml = odds.get("home_ml")
    away_ml = odds.get("away_ml")
    if home_ml is None or away_ml is None:
        return False, None

    # Convertir moneyline americano a probabilidad implícita
    def ml_to_prob(ml):
        if ml < 0:
            return abs(ml) / (abs(ml) + 100)
        else:
            return 100 / (ml + 100)

    market_home_prob = ml_to_prob(home_ml) * 100
    market_away_prob = ml_to_prob(away_ml) * 100

    model_favors_home  = hp >= 50
    market_favors_home = market_home_prob >= market_away_prob

    is_value = model_favors_home != market_favors_home

    # Diferencia entre probabilidad del modelo y del mercado para el equipo favorito del modelo
    if model_favors_home:
        edge = round(hp - market_home_prob, 1)
    else:
        edge = round(ap - market_away_prob, 1)

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

# 9. Actualizar historial con resultados de ayer
def update_history(history, yesterday_games, standings, team_stats):
    existing = {f"{h['home']}-{h['away']}-{h['date']}" for h in history}
    added = 0
    for g in yesterday_games:
        if g["status"] != "Final":
            continue
        if g["home_score"] is None:
            continue
        key = f"{g['home']}-{g['away']}-{YESTERDAY}"
        if key in existing:
            continue
        pred = calc_model(g["home"], g["away"], standings, team_stats)
        fav  = g["home"] if pred["hp"] >= 50 else g["away"]
        win  = g["home"] if g["home_score"] > g["away_score"] else g["away"]
        hit  = fav == win
        score = (
            f"{g['away']} {g['away_score']}-{g['home_score']} {g['home']}"
            if g["away_score"] > g["home_score"]
            else f"{g['home']} {g['home_score']}-{g['away_score']} {g['away']}"
        )
        history.append({
            "date":   YESTERDAY,
            "home":   g["home"],
            "away":   g["away"],
            "hp":     pred["hp"],
            "pred":   fav,
            "actual": score,
            "hit":    hit,
        })
        added += 1
    print(f"{added} resultados de ayer agregados al historial")
    return history

# 10. Main
def main():
    print("\nObteniendo standings...")
    standings = get_standings()
    print(f"   {len(standings)} equipos cargados")

    print("\nObteniendo estadisticas dinamicas de equipos...")
    team_stats = get_team_stats()
    print(f"   {len(team_stats)} equipos con stats actualizados")

    print("\nObteniendo partidos de hoy...")
    today_games = get_games(TODAY)
    print(f"   {len(today_games)} partidos hoy")

    print("\nObteniendo ERAs de abridores...")
    for g in today_games:
        g["home_era"] = get_pitcher_era(g.get("home_pitcher_id"))
        g["away_era"] = get_pitcher_era(g.get("away_pitcher_id"))
        if g["home_pitcher"]:
            era_str = f"ERA {g['home_era']}" if g["home_era"] else "ERA N/A"
            print(f"   {g['home_pitcher']} ({g['home']}) - {era_str}")

    print("\nObteniendo momios...")
    odds_map = get_odds()

    print("\nObteniendo mercados Polymarket...")
    poly_map = get_polymarket(today_games)

    print("\nCalculando Top 5...")
    predictions = []
    for g in today_games:
        if g["status"] == "Final":
            continue
        pred = calc_model(
            g["home"], g["away"], standings, team_stats,
            g.get("home_era"), g.get("away_era")
        )
        # Momios de sportsbook
        odds_key  = f"{g['away']}@{g['home']}"
        game_odds = odds_map.get(odds_key, {})
        is_value, edge = calc_value_bet(pred["hp"], pred["ap"], game_odds)

        # Polymarket
        poly = match_polymarket(g["away"], g["home"], poly_map)

        predictions.append({
            **g,
            **pred,
            "odds":       game_odds,
            "value":      is_value,
            "edge":       edge,
            "polymarket": poly,
        })

    if not predictions:
        print("No hay partidos pendientes hoy")
        top5 = []
    else:
        top5 = sorted(predictions, key=lambda x: x["diff"], reverse=True)[:5]
        print(f"   Top 5 listo. Lider: {top5[0]['away']} @ {top5[0]['home']} ({top5[0]['conf']} confianza)")
        value_bets = [p for p in top5 if p.get("value")]
        if value_bets:
            print(f"   Value bets detectados: {len(value_bets)}")

    print("\nActualizando historial...")
    yesterday_games = get_games(YESTERDAY)
    history = load_history()
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

    output = {
        "date":       TODAY,
        "updated":    datetime.now(MEXICO_TZ).strftime("%d/%m/%Y %H:%M CST"),
        "standings":  standings,
        "team_stats": team_stats,
        "top5":       top5,
        "history":    history[-50:],
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
    print(f"\nListo: {total} predicciones historicas, {pct}% precision")
    print(f"Stats dinamicos incluidos para {len(team_stats)} equipos")
    if odds_map:
        print(f"Momios incluidos para {len(odds_map)} partidos")
    if poly_map:
        print(f"Polymarket incluido para {len(poly_map)} mercados")

if __name__ == "__main__":
    main()
