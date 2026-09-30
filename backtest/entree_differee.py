"""Backtest v0 — test d'entrée différée : acheter à J+90 plutôt qu'au TGE.

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de
plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4,
pas la détection de problèmes.

Population : tokens joints ayant un prix à J+90 (mesuré) et à J+180 (mesuré, ou
imputé à -100 % si le token est mort entre les deux).
Mesure : perf J+90 -> J+180 vs BTC = (P180/P90) / (BTC180/BTC90) - 1, déduite des
perfs relatives de performances.csv : (1 + rel180) / (1 + rel90) - 1.
Groupes : tous, hors plancher, plancher ; n, médiane, part positive. Aucun autre
découpage.

La règle de décision est écrite en tête de la sortie, avant les résultats.

Usage  : python backtest/entree_differee.py
Sortie : backtest/entree_differee.md
"""

import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

from analyser_notation import est_fantome, lire_csv
from bilan_passage import JOURS_SANS_COTATION_MORT, charger_notes, valeur_jn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
REGLE = ("médiane hors plancher >= 0 : entrée différée à creuser ; "
         "< 0 : pas d'achat post-TGE dans ce régime")


def ligne_groupe(nom, valeurs):
    if not valeurs:
        return f"| {nom} | 0 | — | — |"
    positifs = sum(1 for v in valeurs if v > 0)
    return (f"| {nom} | {len(valeurs)} | {statistics.median(valeurs):+.1f} % "
            f"| {100 * positifs / len(valeurs):.0f} % ({positifs}) |")


def main():
    seuil_mort = (date.today() - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()
    notes = charger_notes()
    perfs = lire_csv(RACINE / "backtest" / "performances.csv")

    groupes = {"tous": [], "hors plancher": [], "plancher": []}
    imputes = 0
    for ligne in perfs:
        identifiant = ligne["id_coingecko"]
        if identifiant not in notes or (ligne.get("statut") or "") == "non_mesurable":
            continue
        if not ligne.get("rel_btc_j90_pct"):
            continue  # pas de prix à J+90 : hors population
        rel90 = float(ligne["rel_btc_j90_pct"])
        if rel90 <= -100:
            continue
        derniere = ligne.get("derniere_cotation") or ""
        rel180, impute = valeur_jn(ligne, 180, bool(derniere) and derniere < seuil_mort)
        if rel180 is None:
            continue
        imputes += impute
        perf = ((1 + rel180 / 100) / (1 + rel90 / 100) - 1) * 100
        groupes["tous"].append(perf)
        groupes["plancher" if est_fantome(notes[identifiant]) else "hors plancher"].append(perf)

    hors = groupes["hors plancher"]
    mediane_hors = statistics.median(hors) if hors else None
    if mediane_hors is None:
        verdict = "indéterminé : aucun token hors plancher dans la population"
    elif mediane_hors >= 0:
        verdict = f"médiane hors plancher {mediane_hors:+.1f} % >= 0 : **entrée différée à creuser**"
    else:
        verdict = (f"médiane hors plancher {mediane_hors:+.1f} % < 0 : "
                   f"**pas d'achat post-TGE dans ce régime**")

    L = ["# Test d'entrée différée — achat à J+90 plutôt qu'au TGE", "",
         f"_Généré le {date.today().isoformat()} par backtest/entree_differee.py._", "",
         "## Règle de décision (posée avant les résultats)", "",
         f"> {REGLE[0].upper() + REGLE[1:]}.", "",
         "## Mesure", "",
         "Population : tokens notés avec un prix à J+90 et à J+180 (morts entre J+90 et J+180 "
         f"imputés à -100 % : {imputes}). Perf J+90 -> J+180 vs BTC = "
         "(P180/P90) / (BTC180/BTC90) - 1.", "",
         "| Groupe | n | Médiane | Part positive |", "|---|---|---|---|"]
    for nom, valeurs in groupes.items():
        L.append(ligne_groupe(nom, valeurs))
    L += ["", "## Application de la règle", "", verdict, "",
          "Une seule fenêtre de marché (TGE d'octobre 2025 à juin 2026) : le verdict vaut pour "
          "ce régime.", ""]

    fichier = RACINE / "backtest" / "entree_differee.md"
    fichier.write_text("\n".join(L), encoding="utf-8")
    for nom, valeurs in groupes.items():
        if valeurs:
            print(f"  {nom:<14} n={len(valeurs):>3}  médiane {statistics.median(valeurs):+7.1f} %  "
                  f"positifs {100 * sum(1 for v in valeurs if v > 0) / len(valeurs):.0f} %")
    print(f"Verdict : {verdict.replace('**', '')}")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
