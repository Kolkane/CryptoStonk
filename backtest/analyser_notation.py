"""Backtest v0 — étape 4 : notation × performances.

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de
plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4,
pas la détection de problèmes.

Joint les notes rendues (backtest/notes/*.csv, format des sessions) avec
performances.csv, puis contraste par critère : perf médiane J+90 rel. BTC des
tokens favorablement vs défavorablement notés (valeurs intermédiaires hors
contraste), et pareil sur un score composite v0 (+1 favorable / -1 défavorable
par critère, split à la médiane du score).

Étiquette v0 : grille et seuils posés à la main, non validés. Si les notes
viennent d'un passage stratifié, AUCUNE lecture en taux de réussite absolu —
seul l'écart entre groupes compte.

Usage : python backtest/analyser_notation.py
Lit   : backtest/notes/*.csv + backtest/performances.csv
"""

import csv
import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
JOURS_SANS_COTATION_MORT = 14
SEUIL_FLOAT = 15  # % : aligné sur audit/scoring.py (float au lancement >= 15 % favorable)

# critère -> (valeurs favorables, valeurs défavorables) ; le reste est intermédiaire
CRITERES = {
    "produit_live": ({"oui"}, {"non"}),
    "traction_tge": ({"forte", "moyenne"}, {"faible", "nulle"}),
    "fees_vers_token": ({"oui"}, {"non"}),
    "backers": ({"tier1"}, {"aucun"}),
}


def lire_csv(chemin):
    with chemin.open(encoding="utf-8-sig", newline="") as entree:
        return list(csv.DictReader(entree, delimiter=";"))


def valeur_j90(ligne, seuil_mort):
    if ligne.get("rel_btc_j90_pct"):
        return float(ligne["rel_btc_j90_pct"])
    derniere = ligne.get("derniere_cotation") or ""
    if derniere and derniere < seuil_mort:
        cible = (date.fromisoformat(ligne["date_tge"]) + timedelta(days=90)).isoformat()
        if cible > derniere:
            return -100.0
    return None


def classer(note, critere):
    """+1 favorable, -1 défavorable, 0 intermédiaire ou vide."""
    if critere == "float_initial_pct":
        brut = re.sub(r"[%\s]", "", str(note.get(critere) or "")).replace(",", ".")
        try:
            return 1 if float(brut) >= SEUIL_FLOAT else -1
        except ValueError:
            return 0  # vide ou non numérique = inconnu, hors contraste — jamais traité comme 0 %
    valeur = str(note.get(critere) or "").strip().lower()
    favorables, defavorables = CRITERES[critere]
    return 1 if valeur in favorables else -1 if valeur in defavorables else 0


def contraste(paires):
    """paires = [(classe, j90)] -> stats des groupes favorable / défavorable."""
    fav = [v for c, v in paires if c == 1]
    defav = [v for c, v in paires if c == -1]
    if not fav or not defav:
        return None
    return {"n_fav": len(fav), "med_fav": statistics.median(fav),
            "n_defav": len(defav), "med_defav": statistics.median(defav),
            "ecart": statistics.median(fav) - statistics.median(defav)}


def afficher(nom, c):
    if not c:
        print(f"  {nom:<18} contraste impossible (un des deux groupes est vide)")
        return
    print(f"  {nom:<18} favorable {c['med_fav']:+8.1f} % (n={c['n_fav']:>2})   "
          f"défavorable {c['med_defav']:+8.1f} % (n={c['n_defav']:>2})   "
          f"écart {c['ecart']:+.1f} pts")


