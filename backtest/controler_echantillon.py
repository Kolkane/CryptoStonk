"""Backtest v0 — contrôle qualité de l'échantillon avant notation.

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de
plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4,
pas la détection de problèmes. Ce contrôle vérifie en plus que l'échantillon
lui-même ne ment pas : complétude des fenêtres, biais du survivant, distribution.

Trois questions :
1. complétude — combien de tokens ont leurs fenêtres J+30/90/180, et pourquoi
   les autres ne les ont pas (pas encore écoulée, série arrêtée, trou) ;
2. biais du survivant — CoinGecko déliste les tokens morts : un token sans
   cotation depuis 14 j est réputé mort, et ses fenêtres postérieures à la mort
   sont imputées à -100 % (jamais exclues) ; l'univers TGE de la période est
   estimé via DefiLlama /protocols (proxy : listedAt + symbole), en écartant les
   fiches dont le token préexiste à la fenêtre (nouveaux produits de protocoles
   établis) et les instruments ; /emissions (vraies dates de TGE) est payante ;
3. distribution — perf relative BTC à J+90 : min, médiane, max, % positifs.
   Presque tout positif = signal de biais, pas de marché facile.

Usage  : python backtest/controler_echantillon.py [--debut 2025-10-02] [--fin 2026-06-30]
Sortie : backtest/controle_echantillon.md
"""

import argparse
import csv
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
FENETRES = (30, 90, 180)
SEUIL_TVL_MORT = 10_000  # en dessous : protocole probablement mort/abandonné
JOURS_SANS_COTATION_MORT = 14
MARQUEURS_INSTRUMENTS = ("staked", "restaked", "wrapped", "bridged", "t-bill", "tbill",
                         "treasury", "fund", "overnight", "tokenized", "index")

RAISONS = {"ok": "ok", "future": "pas encore écoulée",
           "arretee": "série arrêtée", "trou": "trou de données"}


def lire_csv(chemin):
    with chemin.open(encoding="utf-8-sig", newline="") as entree:
        return list(csv.DictReader(entree, delimiter=";"))


def raison_fenetre(ligne, n, aujourd_hui):
    if ligne.get(f"rel_btc_j{n}_pct"):
        return "ok"
    cible = date.fromisoformat(ligne["date_tge"]) + timedelta(days=n)
    if cible.isoformat() > aujourd_hui:
        return "future"
    derniere = ligne.get("derniere_cotation") or ""
    if derniere and derniere < (cible - timedelta(days=3)).isoformat():
        return "arretee"
    return "trou"


def valeur_ou_imputation(ligne, n, est_mort):
    """Valeur mesurée, sinon -100 % si le token est mort avant la fenêtre, sinon None.
    Un mort reste à -100 % même pour une fenêtre pas encore « écoulée »."""
    if ligne.get(f"rel_btc_j{n}_pct"):
        return float(ligne[f"rel_btc_j{n}_pct"]), False
    if est_mort:
        cible = (date.fromisoformat(ligne["date_tge"]) + timedelta(days=n)).isoformat()
        if cible > (ligne.get("derniere_cotation") or ""):
            return -100.0, True
    return None, False


def stats(valeurs):
    if not valeurs:
        return None
    return {"n": len(valeurs), "min": min(valeurs), "mediane": statistics.median(valeurs),
            "max": max(valeurs), "pct_positifs": 100 * sum(1 for v in valeurs if v > 0) / len(valeurs)}


def ligne_stats(nom, s):
    if not s:
        return f"| {nom} | 0 | — | — | — | — |"
    return (f"| {nom} | {s['n']} | {s['min']:+.1f} % | {s['mediane']:+.1f} % "
            f"| {s['max']:+.1f} % | {s['pct_positifs']:.0f} % |")


