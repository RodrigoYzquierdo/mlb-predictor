"""
MLB Predictor - Entrenamiento de modelo (Regresion Logistica)
Descarga partidos historicos de 2026, reconstruye features, entrena
una regresion logistica y exporta los pesos optimos a model_weights.json

Uso: corre via GitHub Actions (train.yml)
Requiere: requests, pytz, scikit-learn, numpy

NOTA SOBRE DATA LEAKAGE:
Las stats de equipo (ERA, OPS, bullpen) se obtienen como acumulado de la
temporada COMPLETA, no como eran en cada fecha. Esto introduce algo de leakage
(el modelo "ve" stats de junio para predecir abril). Los ratings relativos entre
equipos son razonablemente estables, asi que el modelo sigue siendo valido como
aproximacion. Para un modelo de produccion puro habria que usar stats point-in-time.
"""

import requests
import json
from datetime import datetime, timedelta
import pytz
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

MLB_API   = "https://statsapi.mlb.com/api/v1"
MEXICO_TZ = pytz.timezone("America/Mexico_City")

SEASON_START = "2026-03-26"
SEASON_END   = (datetime.now(MEXICO_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

print(f"Entrenamiento: {SEASON_START} -> {SEASON_END}")

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
    "D-backs": "AZ", "Braves": "ATL", "Orioles": "BAL", "Red Sox": "BOS",
    "Cubs": "CHC", "White Sox": "CWS", "Reds": "CIN", "Guardians": "CLE",
    "Rockies": "COL", "Tigers": "DET", "Astros": "HOU", "Royals": "KC",
    "Angels": "LAA", "Dodgers": "LAD", "Marlins": "MIA", "Brewers": "MIL",
    "Twins": "MIN", "Mets": "NYM", "Yankees": "NYY", "Phillies": "PHI",
    "Pirates": "PIT", "Padres": "SD", "Giants": "SF", "Mariners": "SEA",
    "Cardinals": "STL", "Rays": "TB", "Rangers": "TEX", "Blue Jays": "TOR",
    "Nationals": "WSH", "Oakland Athletics": "ATH",
}

PARK_FACTORS = {
    "COL": 1.18, "BOS": 1.08, "CIN": 1.06, "TEX": 1.05, "PHI": 1.04,
    "CHC": 1.03, "MIL": 1.02, "NYY": 1.02, "ATL": 1.01, "HOU": 1.00,
    "STL": 1.00, "TOR": 1.00, "MIN": 0.99, "AZ": 0.99, "DET": 0.99,
    "LAD": 0.98, "ATH": 0.98, "MIA": 0.97, "CLE": 0.97, "WSH": 0.97,
    "BAL": 0.97, "PIT": 0.97, "CWS": 0.96, "KC": 0.96, "TB": 0.96,
    "NYM": 0.96, "SF": 0.95, "LAA": 0.95, "SEA": 0.94, "SD": 0.94,
}

def get_abbr(t):
    name = t.get("name", "UNK")
    return NAME_TO_ABBR.get(name, name[:3].upper())

def date_range(start, end):
    cur = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    out = []
    while cur <= end_dt:
        out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out

def get_team_stats():
    """Stats acumuladas de temporada (pitching, bullpen, hitting)."""
    ts = {}
    for grp, extra in [("pitching", ""), ("pitching", "&pitchingType=bullpen"), ("hitting", "")]:
        try:
            url = f"{MLB_API}/teams/stats?season=2026&group={grp}&stats=season&sportId=1{extra}"
            r = requests.get(url, timeout=10)
            for sp in r.json().get("stats", [{}])[0].get("splits", []):
                abbr = NAME_TO_ABBR.get(sp.get("team", {}).get("name", ""), "UNK")
                if abbr == "UNK":
                    continue
                st = sp.get("stat", {})
                if abbr not in ts:
                    ts[abbr] = {}
                if grp == "pitching" and not extra:
                    ts[abbr]["era"] = float(st.get("era", 4.0) or 4.0)
                    ts[abbr]["whip"] = float(st.get("whip", 1.3) or 1.3)
                elif "bullpen" in extra:
                    ts[abbr]["bullpen_era"] = float(st.get("era", 4.0) or 4.0)
                else:
                    obp = float(st.get("obp", 0.31) or 0.31)
                    slg = float(st.get("slg", 0.41) or 0.41)
                    ts[abbr]["obp"] = obp
                    ts[abbr]["ops"] = obp + slg
        except Exception as e:
            print(f"   Error {grp}{extra}: {e}")
    return ts

def get_standings():
    """Win% y run diff de temporada."""
    url = f"{MLB_API}/standings?leagueId=103,104&season=2026&standingsTypes=regularSeason"
    r = requests.get(url, timeout=10)
    teams = {}
    for rec in r.json().get("records", []):
        for tr in rec.get("teamRecords", []):
            abbr = NAME_TO_ABBR.get(tr.get("team", {}).get("name", ""), "UNK")
            if abbr == "UNK":
                continue
            w = tr.get("wins", 0); l = tr.get("losses", 0)
            rs = tr.get("runsScored", 0); ra = tr.get("runsAllowed", 0)
            teams[abbr] = {
                "wp": w / (w + l) if (w + l) > 0 else 0.5,
                "rdiff": rs - ra,
            }
    return teams

def get_finals(date):
    try:
        url = f"{MLB_API}/schedule?sportId=1&date={date}&hydrate=linescore"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        out = []
        for de in r.json().get("dates", []):
            for g in de.get("games", []):
                if g["status"]["abstractGameState"] != "Final":
                    continue
                home = g["teams"]["home"]; away = g["teams"]["away"]
                hs = home.get("score"); as_ = away.get("score")
                if hs is None or as_ is None:
                    continue
                h = get_abbr(home.get("team", {})); a = get_abbr(away.get("team", {}))
                if h == "UNK" or a == "UNK" or hs == as_:
                    continue
                out.append({"home": h, "away": a, "home_won": 1 if hs > as_ else 0})
        return out
    except:
        return []

DEFAULT = {"era": 4.0, "whip": 1.3, "bullpen_era": 4.0, "obp": 0.31, "ops": 0.72}

def build_features(h, a, standings, ts):
    """Construye el vector de features para un partido (perspectiva: gana local)."""
    hst = standings.get(h, {"wp": 0.5, "rdiff": 0})
    ast = standings.get(a, {"wp": 0.5, "rdiff": 0})
    ht = {**DEFAULT, **ts.get(h, {})}
    at = {**DEFAULT, **ts.get(a, {})}
    pf = PARK_FACTORS.get(h, 1.0)
    pf_pitch = 2.0 - pf

    # Features como DIFERENCIAS (local - visitante) — mejor para regresion
    return [
        hst["wp"] - ast["wp"],                                    # dif win%
        (hst["rdiff"] - ast["rdiff"]) / 100.0,                    # dif run diff (escalado)
        (at["era"] - ht["era"]) * pf_pitch,                       # dif ERA (invertido: menor ERA = mejor)
        (at["bullpen_era"] - ht["bullpen_era"]) * pf_pitch,       # dif bullpen ERA
        (ht["ops"] - at["ops"]) * pf,                             # dif OPS ajustado park
        ht["obp"] - at["obp"],                                    # dif OBP
        pf - 1.0,                                                 # park factor centrado
        1.0,                                                      # constante ventaja local (sesgo)
    ]

FEATURE_NAMES = [
    "dif_winpct", "dif_rundiff", "dif_era", "dif_bullpen",
    "dif_ops", "dif_obp", "park_factor", "home_advantage",
]

def main():
    print("\n1. Obteniendo stats de temporada...")
    ts = get_team_stats()
    standings = get_standings()
    print(f"   {len(ts)} equipos con stats, {len(standings)} en standings")

    print("\n2. Descargando partidos finalizados...")
    X, y = [], []
    dates = date_range(SEASON_START, SEASON_END)
    for i, d in enumerate(dates):
        for g in get_finals(d):
            X.append(build_features(g["home"], g["away"], standings, ts))
            y.append(g["home_won"])
        if (i + 1) % 20 == 0:
            print(f"   [{round((i+1)/len(dates)*100)}%] {d} — {len(X)} partidos")

    X = np.array(X); y = np.array(y)
    print(f"\n3. Dataset: {len(X)} partidos, {y.mean()*100:.1f}% ganados por local")

    print("\n4. Entrenando regresion logistica...")
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = LogisticRegression(max_iter=1000, C=1.0)
    model.fit(Xs, y)

    # Validacion cruzada
    scores = cross_val_score(model, Xs, y, cv=5)
    print(f"   Precision cross-val: {scores.mean()*100:.1f}% (+/- {scores.std()*100:.1f}%)")

    # Precision en training
    train_acc = model.score(Xs, y)
    print(f"   Precision training: {train_acc*100:.1f}%")

    print("\n5. Pesos aprendidos:")
    for name, coef in zip(FEATURE_NAMES, model.coef_[0]):
        print(f"   {name:18s}: {coef:+.3f}")
    print(f"   {'intercept':18s}: {model.intercept_[0]:+.3f}")

    # Exportar pesos + parametros del scaler para usar en produccion
    weights = {
        "feature_names": FEATURE_NAMES,
        "coefficients":  model.coef_[0].tolist(),
        "intercept":     float(model.intercept_[0]),
        "scaler_mean":   scaler.mean_.tolist(),
        "scaler_scale":  scaler.scale_.tolist(),
        "cv_accuracy":   float(scores.mean()),
        "train_accuracy": float(train_acc),
        "n_games":       int(len(X)),
        "trained_at":    datetime.now(MEXICO_TZ).strftime("%Y-%m-%d %H:%M CST"),
    }
    with open("public/model_weights.json", "w") as f:
        json.dump(weights, f, indent=2)

    print(f"\n✓ Modelo entrenado con {len(X)} partidos")
    print(f"  Pesos guardados en public/model_weights.json")
    print(f"  Precision esperada: {scores.mean()*100:.1f}%")

if __name__ == "__main__":
    main()
