"""Test de rétention — la solution garde-t-elle ses utilisateurs quand les incitations s'arrêtent ?

Protocole figé et committé avant ce script : backtest/retention/protocole.md.

Population : tokens hors plancher joints à J+90, avec une série TVL DefiLlama
couvrant au moins 90 % des jours de J-30 à J+30 autour du TGE.
Rétention : TVL moyenne de J+23 à J+30 / TVL moyenne de J-30 à J-1.
Issues : perf vs BTC de J+30 à J+180 (principale) et de J+30 à J+90 (secondaire).
Contraste : split à la médiane de rétention, médiane d'issue de chaque côté.
Règle : moins de 20 mesurables = non concluant ; écart >= +20 pts en faveur de la
forte rétention sur l'issue principale = signal à creuser ; sinon pas de signal.

Usage  : python backtest/retention/calculer.py
Sortie : backtest/retention/resultats.md
"""

import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "backtest"))
sys.path.insert(0, str(RACINE / "backtest" / "farming"))
from analyser_notation import est_fantome, lire_csv  # noqa: E402
from bilan_passage import JOURS_SANS_COTATION_MORT, charger_notes, valeur_jn  # noqa: E402
from preparer import correspondances, serie_tvl  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DOSSIER = RACINE / "backtest" / "retention"
COUVERTURE_MIN = 0.9
N_MIN = 20
ECART_SIGNAL = 20.0
ISSUES = ((180, "principale"), (90, "secondaire"))


def perf_depuis_j30(ligne, n, est_mort):
    """Perf vs BTC de J+30 à J+n ; J+30 mesuré obligatoire, mort avant J+n = -100 %."""
    if (ligne.get("statut") or "") == "non_mesurable" or not ligne.get("rel_btc_j30_pct"):
        return None
    rel30 = float(ligne["rel_btc_j30_pct"])
    if rel30 <= -100:
        return None
    reln, _ = valeur_jn(ligne, n, est_mort)
    if reln is None:
        return None
    return ((1 + reln / 100) / (1 + rel30 / 100) - 1) * 100


def retention(serie, date_tge):
    """(ratio ou None, motif ou couverture)."""
    tge = date.fromisoformat(date_tge)
    jours = dict(serie)

    def points(debut, fin):
        return [jours[j] for j in ((tge + timedelta(days=d)).isoformat() for d in range(debut, fin + 1))
                if j in jours]

    taux = len(points(-30, 30)) / 61
    if taux < COUVERTURE_MIN:
        return None, f"série couvrant {taux:.0%} des jours"
    avant, apres = points(-30, -1), points(23, 30)
    if not avant or not apres:
        return None, "fenêtre avant ou après vide"
    moyenne_avant = statistics.mean(avant)
    if moyenne_avant <= 0:
        return None, "TVL pré-TGE nulle"
    return statistics.mean(apres) / moyenne_avant, f"série couvrant {taux:.0%} des jours"


def contraste(mesures):
    """mesures = [(rétention, issue)] -> médiane de rétention, groupes forte / faible."""
    mediane = statistics.median(r for r, _ in mesures)
    forte = [i for r, i in mesures if r > mediane]
    faible = [i for r, i in mesures if r < mediane]
    resultat = {"n": len(mesures), "mediane_retention": mediane,
                "n_forte": len(forte), "n_faible": len(faible),
                "med_forte": statistics.median(forte) if forte else None,
                "med_faible": statistics.median(faible) if faible else None}
    resultat["ecart"] = (resultat["med_forte"] - resultat["med_faible"]
                         if forte and faible else None)
    return resultat


def fmt(v, suffixe=" %"):
    return "—" if v is None else f"{v:+.1f}{suffixe}"