def main():
    dossier_notes = RACINE / "backtest" / "notes"
    fichiers = sorted(dossier_notes.glob("*.csv")) if dossier_notes.exists() else []
    if not fichiers:
        print("Aucune note — générez les sessions (backtest/preparer_sessions.py), notez via "
              "Claude.ai, collez les réponses dans backtest/notes/<session>.csv")
        return

    par_id = {}
    for fichier in fichiers:
        for note in lire_csv(fichier):
            identifiant = (note.get("id_coingecko") or "").strip()
            if not identifiant:
                print(f"  ! {fichier.name} : ligne sans id_coingecko ignorée")
                continue
            par_id.setdefault(identifiant, []).append((fichier.name, note))

    # un même id noté plusieurs fois : toléré seulement si les notes sont identiques —
    # toute divergence est une erreur à résoudre à la main, jamais silencieusement
    champs_notation = ("produit_live", "traction_tge", "float_initial_pct",
                       "fees_vers_token", "backers", "confiance")

    def normalise(note, champ):
        return str(note.get(champ) or "").strip().lower().replace(",", ".")

    notes, conflits = {}, []
    for identifiant, versions in par_id.items():
        premier_fichier, reference = versions[0]
        for nom_fichier, note in versions[1:]:
            divergents = [c for c in champs_notation
                          if normalise(note, c) != normalise(reference, c)]
            if divergents:
                conflits.append((identifiant, premier_fichier, nom_fichier, divergents))
        notes[identifiant] = reference
    if conflits:
        print("CONFLITS de notation — résolvez à la main avant analyse :")
        for identifiant, f1, f2, divergents in conflits:
            print(f"  {identifiant} : {f1} vs {f2} — divergent sur {', '.join(divergents)}")
        sys.exit(1)

    seuil_mort = (date.today() - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()
    j90 = {}
    for l in lire_csv(RACINE / "backtest" / "performances.csv"):
        v = valeur_j90(l, seuil_mort)
        if v is not None:
            j90[l["id_coingecko"]] = v

    joints = [(identifiant, note) for identifiant, note in notes.items() if identifiant in j90]
    sans_perf = len(notes) - len(joints)
    basses = sum(1 for _, n in joints if str(n.get("confiance") or "").strip().lower() == "basse")

    print(f"Notes : {len(notes)} ({len(fichiers)} fichier(s)) ; jointes à un J+90 mesuré ou "
          f"imputé : {len(joints)}" + (f" ; sans perf : {sans_perf}" if sans_perf else "")
          + f" ; confiance basse : {basses}")
    print("v0 — grille non validée. Passage stratifié => pas de lecture absolue : "
          "seul l'écart favorable/défavorable compte.\n")
    if not joints:
        return

    print("Perf médiane J+90 rel. BTC par critère :")
    criteres = list(CRITERES) + ["float_initial_pct"]
    scores = {}
    for identifiant, note in joints:
        scores[identifiant] = sum(classer(note, c) for c in criteres)
    for critere in criteres:
        paires = [(classer(note, critere), j90[identifiant]) for identifiant, note in joints]
        afficher(critere, contraste(paires))

    valeurs_scores = list(scores.values())
    mediane_score = statistics.median(valeurs_scores)
    paires_composite = [(1 if scores[i] > mediane_score else -1 if scores[i] < mediane_score else 0,
                         j90[i]) for i, _ in joints]
    print(f"\nScore composite v0 (somme ±1 par critère, -5..+5 ; split à la médiane "
          f"= {mediane_score:+.1f}, ex æquo écartés) :")
    afficher("composite", contraste(paires_composite))
    repartition = {}
    for s in valeurs_scores:
        repartition[s] = repartition.get(s, 0) + 1
    print("  répartition des scores : "
          + ", ".join(f"{s:+d}×{n}" for s, n in sorted(repartition.items())))

    if basses:
        hauts = [(1 if scores[i] > mediane_score else -1 if scores[i] < mediane_score else 0, j90[i])
                 for i, n in joints if str(n.get("confiance") or "").strip().lower() != "basse"]
        print(f"\nContrôle sans les {basses} note(s) confiance=basse :")
        afficher("composite", contraste(hauts))


if __name__ == "__main__":
    main()
