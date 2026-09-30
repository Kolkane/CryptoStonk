"""Backtest farming — calcul des lectures TVL et volume (protocole.md, figé).

Ne s'exécute utilement qu'une fois les notes farming rendues dans
backtest/farming/notes/*.csv (format des sessions farm_NN.txt) : sans notes, il
s'arrête sans rien calculer.

Pour chaque token noté programme_pretge=oui : valeur de sortie
(airdrop_pct_farmers × airdrop_unlock_tge_pct × supply totale × médiane des
clôtures J+1 à J+7), puis selon base_eligibilite la lecture TVL (rendement
annualisé) et/ou la lecture volume (bps du volume cumulé). Q1 : médiane du
rendement TVL contre 5 %/an. Q2 : traction_tge forte contre le reste, backers
tier1 contre le reste, pour chaque lecture.

Usage  : python backtest/farming/calculer.py
Sortie : backtest/farming/resultats.md
"""

import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

from preparer import DOSSIER, RACINE, lire_csv, serie_tvl, serie_volume

sys.path.insert(0, str(RACINE / "backtest"))
from bilan_passage import charger_notes  # noqa: E402
from mesurer_performance import appel_cg, serie_journaliere  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

CHAMPS_FARMING = ("programme_pretge", "debut_programme", "base_eligibilite",
                  "airdrop_pct_farmers", "airdrop_unlock_tge_pct", "confiance")
COUVERTURE_MIN = 0.9
JOURS_SORTIE = range(1, 8)
JOURS_SORTIE_MIN = 5
SEUIL_Q1 = 5.0  # %/an


def nombre(texte):
    brut = re.sub(r"[%\s]", "", str(texte or "")).replace(",", ".")
    try:
        return float(brut)
    except ValueError:
        return None


def charger_notes_farming():
    """{id: note} ; arrêt sur divergence entre deux fichiers."""
    par_id = {}
    for fichier in sorted((DOSSIER / "notes").glob("*.csv")):
        for note in lire_csv(fichier):
            identifiant = (note.get("id_coingecko") or "").strip()
            if identifiant:
                par_id.setdefault(identifiant, []).append((fichier.name, note))
    conflits = [f"{i} ({', '.join(f for f, _ in v)})" for i, v in par_id.items()
                if any(str(n.get(c) or "").strip().lower() != str(v[0][1].get(c) or "").strip().lower()
                       for _, n in v[1:] for c in CHAMPS_FARMING)]
    if conflits:
        print("Conflits de notes farming, à résoudre à la main : " + " ; ".join(conflits))
        sys.exit(1)
    return {i: v[0][1] for i, v in par_id.items()}


def valeur_sortie(identifiant, date_tge, note):
    """(valeur en $, détail) ou (None, raison)."""
    pct, unlock = nombre(note.get("airdrop_pct_farmers")), nombre(note.get("airdrop_unlock_tge_pct"))
    if pct is None or unlock is None:
        return None, "airdrop_pct_farmers ou airdrop_unlock_tge_pct manquant"
    fiche = appel_cg(f"/coins/{identifiant}", {"localization": "false", "tickers": "false",
                                                "market_data": "true", "community_data": "false",
                                                "developer_data": "false"})
    supply = (fiche.get("market_data") or {}).get("total_supply")
    if not supply:
        return None, "total_supply CoinGecko absente"
    serie = serie_journaliere(identifiant)
    tge = date.fromisoformat(date_tge)
    clotures = [serie[j] for j in ((tge + timedelta(days=n)).isoformat() for n in JOURS_SORTIE)
                if j in serie]
    if len(clotures) < JOURS_SORTIE_MIN:
        return None, f"{len(clotures)} clôture(s) sur J+1..J+7"
    prix = statistics.median(clotures)
    return pct / 100 * unlock / 100 * supply * prix, f"supply {supply:,.0f}, prix médian {prix:.4g} $"


def fenetre(serie, debut, date_tge):
    """Points de la série dans [debut, TGE[ et taux de couverture des jours."""
    points = [(j, v) for j, v in serie if debut <= j < date_tge]
    jours = (date.fromisoformat(date_tge) - date.fromisoformat(debut)).days
    return points, (len(points) / jours if jours > 0 else 0), jours


def cellule(n_med, unite):
    n, med = n_med
    return f"n={n}, {med:.1f} {unite}" if med is not None else f"n={n}, —"


def mediane_groupes(valeurs, notes_backtest, champ, favorable):
    groupes = {"favorable": [], "reste": []}
    for identifiant, v in valeurs.items():
        cle = ("favorable" if str(notes_backtest.get(identifiant, {}).get(champ) or "").strip().lower()
               == favorable else "reste")
        groupes[cle].append(v)
    return {k: (len(v), statistics.median(v) if v else None) for k, v in groupes.items()}


