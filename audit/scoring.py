"""Scoring v1 d'un candidat — couche 4 (la v0 pondérée reste dans l'historique git).

v1 : filtre validé sur backtest (87 TGE oct 2025-juin 2026) ; indices
float/traction non validés comme classeur. Détail : backtest/bilan_passage_complet.md.

Étape 1, filtre d'exclusion : exclu si produit_live=non ET traction_tge=nulle
ET backers=aucun (profil plancher : 44 % de quasi-zéros à J+90 contre 8 % au-dessus).
Étape 2, indices — pas un score de classement :
- float_initial_pct >= 50 : malus ; 20-50 : malus léger ; < 20 : neutre (pas de
  bonus pour le float bas : pente monotone, tranche < 10 % trop petite) ;
- traction_tge forte ou moyenne : bonus (seul critère positif au-dessus du
  plancher à J+90 et J+180, signal modeste) ;
- capture_valeur et backers : affichés, poids 0 (signal instable ou nul).

Champs : même vocabulaire que les notes du backtest (produit_live, traction_tge,
backers, float_initial_pct) ; float_lancement_pct accepté en alias de lecture.

Usage : python audit/scoring.py audit/candidats/<slug>.yaml
        python audit/scoring.py --controle-backtest
"""

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
ETIQUETTE_V1 = ("v1 : filtre validé sur backtest (87 TGE oct 2025-juin 2026) ; "
                "indices float/traction non validés comme classeur")


def valeur(c, champ):
    return str(c.get(champ) or "").strip().lower()


def lire_float(c):
    """float_initial_pct, au premier niveau ou sous tokenomics ; alias float_lancement_pct."""
    tokenomics = c.get("tokenomics") or {}
    for source, champ in ((c, "float_initial_pct"), (tokenomics, "float_initial_pct"),
                          (c, "float_lancement_pct"), (tokenomics, "float_lancement_pct")):
        brut = re.sub(r"[%\s]", "", str(source.get(champ) or "")).replace(",", ".")
        try:
            return float(brut)
        except ValueError:
            continue
    return None


def lire_backers(c):
    """Tier des backers ; une liste de noms (ancien gabarit) vide vaut « aucun »."""
    brut = c.get("backers")
    if isinstance(brut, list):
        return "aucun" if not brut else "non classé"
    return valeur(c, "backers")


def filtre(c):
    """(statut, détail) avec statut exclu | retenu | incomplet."""
    champs = {"produit_live": valeur(c, "produit_live"),
              "traction_tge": valeur(c, "traction_tge"),
              "backers": lire_backers(c)}
    manquants = [k for k, v in champs.items() if not v]
    detail = ", ".join(f"{k}={v or '?'}" for k, v in champs.items())
    if champs["produit_live"] == "non" and champs["traction_tge"] == "nulle" \
            and champs["backers"] == "aucun":
        return "exclu", detail
    if manquants:
        return "incomplet", f"{detail} — renseigner {', '.join(manquants)}"
    return "retenu", detail


def indices(c):
    """[(libellé, signal)] ; signal : bonus | neutre | malus léger | malus | inconnu."""
    f = lire_float(c)
    if f is None:
        signal_float = "inconnu"
    elif f >= 50:
        signal_float = "malus"
    elif f >= 20:
        signal_float = "malus léger"
    else:
        signal_float = "neutre"
    traction = valeur(c, "traction_tge")
    signal_traction = ("bonus" if traction in ("forte", "moyenne")
                       else "neutre" if traction else "inconnu")
    return [(f"float initial {f:g} %" if f is not None else "float initial ?", signal_float),
            (f"traction {traction or '?'}", signal_traction)]


def affiches(c):
    """Informations montrées sans poids."""
    capture = (c.get("tokenomics") or {}).get("capture_valeur") or c.get("fees_vers_token")
    return [("capture de valeur", str(capture or "?")), ("backers", lire_backers(c) or "?")]


def evaluer(c):
    statut, detail = filtre(c)
    return {"filtre": statut, "detail": detail, "indices": indices(c), "affiches": affiches(c)}


def controle_backtest():
    """Le filtre doit exclure exactement les profils plancher des jointes J+90 du bilan."""
    sys.path.insert(0, str(RACINE / "backtest"))
    from analyser_notation import est_fantome, lire_csv
    from bilan_passage import JOURS_SANS_COTATION_MORT, charger_notes, valeur_jn

    seuil_mort = (date.today() - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()
    notes = charger_notes()
    joints = []
    for ligne in lire_csv(RACINE / "backtest" / "performances.csv"):
        identifiant = ligne["id_coingecko"]
        derniere = ligne.get("derniere_cotation") or ""
        v, _ = valeur_jn(ligne, 90, bool(derniere) and derniere < seuil_mort)
        if identifiant in notes and v is not None:
            joints.append(identifiant)
    exclus = {i for i in joints if filtre(notes[i])[0] == "exclu"}
    plancher = {i for i in joints if est_fantome(notes[i])}
    identique = exclus == plancher
    print(f"Contrôle backtest : {len(joints)} jointes J+90 ; filtre v1 exclut {len(exclus)} ; "
          f"profils plancher du bilan : {len(plancher)} ; ensembles identiques : "
          f"{'oui' if identique else 'NON'}")
    if not identique:
        print(f"  en trop : {sorted(exclus - plancher)} ; manquants : {sorted(plancher - exclus)}")
        sys.exit(1)


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("fichier", nargs="?", help="audit/candidats/<slug>.yaml")
    analyseur.add_argument("--controle-backtest", action="store_true",
                           help="vérifie le filtre sur les notes jointes du backtest")
    options = analyseur.parse_args()

    if options.controle_backtest:
        controle_backtest()
        return
    if not options.fichier:
        analyseur.error("fichier candidat requis (ou --controle-backtest)")

    candidat = yaml.safe_load(Path(options.fichier).read_text(encoding="utf-8")) or {}
    resultat = evaluer(candidat)
    print(f"Scoring v1 — {candidat.get('nom') or options.fichier} "
          f"({candidat.get('verticale') or 'verticale ?'})")
    print(f"  {ETIQUETTE_V1}")
    print(f"  Étape 1, filtre d'exclusion : {resultat['filtre'].upper()} ({resultat['detail']})")
    print("  Étape 2, indices (pas un score de classement) :")
    for libelle, signal in resultat["indices"]:
        print(f"    {libelle:<22} {signal}")
    for libelle, texte in resultat["affiches"]:
        print(f"    {libelle:<22} {texte}  (affiché, poids 0)")
    print("Ce que la grille ne voit pas : équipe, audits sécurité, régulation, momentum narratif.")


if __name__ == "__main__":
    main()