def main():
    seuil_mort = (date.today() - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()
    notes = charger_notes()
    population = []
    for ligne in lire_csv(RACINE / "backtest" / "performances.csv"):
        identifiant = ligne["id_coingecko"]
        derniere = ligne.get("derniere_cotation") or ""
        mort = bool(derniere) and derniere < seuil_mort
        v90, _ = valeur_jn(ligne, 90, mort)
        if identifiant in notes and v90 is not None and not est_fantome(notes[identifiant]):
            population.append({"id_coingecko": identifiant, "ticker": ligne["ticker"],
                               "verticale": ligne["verticale"], "date_tge": ligne["date_tge"],
                               "ligne": ligne, "mort": mort})
    correspondances(population)

    motifs = {}
    for t in population:
        if not t["slug_defillama"]:
            t["retention"], t["motif"] = None, "absent de DefiLlama"
        else:
            t["retention"], t["motif"] = retention(serie_tvl(t["genre_defillama"], t["slug_defillama"]),
                                                   t["date_tge"])
        if t["retention"] is None:
            cle = "série < 90 % des jours" if t["motif"].startswith("série couvrant") else t["motif"]
            motifs[cle] = motifs.get(cle, 0) + 1
        for n, _ in ISSUES:
            t[f"issue_{n}"] = perf_depuis_j30(t["ligne"], n, t["mort"])
        texte = f"{t['retention']:.0%}" if t["retention"] is not None else t["motif"]
        print(f"  {t['ticker']:<9} {t['methode']:<18} rétention {texte}")

    mesurables_retention = [t for t in population if t["retention"] is not None]
    resultats = {}
    for n, nom in ISSUES:
        mesures = [(t["retention"], t[f"issue_{n}"]) for t in mesurables_retention
                   if t[f"issue_{n}"] is not None]
        resultats[n] = contraste(mesures) if mesures else None

    principal = resultats[180]
    if not principal or principal["n"] < N_MIN:
        verdict = (f"**Non concluant** : {principal['n'] if principal else 0} token(s) mesurable(s) "
                   f"sur l'issue principale, seuil {N_MIN}.")
    elif principal["ecart"] is not None and principal["ecart"] >= ECART_SIGNAL:
        verdict = (f"**Signal à creuser** : écart {principal['ecart']:+.1f} pts en faveur de la forte "
                   f"rétention sur l'issue principale (seuil +{ECART_SIGNAL:.0f}).")
    else:
        verdict = (f"**Pas de signal** : écart {fmt(principal['ecart'], ' pts')} sur l'issue principale, "
                   f"sous le seuil de +{ECART_SIGNAL:.0f} pts.")

    L = ["# Test de rétention — résultats", "",
         f"_Calculé le {date.today().isoformat()} selon [protocole.md](protocole.md), figé et committé "
         f"avant ce calcul._", "",
         "Règle : moins de 20 tokens mesurables sur l'issue principale = non concluant ; écart d'au moins "
         "+20 pts en faveur de la forte rétention sur l'issue principale = signal à creuser ; sinon pas "
         "de signal.", "",
         "## Couverture", "",
         "| Étape | Tokens |", "|---|---|",
         f"| Population : hors plancher joints à J+90 | {len(population)} |"]
    for motif, n in sorted(motifs.items(), key=lambda x: -x[1]):
        L.append(f"| … exclus : {motif} | {n} |")
    L.append(f"| Rétention mesurable | **{len(mesurables_retention)}** |")
    for n, nom in ISSUES:
        L.append(f"| … et issue {nom} (J+30 à J+{n}) mesurable | "
                 f"**{resultats[n]['n'] if resultats[n] else 0}** |")

    L += ["", "## Contraste", "",
          "| Issue | n | Médiane de rétention | Forte rétention (n, médiane) | Faible rétention (n, médiane) | Écart |",
          "|---|---|---|---|---|---|"]
    for n, nom in ISSUES:
        r = resultats[n]
        if not r:
            L.append(f"| {nom} (J+30 à J+{n}) | 0 | — | — | — | — |")
            continue
        L.append(f"| {nom} (J+30 à J+{n}) | {r['n']} | {r['mediane_retention']:.0%} "
                 f"| n={r['n_forte']}, {fmt(r['med_forte'])} | n={r['n_faible']}, {fmt(r['med_faible'])} "
                 f"| {fmt(r['ecart'], ' pts')} |")

    L += ["", "## Verdict (issue principale)", "", verdict, "",
          "L'issue secondaire est rapportée mais ne décide pas.", "",
          "## Détail par token", "",
          "| Token | Correspondance | Rétention | J+30 à J+180 | J+30 à J+90 |", "|---|---|---|---|---|"]
    for t in sorted(population, key=lambda t: -(t["retention"] if t["retention"] is not None else -1)):
        retention_txt = f"{t['retention']:.0%}" if t["retention"] is not None else f"— ({t['motif']})"
        L.append(f"| {t['ticker']} | {t['slug_defillama'] or '—'} | {retention_txt} "
                 f"| {fmt(t['issue_180'])} | {fmt(t['issue_90'])} |")

    fichier = DOSSIER / "resultats.md"
    fichier.write_text("\n".join(L) + "\n", encoding="utf-8")
    for n, nom in ISSUES:
        r = resultats[n]
        if r:
            print(f"Issue {nom} : n={r['n']}, forte {fmt(r['med_forte'])} (n={r['n_forte']}), "
                  f"faible {fmt(r['med_faible'])} (n={r['n_faible']}), écart {fmt(r['ecart'], ' pts')}")
    print(f"Verdict : {verdict.replace('**', '')}")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
