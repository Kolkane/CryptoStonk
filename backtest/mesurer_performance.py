"""Backtest v0 — étape 2 : performance prix à J+30 / J+90 / J+180 après TGE.

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de
plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4,
pas la détection de problèmes.

Pour chaque token de backtest/echantillon.csv : performance absolue et relative
à BTC sur la même fenêtre (rendement token / rendement BTC − 1). Une fenêtre qui
dépasse aujourd'hui, ou sans cotation (token mort/délisté), reste vide.
Même throttle CoinGecko que l'étape 1, 1 appel par token.

Dates de TGE : par défaut, première cotation CoinGecko (proxy). Les vraies dates
trouvées en notation se déclarent dans backtest/overrides_tge.csv
(id_coingecko;date_tge_reelle;source) et priment. Si la date réelle précède
l'historique CoinGecko du token (plafond 365 j de l'offre gratuite), les
fenêtres passent « non mesurable » plutôt que d'être mesurées depuis la première
cotation — on ne réintroduit pas le décalage en silence.

Usage  : python backtest/mesurer_performance.py [--ids id1,id2]
         --ids : re-mesure ces tokens seulement et fusionne dans performances.csv
Sortie : backtest/performances.csv
Clé optionnelle : COINGECKO_API_KEY (offre démo).
"""

import argparse
import csv
import os
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
CG = "https://api.coingecko.com/api/v3"
ENTETES = {"User-Agent": "CryptoStonk/0.1 (outil interne)"}
PAUSE = 13  # mesuré : sous ~5 appels/min le sans-clé ne déclenche plus de 429
HISTO_MAX_JOURS = 365  # plafond d'historique de l'offre gratuite
FENETRES = (30, 90, 180)
TOLERANCE_JOURS = 3  # même tolérance que prix_vers

_dernier_appel = 0.0


def appel_cg(chemin, params=None):
    global _dernier_appel
    entetes = dict(ENTETES)
    cle = os.environ.get("COINGECKO_API_KEY")
    if cle:
        entetes["x-cg-demo-api-key"] = cle
    for _ in range(5):
        attente = PAUSE - (time.monotonic() - _dernier_appel)
        if attente > 0:
            time.sleep(attente)
        _dernier_appel = time.monotonic()
        reponse = requests.get(f"{CG}{chemin}", params=params, headers=entetes, timeout=60)
        if reponse.status_code == 429:
            pause = int(reponse.headers.get("Retry-After") or 30)
            print(f"  429 CoinGecko, pause {pause} s")
            time.sleep(pause)
            continue
        if reponse.status_code == 401:
            raise RuntimeError(f"CoinGecko 401 sur {chemin} : hors offre gratuite "
                               f"(historique plafonné à {HISTO_MAX_JOURS} j)")
        reponse.raise_for_status()
        return reponse.json()
    raise RuntimeError("CoinGecko : rate limit persistant, réessayez plus tard")


def lire_csv(chemin):
    with chemin.open(encoding="utf-8-sig", newline="") as entree:
        return list(csv.DictReader(entree, delimiter=";"))


def lire_overrides():
    fichier = RACINE / "backtest" / "overrides_tge.csv"
    if not fichier.exists():
        return {}
    return {l["id_coingecko"].strip(): (l["date_tge_reelle"].strip(), (l.get("source") or "").strip())
            for l in lire_csv(fichier) if (l.get("id_coingecko") or "").strip()}


def serie_journaliere(id_coingecko):
    """{date ISO: dernier prix du jour} depuis market_chart days=365."""
    brut = appel_cg(f"/coins/{id_coingecko}/market_chart",
                    {"vs_currency": "usd", "days": str(HISTO_MAX_JOURS)})
    serie = {}
    for ts, prix in brut.get("prices") or []:
        jour = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
        serie[jour] = prix  # le dernier point du jour écrase les précédents
    return serie


def prix_vers(serie, jour_cible):
    """Prix au jour le plus proche dans ±3 jours (préférence : exact, puis après)."""
    for decalage in (0, 1, -1, 2, -2, 3, -3):
        jour = (date.fromisoformat(jour_cible) + timedelta(days=decalage)).isoformat()
        if jour in serie:
            return serie[jour]
    return None


