"""Backtest v0 — étape 1 : constituer l'échantillon de tokens lancés (TGE).

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de
plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4,
pas la détection de problèmes.

Tokens listés entre --debut et --fin sur nos verticales, via l'API CoinGecko
gratuite (~10 appels/min : throttle 6,5 s, reprise sur 429, cache de progression
dans data/backtest/verifies.json — relancer reprend où on s'était arrêté).
Proxys assumés, étiquetés dans le CSV : date de TGE = première cotation
CoinGecko ; FDV initiale approchée = premier prix × offre implicite actuelle
(FDV actuelle / prix actuel) — à corriger à la main si l'offre a changé.

Limite de l'offre gratuite : historique de prix plafonné à 365 jours, donc la
fenêtre effective démarre au plus tôt ~360 j en arrière (affichée au lancement) ;
le tout début de la fenêtre demandée peut sortir du champ.

Usage  : python backtest/constituer_echantillon.py [--debut 2025-09-01]
         [--fin 2026-06-30] [--max-verifs 250] [--reset]
Sortie : backtest/echantillon.csv (cible : 50 tokens minimum)
Clé optionnelle : COINGECKO_API_KEY (offre démo) si le sans-clé rate-limite trop.
"""

import argparse
import csv
import json
import os
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
HISTO_MAX_JOURS = 365  # plafond d'historique de l'offre gratuite (days=max : payant)
# parts de fonds, LST, wrappés… : des instruments, pas des TGE de protocoles
MARQUEURS_INSTRUMENTS = ("staked", "restaked", "wrapped", "bridged", "t-bill", "tbill",
                         "treasury", "fund", "overnight", "tokenized", "index",
                         "xstock", "pre-ipo", " lst", "-lst")
ETIQUETTE = "v0 : TGE = première cotation CoinGecko ; FDV initiale approchée"
COLONNES = ["ticker", "nom", "id_coingecko", "verticale", "categorie_cg", "date_tge",
            "fdv_initiale_approx_usd", "fdv_actuelle_usd", "methode"]

# mots-clés cherchés dans les identifiants de catégories CoinGecko, par verticale
VERTICALES_MOTS = {
    "perps": ["perpetual"],
    "options": ["options"],
    "rwa": ["real-world"],
    "bridges": ["bridge-governance", "cross-chain-communication"],
    "lsd_restaking": ["liquid-staking", "restaking"],
    "lending": ["lending"],
    "dex": ["decentralized-exchange"],
    "rendement": ["yield"],
}

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


def choisir_categories():
    """Associe nos verticales aux catégories CoinGecko réelles (2 max par verticale)."""
    toutes = appel_cg("/coins/categories/list")
    selection = []
    for verticale, mots in VERTICALES_MOTS.items():
        trouvees = sorted((c["category_id"] for c in toutes
                           if any(m in c["category_id"] for m in mots)),
                          key=lambda i: (len(i), i))[:2]
        for categorie in trouvees:
            if all(categorie != c for _, c in selection):
                selection.append((verticale, categorie))
        if not trouvees:
            print(f"  ! aucune catégorie CoinGecko trouvée pour « {verticale} »")
    for verticale, categorie in selection:
        print(f"  {verticale:<14} <- {categorie}")
    return selection


def candidats_par_prefiltre(selection, debut):
    """Pré-filtre gratuit : ATL et ATH tous deux dans la fenêtre => historique de prix
    entièrement récent, donc probablement listé dans la fenêtre (confirmé ensuite)."""
    pool, ecartes = {}, 0
    for verticale, categorie in selection:
        marches = appel_cg("/coins/markets", {
            "vs_currency": "usd", "category": categorie, "order": "market_cap_desc",
            "per_page": 250, "page": 1, "sparkline": "false"})
        retenus = 0
        for piece in marches:
            atl, ath = (piece.get("atl_date") or "")[:10], (piece.get("ath_date") or "")[:10]
            if not atl or not ath or min(atl, ath) < debut:
                continue
            nom_id = f"{piece.get('name', '')} {piece['id']}".lower()
            symbole = (piece.get("symbol") or "").lower()
            if any(m in nom_id for m in MARQUEURS_INSTRUMENTS) or "usd" in symbole or "eur" in symbole:
                ecartes += 1
                continue
            if piece["id"] not in pool:
                pool[piece["id"]] = {**piece, "verticale": verticale, "categorie_cg": categorie}
                retenus += 1
        print(f"  {categorie:<28} {len(marches):>3} pièces, {retenus} candidates")
    print(f"  ({ecartes} instruments/wrappés écartés par marqueurs)")
    return pool


