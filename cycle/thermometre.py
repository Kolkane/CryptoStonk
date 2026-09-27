"""Thermomètre de cycle — couche 1.

Mesure le niveau d'euphorie du marché sur 4 indicateurs publics et en tire
un score composite 0-100. Sert à dimensionner le risque, pas à timer au jour près.

Usage  : python cycle/thermometre.py
Sortie : data/cycle/AAAA-MM-JJ.json + résumé console.

Les seuils de scoring sont des heuristiques v0, à recalibrer sur données historiques.
"""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).resolve().parents[1]
ENTETES = {"User-Agent": "CryptoStonk/0.1 (outil interne)"}
ID_COINBASE = "886427730"  # l'app Coinbase, pas Coinbase Wallet (1278383455)


def get_json(url, timeout=60):
    reponse = requests.get(url, headers=ENTETES, timeout=timeout)
    reponse.raise_for_status()
    return reponse.json()


def rang_coinbase():
    """Rang de Coinbase dans le top 100 gratuit US de l'App Store (None = hors top 100)."""
    flux = get_json("https://rss.applemarketingtools.com/api/v2/us/apps/top-free/100/apps.json")
    for rang, app in enumerate(flux["feed"]["results"], 1):
        if app.get("id") == ID_COINBASE:
            return rang
    return None


def score_rang(rang):
    if rang is None:
        return 10
    for seuil, score in ((1, 100), (5, 95), (10, 90), (25, 75), (50, 60), (100, 40)):
        if rang <= seuil:
            return score
    return 10


def funding_annualise():
    """Funding moyen BTC+ETH annualisé en % (3 périodes de 8 h/jour). Binance, repli Bybit."""
    taux = []
    for symbole in ("BTCUSDT", "ETHUSDT"):
        try:
            d = get_json(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbole}", timeout=20)
            taux.append(float(d["lastFundingRate"]))
        except Exception:
            d = get_json(f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbole}", timeout=20)
            taux.append(float(d["result"]["list"][0]["fundingRate"]))
    return sum(taux) / len(taux) * 3 * 365 * 100


def score_funding(annuel):
    # ~11 %/an = taux neutre (0,01 % par période de 8 h)
    if annuel <= 0:
        return 5
    for seuil, score in ((5, 20), (11, 35), (20, 50), (40, 70), (80, 85)):
        if annuel <= seuil:
            return score
    return 95


def croissance_stablecoins():
    """Croissance de l'encours total des stablecoins sur 30 jours, en %."""
    serie = get_json("https://stablecoins.llama.fi/stablecoincharts/all", timeout=90)
    if len(serie) < 31:
        raise ValueError("série stablecoins trop courte")

    def total(point):
        for cle in ("totalCirculatingUSD", "totalCirculating"):
            valeur = point.get(cle)
            if isinstance(valeur, dict) and valeur.get("peggedUSD"):
                return float(valeur["peggedUSD"])
        raise ValueError(f"point sans encours exploitable : {list(point)}")

    return (total(serie[-1]) / total(serie[-31]) - 1) * 100


def score_stablecoins(pct):
    if pct <= 0:
        return 10
    for seuil, score in ((1, 30), (2, 45), (4, 65), (6, 80)):
        if pct <= seuil:
            return score
    return 90


def interet_google():
    """Intérêt Google Trends pour « bitcoin », 0-100 relatif au pic 12 mois. Optionnel."""
    from pytrends.request import TrendReq

    pt = TrendReq(hl="en-US", tz=0)
    pt.build_payload(["bitcoin"], timeframe="today 12-m")
    df = pt.interest_over_time()
    if df.empty:
        raise ValueError("série Trends vide")
    return int(df["bitcoin"].iloc[-1])


def lecture(score):
    if score < 25:
        return "froid — cycle déprimé, on peut chercher"
    if score < 50:
        return "tiède — conditions normales"
    if score < 75:
        return "chaud — sélectivité, réduire la taille des paris"
    return "euphorie — on n'achète pas ici"


def main():
    indicateurs = {}

    try:
        rang = rang_coinbase()
        indicateurs["rang_coinbase_appstore"] = {
            "valeur": rang if rang is not None else "hors top 100",
            "score": score_rang(rang),
            "unite": "rang top 100 gratuit US",
        }
    except Exception as erreur:
        indicateurs["rang_coinbase_appstore"] = {"valeur": None, "score": None, "note": f"échec : {erreur}"}

    try:
        annuel = funding_annualise()
        indicateurs["funding_btc_eth"] = {
            "valeur": round(annuel, 2), "score": score_funding(annuel), "unite": "% annualisé",
        }
    except Exception as erreur:
        indicateurs["funding_btc_eth"] = {"valeur": None, "score": None, "note": f"échec : {erreur}"}

    try:
        pct = croissance_stablecoins()
        indicateurs["stablecoins_30j"] = {
            "valeur": round(pct, 2), "score": score_stablecoins(pct), "unite": "% sur 30 j",
        }
    except Exception as erreur:
        indicateurs["stablecoins_30j"] = {"valeur": None, "score": None, "note": f"échec : {erreur}"}

    try:
        interet = interet_google()
        indicateurs["google_trends_bitcoin"] = {
            "valeur": interet, "score": interet, "unite": "0-100 relatif au pic 12 mois",
        }
    except ImportError:
        indicateurs["google_trends_bitcoin"] = {
            "valeur": None, "score": None, "note": "indisponible — pip install pytrends (optionnel)",
        }
    except Exception as erreur:
        indicateurs["google_trends_bitcoin"] = {"valeur": None, "score": None, "note": f"échec : {erreur}"}

    scores = [i["score"] for i in indicateurs.values() if i["score"] is not None]
    composite = round(sum(scores) / len(scores), 1) if scores else None

    resultat = {
        "date": date.today().isoformat(),
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "indicateurs": indicateurs,
        "score_composite": composite,
        "lecture": lecture(composite) if composite is not None else "aucun indicateur disponible",
    }

    dossier = RACINE / "data" / "cycle"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"{resultat['date']}.json"
    fichier.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Thermomètre de cycle — {resultat['date']}")
    for nom, i in indicateurs.items():
        if i["score"] is None:
            print(f"  {nom:<26} {i['note']}")
        else:
            print(f"  {nom:<26} {i['valeur']} {i.get('unite', '')}  ->  score {i['score']}")
    print(f"  {'COMPOSITE':<26} {composite}  ({resultat['lecture']})")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
