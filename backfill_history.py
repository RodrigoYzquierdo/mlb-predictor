"""
MLB Predictor - Script de backfill historico
Descarga todos los partidos finalizados de la temporada 2026
y calcula predicciones retroactivas para poblar history.json

Uso: python backfill_history.py
Requiere: pip install requests pytz
"""

import requests
import json
from datetime import datetime, timedelta
import pytz
import os
import time

MLB_API   = "https://statsapi.mlb.com/api/v1"
MEXICO_TZ = pytz.timezone("America/Mexico_City")

# Temporada 2026: del Opening Day hasta ayer
SEASON_START = "2026-03-26"
SEASON_END   = (datetime.now(MEXICO_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
HISTORY_FILE = "public/history.json"

print(f"Backfill: {SEASON_START} → {SEASON_END}")

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
    "D-backs": "AZ",    "Braves": "ATL",    "Orioles": "BAL",
    "Red Sox": "BOS",   "Cubs": "CHC",      "White Sox": "CWS",
    "Reds": "CIN",      "Guardians": "CLE", "Rockies": "COL",
    "Tigers": "DET",    "Astros": "HOU",    "Royals": "KC",
    "Angels": "LAA",    "Dodgers": "LAD",   "Marlins": "MIA",
    "Brewers": "MIL",   "Twins": "MIN",     "Mets": "NYM",
    "Yankees": "NYY",   "Phillies": "PHI",  "Pirates": "PIT",
    "Padres": "SD",     "Giants": "SF",     "Mariners": "SEA",
    "Cardinals": "STL", "Rays": "TB",       "Rangers": "TEX",
    "Blue Jays": "TOR", "Nationals": "WSH", "Oakland Athletics": "ATH",
}

PARK_FACTORS = {
    "COL": 1.18, "BOS": 1.08, "CIN": 1.06, "TEX": 1.05,
    "PHI": 1.04, "CHC": 1.03, "MIL": 1.02, "NYY": 1.02,
    "ATL": 1.01, "HOU": 1.00, "STL": 1.00, "TOR": 1.00,
    "MIN": 0.99, "AZ":  0.99, "DET": 0.99, "LAD": 0.98,
    "ATH": 0.98, "MIA": 0.97, "CLE": 0.97, "WSH": 0.97,
    "BAL": 0.97, "PIT": 0.97, "CWS": 0.96, "KC":  0.96,
    "TB":  0.96, "NYM": 0.96, "SF":  0.95, "LAA": 0.95,
    "SEA": 0.94, "SD":  0.94,
}

def get_abbr(team_dict):
    name = team_dict.get("name", "UNK")
    return NAME_TO_ABBR.get(name, name[:3].upper())

def date_range(start, end):
    """Genera lista de fechas entre start y end (inclusive)."""
    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt  = datetime.strptime(end, "%Y-%m-%d")
    dates   = []
    while current <= end_dt:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates

def get_games_for_date(date):
    """Obtiene todos los partidos finales de una fecha."""
    try:
        url = f"{MLB_API}/schedule?sportId=1&date={date}&hydrate=linescore"
        r   = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        data  = r.json()
        games = []
        for date_entry in data.get("dates", []):
            for g in date_entry.get("games", []):
                if g["status"]["abstractGameState"] != "Final":
                    continue
                home = g["teams"]["home"]
                away = g["teams"]["away"]
                h_score = home.get("score")
                a_score = away.get("score")
                if h_score is None or a_score is None:
                    continue
                h_abbr = get_abbr(home.get("team", {}))
                a_abbr = get_abbr(away.get("team", {}))
                if h_abbr == "UNK" or a_abbr == "UNK":
                    continue
                games.append({
                    "date":       date,
                    "home":       h_abbr,
                    "away":       a_abbr,
                    "home_score": int(h_score),
                    "away_score": int(a_score),
                })
        return games
    except Exception as e:
        print(f"   Error {date}: {e}")
        return []

def get_standings_for_date(date):
    """Obtiene standings hasta una fecha especifica."""
    try:
        # MLB API no permite standings por fecha historica facilmente
        # Usamos el season completo y filtramos — es una aproximacion
        url = f"{MLB_API}/standings?leagueId=103,104&season=2026&standingsTypes=regularSeason&date={date}"
        r   = requests.get(url, timeout=10)
        if r.status_code != 200:
            return {}
        data  = r.json()
        teams = {}
        for record in data.get("records", []):
            for tr in record.get("teamRecords", []):
                team = tr.get("team", {})
                name = team.get("name", "UNK")
                abbr = NAME_TO_ABBR.get(name, name[:3].upper())
                w    = tr.get("wins", 0)
                l    = tr.get("losses", 0)
                rs   = tr.get("runsScored", 0)
                ra   = tr.get("runsAllowed", 0)
                # Forma reciente
                last10_w = last10_l = None
                for rec in tr.get("records", {}).get("splitRecords", []):
                    if rec.get("type") == "lastTen":
                        last10_w = rec.get("wins", 0)
                        last10_l = rec.get("losses", 0)
                        break
                teams[abbr] = {
                    "w":    w, "l": l,
                    "pct":  round(w / (w + l), 3) if (w + l) > 0 else 0.500,
                    "rdiff": rs - ra,
                    "last10_pct": round(last10_w / 10, 3) if last10_w is not None else None,
                }
        return teams
    except Exception as e:
        print(f"   Error standings {date}: {e}")
        return {}

def get_team_stats_season():
    """Obtiene stats de pitcheo y bateo de toda la temporada 2026."""
    team_stats = {}

    try:
        url  = f"{MLB_API}/teams/stats?season=2026&group=pitching&stats=season&sportId=1"
        r    = requests.get(url, timeout=10)
        data = r.json()
        for split in data.get("stats", [{}])[0].get("splits", []):
            team = split.get("team", {})
            abbr = NAME_TO_ABBR.get(team.get("name", ""), "UNK")
            stat = split.get("stat", {})
            if abbr not in team_stats:
                team_stats[abbr] = {}
            try:
                team_stats[abbr]["era"]  = round(float(stat.get("era",  "4.00")), 2)
                team_stats[abbr]["whip"] = round(float(stat.get("whip", "1.30")), 3)
            except:
                pass
    except Exception as e:
        print(f"   Error pitching stats: {e}")

    try:
        url  = f"{MLB_API}/teams/stats?season=2026&group=pitching&stats=season&sportId=1&pitchingType=bullpen"
        r    = requests.get(url, timeout=10)
        data = r.json()
        for split in data.get("stats", [{}])[0].get("splits", []):
            team = split.get("team", {})
            abbr = NAME_TO_ABBR.get(team.get("name", ""), "UNK")
            stat = split.get("stat", {})
            if abbr in team_stats:
                try:
                    team_stats[abbr]["bullpen_era"] = round(float(stat.get("era", "4.00")), 2)
                except:
                    pass
    except Exception as e:
        print(f"   Error bullpen stats: {e}")

    try:
        url  = f"{MLB_API}/teams/stats?season=2026&group=hitting&stats=season&sportId=1"
        r    = requests.get(url, timeout=10)
        data = r.json()
        for split in data.get("stats", [{}])[0].get("splits", []):
            team = split.get("team", {})
            abbr = NAME_TO_ABBR.get(team.get("name", ""), "UNK")
            stat = split.get("stat", {})
            if abbr not in team_stats:
                team_stats[abbr] = {}
            try:
                obp = round(float(stat.get("obp", ".310")), 3)
                slg = round(float(stat.get("slg", ".410")), 3)
                team_stats[abbr]["obp"] = obp
                team_stats[abbr]["slg"] = slg
                team_stats[abbr]["ops"] = round(obp + slg, 3)
            except:
                pass
    except Exception as e:
        print(f"   Error batting stats: {e}")

    print(f"   Team stats: {len(team_stats)} equipos")
    return team_stats

def calc_model(h_abbr, a_abbr, standings, team_stats):
    """Modelo v2.0 — mismo que usa el script diario."""
    hs_data = standings.get(h_abbr, {})
    as_data = standings.get(a_abbr, {})

    DEFAULT = {
        "era": 4.00, "whip": 1.30,
        "bullpen_era": 4.00,
        "obp": .310, "slg": .410, "ops": .720,
    }
    ht = {**DEFAULT, **team_stats.get(h_abbr, {})}
    at = {**DEFAULT, **team_stats.get(a_abbr, {})}

    h_w  = hs_data.get("w", 40);  h_l  = hs_data.get("l", 40)
    a_w  = as_data.get("w", 40);  a_l  = as_data.get("l", 40)
    h_wp = h_w / (h_w + h_l) if (h_w + h_l) > 0 else 0.5
    a_wp = a_w / (a_w + a_l) if (a_w + a_l) > 0 else 0.5

    h_form = hs_data.get("last10_pct") or h_wp
    a_form = as_data.get("last10_pct") or a_wp
    h_rdiff = hs_data.get("rdiff", 0)
    a_rdiff = as_data.get("rdiff", 0)

    pf              = PARK_FACTORS.get(h_abbr, 1.0)
    pf_pitching_adj = 2.0 - pf
    pf_hitting_adj  = pf

    hs, as_ = 0, 0

    hs  += h_wp   * 20;  as_ += a_wp   * 20   # Win%
    hs  += h_form * 15;  as_ += a_form * 15   # Forma reciente
    hs  += (5.0 - min(ht["era"]        * pf_pitching_adj, 5.5)) * 5   # ERA staff
    as_ += (5.0 - min(at["era"]        * pf_pitching_adj, 5.5)) * 5
    hs  += (5.0 - min(ht["bullpen_era"]* pf_pitching_adj, 5.5)) * 5   # Bullpen
    as_ += (5.0 - min(at["bullpen_era"]* pf_pitching_adj, 5.5)) * 5
    hs  += (ht["ops"] * pf_hitting_adj - 0.680) * 30                  # OPS
    as_ += (at["ops"] * pf_hitting_adj - 0.680) * 30
    hs  += (ht["obp"] - 0.280) * 50;  as_ += (at["obp"] - 0.280) * 50  # OBP
    hs  += max(-1, min(1, h_rdiff / 150)) * 8                         # Run diff
    as_ += max(-1, min(1, a_rdiff / 150)) * 8
    hs  *= 1.045                                                       # Local

    total = max(hs + as_, 1)
    hp    = max(30, min(70, round(hs / total * 100)))
    return hp

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history):
    os.makedirs("public", exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def main():
    print("\n1. Obteniendo team stats de la temporada 2026...")
    team_stats = get_team_stats_season()

    print("\n2. Obteniendo fechas a procesar...")
    dates = date_range(SEASON_START, SEASON_END)
    print(f"   {len(dates)} dias a procesar ({SEASON_START} → {SEASON_END})")

    print("\n3. Cargando historial existente...")
    history = load_history()
    # Limpiar UNK
    history = [h for h in history if h.get("home") != "UNK" and h.get("away") != "UNK"]
    existing = {f"{h['home']}-{h['away']}-{h['date']}" for h in history}
    print(f"   {len(history)} entradas existentes")

    print("\n4. Procesando partidos historicos...")
    added   = 0
    skipped = 0
    errors  = 0

    # Agrupar fechas en bloques de 7 dias para reducir llamadas a standings
    standings_cache = {}
    standings_date  = None

    for i, date in enumerate(dates):
        # Actualizar standings cada 7 dias (aproximacion — standings cambian diario
        # pero la API historica es lenta; cada 7 dias es suficientemente preciso)
        week = date[:8] + "0" + date[8] if len(date) > 8 else date[:7]
        if week not in standings_cache:
            standings_cache[week] = get_standings_for_date(date)
            time.sleep(0.3)  # No saturar la API

        standings = standings_cache[week]

        games = get_games_for_date(date)
        time.sleep(0.2)

        for g in games:
            key = f"{g['home']}-{g['away']}-{g['date']}"
            if key in existing:
                skipped += 1
                continue

            hp  = calc_model(g["home"], g["away"], standings, team_stats)
            fav = g["home"] if hp >= 50 else g["away"]
            win = g["home"] if g["home_score"] > g["away_score"] else g["away"]
            hit = fav == win

            score = (
                f"{g['away']} {g['away_score']}-{g['home_score']} {g['home']}"
                if g["away_score"] > g["home_score"]
                else f"{g['home']} {g['home_score']}-{g['away_score']} {g['away']}"
            )

            history.append({
                "date":   g["date"],
                "home":   g["home"],
                "away":   g["away"],
                "hp":     hp,
                "pred":   fav,
                "actual": score,
                "hit":    hit,
            })
            existing.add(key)
            added += 1

        if (i + 1) % 10 == 0:
            progress = round((i + 1) / len(dates) * 100)
            hits_so_far  = sum(1 for h in history if h["hit"])
            total_so_far = len(history)
            pct = round(hits_so_far / total_so_far * 100) if total_so_far > 0 else 0
            print(f"   [{progress}%] {date} — {added} nuevos, {pct}% precision acumulada")

    # Ordenar por fecha
    history.sort(key=lambda h: h["date"])

    print(f"\n5. Guardando historial...")
    save_history(history)

    # Resumen final
    hits  = sum(1 for h in history if h["hit"])
    total = len(history)
    pct   = round(hits / total * 100) if total > 0 else 0

    print(f"\n{'='*50}")
    print(f"BACKFILL COMPLETO")
    print(f"  Total partidos: {total}")
    print(f"  Nuevos agregados: {added}")
    print(f"  Ya existian: {skipped}")
    print(f"  Precision general: {pct}%")
    print(f"  Aciertos: {hits} / {total}")
    print(f"{'='*50}")

    # Analisis por confianza
    print(f"\nAnalisis por nivel de prediccion:")
    for threshold, label in [(15, "Alta (>65%)"), (8, "Media (58-65%)"), (0, "Baja (<58%)")]:
        subset = [h for h in history if abs(h["hp"] - 50) > threshold]
        if subset:
            h2 = sum(1 for h in subset if h["hit"])
            print(f"  {label}: {round(h2/len(subset)*100)}% ({h2}/{len(subset)})")

if __name__ == "__main__":
    main()