def mesurer_token(t, btc, overrides, aujourd_hui):
    try:
        serie = serie_journaliere(t["id_coingecko"])
    except requests.RequestException as erreur:
        print(f"  {t['ticker']} : erreur réseau ({erreur}), fenêtres vides")
        serie = {}

    tge, origine = t["date_tge"], "coingecko"
    if t["id_coingecko"] in overrides:
        date_reelle, source = overrides[t["id_coingecko"]]
        tge, origine = date_reelle, f"override:{source or 'sans source'}"

    ligne = {"ticker": t["ticker"], "id_coingecko": t["id_coingecko"],
             "verticale": t["verticale"], "date_tge": tge, "origine_tge": origine,
             "derniere_cotation": max(serie) if serie else ""}
    for n in FENETRES:
        ligne[f"perf_j{n}_pct"] = ligne[f"rel_btc_j{n}_pct"] = ""

    premiere = min(serie) if serie else ""
    if serie and origine != "coingecko" and tge < (
            date.fromisoformat(premiere) - timedelta(days=TOLERANCE_JOURS)).isoformat():
        # la vraie date précède l'historique CoinGecko : aucun prix au TGE — on ne
        # mesure PAS depuis la première cotation, ce serait le proxy réintroduit en douce
        ligne["statut"] = "non_mesurable"
        return ligne

    p0, b0 = prix_vers(serie, tge), prix_vers(btc, tge)
    for n in FENETRES:
        cible = (date.fromisoformat(tge) + timedelta(days=n)).isoformat()
        pt, bt = prix_vers(serie, cible), prix_vers(btc, cible)
        if cible > aujourd_hui or not (p0 and pt and b0 and bt):
            continue
        ligne[f"perf_j{n}_pct"] = round((pt / p0 - 1) * 100, 1)
        ligne[f"rel_btc_j{n}_pct"] = round(((pt / p0) / (bt / b0) - 1) * 100, 1)
    complet = all(ligne[f"rel_btc_j{n}_pct"] != "" for n in FENETRES)
    ligne["statut"] = "ok" if complet else "partiel"
    return ligne


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--ids", help="re-mesure ciblée : ids CoinGecko séparés par des "
                                         "virgules, fusionnés dans performances.csv")
    options = analyseur.parse_args()

    fichier_echantillon = RACINE / "backtest" / "echantillon.csv"
    if not fichier_echantillon.exists():
        print("Pas d'échantillon — lancez d'abord backtest/constituer_echantillon.py")
        return
    tokens = lire_csv(fichier_echantillon)
    overrides = lire_overrides()
    fichier_sortie = RACINE / "backtest" / "performances.csv"

    existantes = {}
    if options.ids:
        cibles = {i.strip() for i in options.ids.split(",") if i.strip()}
        inconnues = cibles - {t["id_coingecko"] for t in tokens}
        if inconnues:
            print(f"  ! ids hors échantillon ignorés : {', '.join(sorted(inconnues))}")
        a_mesurer = [t for t in tokens if t["id_coingecko"] in cibles]
        if fichier_sortie.exists():
            for l in lire_csv(fichier_sortie):
                l.setdefault("origine_tge", "coingecko")
                existantes[l["id_coingecko"]] = l
    else:
        a_mesurer = tokens

    if not a_mesurer:
        print("Rien à mesurer.")
        return
    corriges = [t["ticker"] for t in a_mesurer if t["id_coingecko"] in overrides]
    if corriges:
        print(f"Dates de TGE corrigées par overrides_tge.csv : {', '.join(corriges)}")
    print(f"{len(a_mesurer)} token(s), série BTC puis 1 appel par token "
          f"(~{round((len(a_mesurer) + 1) * PAUSE / 60)} min)")
    btc = serie_journaliere("bitcoin")
    aujourd_hui = date.today().isoformat()

    for rang, t in enumerate(a_mesurer, 1):
        ligne = mesurer_token(t, btc, overrides, aujourd_hui)
        existantes[t["id_coingecko"]] = ligne
        if ligne["statut"] == "non_mesurable":
            affichage = "non mesurable (TGE réel avant l'historique CoinGecko)"
        else:
            affichage = "  ".join(f"J+{n} {str(ligne[f'rel_btc_j{n}_pct']) or '—':>8}"
                                  for n in FENETRES) + "  (rel. BTC, %)"
        print(f"  [{rang}/{len(a_mesurer)}] {t['ticker']:<10} {affichage}")

    lignes = [existantes[t["id_coingecko"]] for t in tokens if t["id_coingecko"] in existantes]
    colonnes = ["ticker", "id_coingecko", "verticale", "date_tge", "origine_tge", "derniere_cotation"]
    for n in FENETRES:
        colonnes += [f"perf_j{n}_pct", f"rel_btc_j{n}_pct"]
    colonnes.append("statut")
    with fichier_sortie.open("w", encoding="utf-8-sig", newline="") as sortie:
        redacteur = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";", restval="")
        redacteur.writeheader()
        redacteur.writerows(lignes)

    for n in FENETRES:
        valeurs = [float(l[f"rel_btc_j{n}_pct"]) for l in lignes if l[f"rel_btc_j{n}_pct"] != ""]
        if valeurs:
            print(f"  médiane rel. BTC J+{n} : {statistics.median(valeurs):+.1f} % ({len(valeurs)} tokens)")
    j90 = sorted((l for l in lignes if l["rel_btc_j90_pct"] != ""),
                 key=lambda l: float(l["rel_btc_j90_pct"]), reverse=True)
    if j90:
        tetes = ", ".join(f"{l['ticker']} {float(l['rel_btc_j90_pct']):+.0f} %" for l in j90[:5])
        queues = ", ".join(f"{l['ticker']} {float(l['rel_btc_j90_pct']):+.0f} %" for l in j90[-5:])
        print(f"  top J+90 : {tetes}")
        print(f"  flop J+90 : {queues}")
    print(f"Écrit : {fichier_sortie.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