def main():
    notes = charger_notes_farming()
    if not notes:
        print("Aucune note farming dans backtest/farming/notes/ : rien à calculer "
              "(protocole figé, sessions dans backtest/farming/sessions/).")
        return

    candidats = {c["id_coingecko"]: c for c in lire_csv(DOSSIER / "candidats.csv")}
    dates_tge = {l["id_coingecko"]: l["date_tge"]
                 for l in lire_csv(RACINE / "backtest" / "performances.csv")}
    notes_backtest = charger_notes()

    lignes, lecture_tvl, lecture_volume = [], {}, {}
    for identifiant, note in sorted(notes.items()):
        c = candidats.get(identifiant)
        if not c or str(note.get("programme_pretge") or "").strip().lower() != "oui":
            continue
        date_tge = dates_tge.get(identifiant)
        base = str(note.get("base_eligibilite") or "").strip().lower()
        debut = str(note.get("debut_programme") or "").strip()
        if debut and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", debut):
            debut = ""  # format invalide : traité comme manquant
        valeur, detail = valeur_sortie(identifiant, date_tge, note)
        ligne = {"ticker": c["ticker"], "base": base or "?", "valeur": valeur, "detail": detail,
                 "tvl": "—", "volume": "—"}

        if valeur is not None and debut and base in ("tvl", "mixte"):
            if not c["slug_defillama"]:
                ligne["tvl"] = "absent de DefiLlama"
            else:
                points, taux, jours = fenetre(serie_tvl(c["genre_defillama"], c["slug_defillama"]),
                                              debut, date_tge)
                tvl_moy = statistics.mean(v for _, v in points) if points else 0
                if taux < COUVERTURE_MIN or tvl_moy <= 0:
                    ligne["tvl"] = f"couverture {taux:.0%} : non mesurable"
                else:
                    rendement = valeur / (tvl_moy * jours / 365.25) * 100
                    lecture_tvl[identifiant] = rendement
                    ligne["tvl"] = f"{rendement:.1f} %/an (TVL moy. {tvl_moy:,.0f} $, {jours} j)"
        if valeur is not None and debut and base in ("volume", "mixte"):
            if not c["volume_sources"]:
                ligne["volume"] = c["couverture_volume"] or "aucune série"
            else:
                points, taux, jours = fenetre(serie_volume(c["volume_sources"].split("|")),
                                              debut, date_tge)
                cumul = sum(v for _, v in points)
                if taux < COUVERTURE_MIN or cumul <= 0:
                    ligne["volume"] = f"couverture {taux:.0%} : non mesurable"
                else:
                    bps = valeur / cumul * 10_000
                    lecture_volume[identifiant] = bps
                    ligne["volume"] = f"{bps:.1f} bps (volume {cumul:,.0f} $, {jours} j)"
        if valeur is not None and not debut:
            ligne["tvl"] = ligne["volume"] = "debut_programme manquant"
        lignes.append(ligne)
        print(f"  {c['ticker']:<8} {base or '?':<7} TVL : {ligne['tvl']} | volume : {ligne['volume']}")

    L = ["# Backtest farming — résultats", "",
         f"_Calculé le {date.today().isoformat()} selon `protocole.md` (figé avant mesure)._", "",
         "| Token | Base | Valeur de sortie | Lecture TVL | Lecture volume |", "|---|---|---|---|---|"]
    for l in lignes:
        valeur = f"{l['valeur']:,.0f} $" if l["valeur"] is not None else f"non mesurable ({l['detail']})"
        L.append(f"| {l['ticker']} | {l['base']} | {valeur} | {l['tvl']} | {l['volume']} |")

    L += ["", "## Q1 — rendement annualisé TVL contre 5 %/an", ""]
    if lecture_tvl:
        mediane = statistics.median(lecture_tvl.values())
        L.append(f"Médiane : **{mediane:.1f} %/an** (n={len(lecture_tvl)}), "
                 f"{'au-dessus' if mediane > SEUIL_Q1 else 'en dessous'} de {SEUIL_Q1:.0f} %/an.")
    else:
        L.append("Aucune lecture TVL mesurable.")

    L += ["", "## Q2 — traction forte et backers tier1 contre le reste", "",
          "| Lecture | Découpage | Favorable (n, médiane) | Reste (n, médiane) |", "|---|---|---|---|"]
    for nom, valeurs, unite in (("TVL", lecture_tvl, "%/an"), ("volume", lecture_volume, "bps")):
        for champ, favorable in (("traction_tge", "forte"), ("backers", "tier1")):
            g = mediane_groupes(valeurs, notes_backtest, champ, favorable)
            L.append(f"| {nom} | {champ} = {favorable} | {cellule(g['favorable'], unite)} "
                     f"| {cellule(g['reste'], unite)} |")

    fichier = DOSSIER / "resultats.md"
    fichier.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