def univers_defillama(debut, fin, tickers, noms):
    """Estimation d'univers : protocoles DefiLlama à token, listés sur la fenêtre,
    nos verticales — en écartant les fiches dont le symbole existe déjà avant la
    fenêtre (token préexistant : nouveau produit, pas TGE) et les instruments,
    puis dédoublonnées par symbole. listedAt = date d'ajout DefiLlama, proxy."""
    brut = yaml.safe_load((RACINE / "config" / "verticals.yaml").read_text(encoding="utf-8"))
    verticales = {c.lower(): v for v, cats in brut.items() for c in cats}
    reponse = requests.get("https://api.llama.fi/protocols", timeout=120,
                           headers={"User-Agent": "CryptoStonk/0.1 (outil interne)"})
    reponse.raise_for_status()
    donnees = reponse.json()

    symboles_anciens = set()
    for p in donnees:
        liste_le = p.get("listedAt")
        symbole = (p.get("symbol") or "-").strip().upper()
        # une fiche sans listedAt est ancienne par définition
        if symbole not in ("-", "") and (
                not liste_le or date.fromtimestamp(liste_le).isoformat() < debut):
            symboles_anciens.add(symbole)

    par_symbole, exclus_anciens, exclus_instruments = {}, 0, 0
    for p in donnees:
        liste_le = p.get("listedAt")
        if not liste_le:
            continue
        jour = date.fromtimestamp(liste_le).isoformat()
        verticale = verticales.get((p.get("category") or "").lower())
        symbole = (p.get("symbol") or "-").strip().upper()
        if not (debut <= jour <= fin) or not verticale or symbole in ("-", ""):
            continue
        if symbole in symboles_anciens:
            exclus_anciens += 1
            continue
        if any(m in (p.get("name") or "").lower() for m in MARQUEURS_INSTRUMENTS):
            exclus_instruments += 1
            continue
        if symbole not in par_symbole or (p.get("tvl") or 0) > (par_symbole[symbole].get("tvl") or 0):
            par_symbole[symbole] = p

    absents, matches = [], 0
    for symbole, p in par_symbole.items():
        nom = (p.get("name") or "").lower()
        trouve = symbole in tickers or any(
            len(n) >= 4 and (n in nom or nom in n) for n in noms)
        if trouve:
            matches += 1
        else:
            absents.append({"nom": p.get("name", ""), "symbole": symbole,
                            "verticale": verticales.get((p.get("category") or "").lower(), "?"),
                            "tvl": round(p.get("tvl") or 0)})
    absents.sort(key=lambda a: -a["tvl"])
    return len(par_symbole), matches, absents, exclus_anciens, exclus_instruments


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--debut", default="2025-10-02", help="début de fenêtre effective")
    analyseur.add_argument("--fin", default="2026-06-30")
    options = analyseur.parse_args()

    fichier_perfs = RACINE / "backtest" / "performances.csv"
    if not fichier_perfs.exists():
        print("Pas de performances.csv — lancez d'abord backtest/mesurer_performance.py")
        return
    echantillon = lire_csv(RACINE / "backtest" / "echantillon.csv")
    perfs = lire_csv(fichier_perfs)
    aujourd_hui = date.today().isoformat()
    seuil_mort = (date.today() - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()

    # morts : plus aucune cotation depuis JOURS_SANS_COTATION_MORT jours
    morts = {l["id_coingecko"] for l in perfs
             if (l.get("derniere_cotation") or "") and l["derniere_cotation"] < seuil_mort}

    # 1. complétude
    compte = {n: {r: 0 for r in RAISONS} for n in FENETRES}
    diagnostics = []
    for l in perfs:
        raisons = {n: raison_fenetre(l, n, aujourd_hui) for n in FENETRES}
        for n in FENETRES:
            compte[n][raisons[n]] += 1
        if any(r != "ok" for r in raisons.values()):
            details = "; ".join(f"J+{n} : {RAISONS[raisons[n]]}"
                                for n in FENETRES if raisons[n] != "ok")
            if not (l.get("derniere_cotation") or ""):
                details = "aucune donnée de prix récupérée"
            diagnostics.append((l, details))
    complets = sum(1 for l in perfs
                   if all(raison_fenetre(l, n, aujourd_hui) == "ok" for n in FENETRES))

    # 2. univers (survivant)
    tickers = {l["ticker"].upper() for l in echantillon}
    noms = {l["nom"].lower() for l in echantillon}
    try:
        taille_univers, matches, absents, exclus_anciens, exclus_instruments = \
            univers_defillama(options.debut, options.fin, tickers, noms)
        erreur_univers = None
    except requests.RequestException as erreur:
        taille_univers, matches, absents = 0, 0, []
        exclus_anciens = exclus_instruments = 0
        erreur_univers = str(erreur)
    absents_morts = [a for a in absents if a["tvl"] < SEUIL_TVL_MORT]

    # 3. distributions : mesures + imputations -100 % des morts
    series = {}
    for n in FENETRES:
        mesures, imputees = [], 0
        for l in perfs:
            valeur, imputee = valeur_ou_imputation(l, n, l["id_coingecko"] in morts)
            if valeur is not None:
                mesures.append((valeur, imputee))
                imputees += imputee
        series[n] = {"mesures": [v for v, i in mesures if not i],
                     "avec_imputes": [v for v, _ in mesures], "imputees": imputees}
    s_survivants = stats(series[90]["mesures"])
    s_imputes = stats(series[90]["avec_imputes"])

    tickers_morts = sorted(l["ticker"] for l in perfs if l["id_coingecko"] in morts)

    # rapport
    lignes = [
        "# Contrôle qualité de l'échantillon — backtest v0", "",
        f"_Généré le {aujourd_hui} par backtest/controler_echantillon.py — à relancer "
        f"après toute extension de l'échantillon._", "",
        "Rappel du cadrage : la couche 2 n'est pas reconstructible (pas d'historique de "
        "plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4, "
        "pas la détection de problèmes.", "",
        "## 1. Complétude des fenêtres", "",
        f"- Tokens ciblés : **{len(echantillon)}** (TGE de "
        f"{min(l['date_tge'] for l in echantillon)} à {max(l['date_tge'] for l in echantillon)}, "
        f"fenêtre effective {options.debut} -> {options.fin}).",
        f"- Données complètes J+30/J+90/J+180 : **{complets}**.", "",
        "| Fenêtre | ok | pas encore écoulée | série arrêtée | trou de données |",
        "|---|---|---|---|---|",
    ]
    for n in FENETRES:
        c = compte[n]
        lignes.append(f"| J+{n} | {c['ok']} | {c['future']} | {c['arretee']} | {c['trou']} |")
    lignes += ["", "Tokens incomplets et diagnostic :", "",
               "| Ticker | Verticale | TGE | Dernière cotation | Diagnostic |", "|---|---|---|---|---|"]
    for l, details in diagnostics:
        marque = " — **mort probable, fenêtres post-mortem imputées -100 %**" \
            if l["id_coingecko"] in morts else ""
        lignes.append(f"| {l['ticker']} | {l['verticale']} | {l['date_tge']} "
                      f"| {l.get('derniere_cotation') or '—'} | {details}{marque} |")

    lignes += ["", "## 2. Biais du survivant", "",
               "CoinGecko déliste ou cesse de suivre les tokens morts : ils ne peuvent pas entrer "
               "dans l'échantillon (le pré-filtre parcourt les pièces encore cotées). L'échantillon "
               "sur-représente donc structurellement les survivants, et les moyennes brutes mentent.", "",
               f"- Morts identifiés **dans** l'échantillon (aucune cotation depuis "
               f"{JOURS_SANS_COTATION_MORT} j) : **{len(morts)}** — "
               f"{', '.join(tickers_morts) or 'aucun'}. Leurs fenêtres postérieures à la mort "
               f"sont **imputées à -100 %**, pas exclues ; leurs fenêtres vécues gardent la mesure.", ""]
    if erreur_univers:
        lignes.append(f"- Estimation d'univers DefiLlama indisponible ({erreur_univers}).")
    else:
        pct_couverture = 100 * matches / taille_univers if taille_univers else 0
        lignes += [
            f"- Univers estimé (DefiLlama /protocols) : **{taille_univers}** lancements de token "
            f"sur la fenêtre, nos verticales — après exclusion de {exclus_anciens} fiches dont le "
            f"token préexiste à la fenêtre (nouveaux produits de protocoles établis, pas des TGE), "
            f"de {exclus_instruments} instruments, et dédoublonnage par symbole.",
            f"- Retrouvés dans l'échantillon : **{matches}** (couverture {pct_couverture:.0f} %). "
            f"Absents : **{len(absents)}**, dont **{len(absents_morts)}** avec TVL < "
            f"{SEUIL_TVL_MORT / 1000:.0f} k$ aujourd'hui (morts/abandonnés probables : la masse "
            f"invisible du biais).", "",
            "Principaux absents (TVL actuelle) :", "",
            "| Protocole | Symbole | Verticale | TVL |", "|---|---|---|---|"]
        for a in absents[:15]:
            lignes.append(f"| {a['nom']} | {a['symbole']} | {a['verticale']} | {a['tvl']:,} $ |"
                          .replace(",", " "))
        lignes += ["", "Limites de l'estimation : listedAt DefiLlama = date d'ajout au site, pas le "
                   "TGE ; rapprochement par symbole/nom approximatif ; DefiLlama a son propre biais "
                   "de survie (plus faible : les fiches mortes restent) ; /emissions (vraies dates "
                   "de TGE) est passée en offre payante."]

    note_imputation = (f"({series[90]['imputees']} imputation(s))" if series[90]["imputees"]
                       else "(aucun ajout : les morts de l'échantillon ont vécu jusqu'à leur J+90 — "
                            "leur -100 % mesuré y figure déjà le cas échéant)")
    lignes += ["", "## 3. Distribution — perf relative à BTC à J+90", "",
               "| Série | n | min | médiane | max | % > 0 |", "|---|---|---|---|---|---|",
               ligne_stats("Survivants (mesuré)", s_survivants),
               ligne_stats(f"Avec morts imputés -100 %", s_imputes), "",
               f"Imputations à J+90 : {note_imputation}", ""]
    for n in (30, 180):
        s_mesure, s_avec = stats(series[n]["mesures"]), stats(series[n]["avec_imputes"])
        if s_mesure:
            texte = (f"Complément J+{n} : médiane {s_mesure['mediane']:+.1f} %, "
                     f"{s_mesure['pct_positifs']:.0f} % positifs ({s_mesure['n']} mesurés)")
            if series[n]["imputees"]:
                texte += (f" ; avec {series[n]['imputees']} mort(s) imputé(s) : médiane "
                          f"{s_avec['mediane']:+.1f} %, {s_avec['pct_positifs']:.0f} % positifs "
                          f"({s_avec['n']}).")
            lignes.append(texte + ("" if texte.endswith(".") else "."))
    if s_survivants:
        if s_survivants["pct_positifs"] >= 70:
            lignes += ["", "**Signal de biais** : la grande majorité des survivants bat BTC à J+90. "
                       "Vu le biais du survivant ci-dessus, lire ces chiffres comme un plafond, "
                       "pas comme le marché."]
        elif s_survivants["mediane"] < 0:
            lignes += ["", "Médiane négative vs BTC : cohérent avec un marché de lancements difficile ; "
                       "le biais du survivant rend la réalité encore un peu pire que ces chiffres."]

    lignes += ["", "## Verdict avant notation", "",
               f"- Noter en priorité les tokens avec J+90 disponible ou imputé "
               f"({(s_imputes or {'n': 0})['n']} sur {len(echantillon)}).",
               f"- Garder les {len(morts)} morts et leurs -100 % dans toutes les moyennes : "
               f"les retirer regonflerait le biais.",
               "- L'échantillon ne couvre qu'une partie de l'univers réel : toute conclusion du "
               "backtest est un ordre de grandeur, pas une preuve.",
               "- Relancer ce contrôle après extension de l'échantillon ou nouvelle mesure."]

    fichier = RACINE / "backtest" / "controle_echantillon.md"
    fichier.write_text("\n".join(lignes), encoding="utf-8")

    print(f"{len(echantillon)} ciblés, {complets} complets 3 fenêtres, {len(morts)} morts "
          f"({series[90]['imputees']} imputation(s) à J+90, {series[180]['imputees']} à J+180)")
    if not erreur_univers and taille_univers:
        print(f"Univers DefiLlama filtré : {taille_univers}, couverture "
              f"{100 * matches / taille_univers:.0f} %, {len(absents_morts)} absents probablement morts "
              f"({exclus_anciens} fiches à token préexistant écartées)")
    if s_survivants:
        print(f"J+90 rel. BTC (survivants) : min {s_survivants['min']:+.1f} %, "
              f"médiane {s_survivants['mediane']:+.1f} %, max {s_survivants['max']:+.1f} %, "
              f"{s_survivants['pct_positifs']:.0f} % positifs")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