def verifier(piece, debut, fin):
    """Confirme la fenêtre par la première cotation ; renvoie la ligne CSV ou None."""
    serie = appel_cg(f"/coins/{piece['id']}/market_chart",
                     {"vs_currency": "usd", "days": str(HISTO_MAX_JOURS)})
    prix = serie.get("prices") or []
    if not prix:
        return None
    premier_ts, premier_prix = prix[0]
    date_tge = datetime.fromtimestamp(premier_ts / 1000, tz=timezone.utc).date().isoformat()
    if not (debut <= date_tge <= fin):
        return None
    fdv = piece.get("fully_diluted_valuation")
    actuel = piece.get("current_price")
    fdv_init = round(fdv * premier_prix / actuel) if fdv and actuel else ""
    return {
        "ticker": (piece.get("symbol") or "").upper(),
        "nom": piece.get("name", ""),
        "id_coingecko": piece["id"],
        "verticale": piece["verticale"],
        "categorie_cg": piece["categorie_cg"],
        "date_tge": date_tge,
        "fdv_initiale_approx_usd": fdv_init,
        "fdv_actuelle_usd": round(fdv) if fdv else "",
        "methode": ETIQUETTE,
    }


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--debut", default="2025-09-01")
    analyseur.add_argument("--fin", default="2026-06-30")
    analyseur.add_argument("--max-verifs", type=int, default=250,
                           help="vérifications par passage (1 appel API chacune)")
    analyseur.add_argument("--reset", action="store_true",
                           help="repart de zéro (efface CSV et cache de progression)")
    options = analyseur.parse_args()

    fichier_csv = RACINE / "backtest" / "echantillon.csv"
    fichier_cache = RACINE / "data" / "backtest" / "verifies.json"
    if options.reset:
        fichier_csv.unlink(missing_ok=True)
        fichier_cache.unlink(missing_ok=True)

    verifies = set(json.loads(fichier_cache.read_text(encoding="utf-8"))) if fichier_cache.exists() else set()
    fichier_cache.parent.mkdir(parents=True, exist_ok=True)

    # une première cotation collée au bord des 365 j d'historique gratuit peut être
    # un token plus ancien tronqué : on borne la fenêtre 5 j après ce bord
    borne_histo = (date.today() - timedelta(days=HISTO_MAX_JOURS - 5)).isoformat()
    debut_effectif = max(options.debut, borne_histo)
    if debut_effectif > options.debut:
        print(f"Historique gratuit plafonné à {HISTO_MAX_JOURS} j : fenêtre effective "
              f"{debut_effectif} -> {options.fin}")

    print("Catégories CoinGecko retenues :")
    selection = choisir_categories()
    print("Pré-filtre (ATL et ATH dans la fenêtre) :")
    pool = candidats_par_prefiltre(selection, options.debut)

    a_verifier = sorted((p for i, p in pool.items() if i not in verifies),
                        key=lambda p: p.get("market_cap_rank") or 10**9)
    a_verifier = a_verifier[:options.max_verifs]
    print(f"{len(pool)} candidates, {len(a_verifier)} à vérifier ce passage "
          f"({len(verifies)} déjà vues) — ~{round(len(a_verifier) * PAUSE / 60)} min")

    nouveau = not fichier_csv.exists()
    with fichier_csv.open("a", encoding="utf-8-sig" if nouveau else "utf-8", newline="") as sortie:
        redacteur = csv.DictWriter(sortie, fieldnames=COLONNES, delimiter=";")
        if nouveau:
            redacteur.writeheader()
        for rang, piece in enumerate(a_verifier, 1):
            try:
                ligne = verifier(piece, debut_effectif, options.fin)
            except requests.RequestException as erreur:
                print(f"  [{rang}/{len(a_verifier)}] {piece['id']} : erreur réseau ({erreur}), on continue")
                continue
            verifies.add(piece["id"])
            fichier_cache.write_text(json.dumps(sorted(verifies)), encoding="utf-8")
            if ligne:
                redacteur.writerow(ligne)
                sortie.flush()
                print(f"  [{rang}/{len(a_verifier)}] + {ligne['ticker']:<10} {ligne['date_tge']}  "
                      f"({ligne['verticale']})")
            else:
                print(f"  [{rang}/{len(a_verifier)}]   {piece['id']} hors fenêtre")

    with fichier_csv.open(encoding="utf-8-sig", newline="") as entree:
        lignes = list(csv.DictReader(entree, delimiter=";"))
    par_verticale = {}
    for l in lignes:
        par_verticale[l["verticale"]] = par_verticale.get(l["verticale"], 0) + 1
    print(f"Échantillon : {len(lignes)} tokens ({', '.join(f'{v} {n}' for v, n in sorted(par_verticale.items()))})")
    if len(lignes) < 50:
        print("Cible de 50 non atteinte — relancez (le cache reprend), élargissez --max-verifs "
              "ou la fenêtre --debut/--fin.")
    print(f"Écrit : {fichier_csv.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
