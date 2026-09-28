"""Scoring v0 d'un candidat — couche 4.

Grille de lecture chiffrée, PAS une vérité : à backtester sur les ~50 derniers
lancements avant de peser réellement dans la décision (feuille de route).

Usage : python audit/scoring.py audit/candidats/<slug>.yaml
"""

import argparse
import statistics
import sys
from pathlib import Path

import yaml

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

POIDS = {
    "produit": 0.20,
    "traction": 0.20,
    "tokenomics": 0.25,
    "distribution": 0.15,
    "valorisation": 0.10,
    "catalyseurs": 0.10,
}


def score_produit(c):
    return {"oui": 100, "testnet": 50, "non": 0}.get(str(c.get("produit_live") or "non").lower(), 0)


def score_traction(c):
    t = c.get("traction") or {}
    tvl = t.get("tvl_usd") or 0
    base = 90 if tvl >= 100e6 else 70 if tvl >= 20e6 else 50 if tvl >= 5e6 else 30 if tvl > 0 else 0
    if (t.get("revenus_30j_usd") or 0) > 0:
        base = min(100, base + 10)
    return base


def score_tokenomics(c):
    tk = c.get("tokenomics") or {}
    if str(tk.get("token_lance") or "non").lower() == "non":
        return 70  # pas de token : optionnalité points, pas de bagholders — à réévaluer au TGE
    score = 0
    # TODO réforme float (bilan stratifié 2026-09-28, backtest/notes/strat_01-04) :
    # le seuil binaire « >= 15 % favorable » est inversé sur l'échantillon backtest —
    # les 3 gagnants notés (NEST 3,5 %, CLO 12,9 %, UP 14,6 %) sont sous 15 %, et les
    # tokens fantômes à 100 % de float finissent à -95/-100 % vs BTC. Piste : notation
    # en cloche (pénaliser les deux extrêmes : très bas = risque d'unlocks, ~100 % =
    # tout déjà dehors). Décision après le passage complet des sessions.
    if (tk.get("float_lancement_pct") or 0) >= 15:
        score += 40
    if (tk.get("unlocks_12m_pct") if tk.get("unlocks_12m_pct") is not None else 100) <= 20:
        score += 30
    if str(tk.get("capture_valeur") or "").strip().lower() not in ("", "rien", "aucune"):
        score += 30
    return score


def score_distribution(c):
    d = c.get("distribution") or {}
    return (50 if d.get("backers") else 0) + (50 if d.get("ecosysteme") else 0)


def score_valorisation(c):
    fdv = (c.get("tokenomics") or {}).get("fdv_usd")
    fdvs = [x.get("fdv_usd") for x in (c.get("comparables") or []) if x and x.get("fdv_usd")]
    if not fdv or not fdvs:
        return None  # non noté, le poids est redistribué
    ratio = fdv / statistics.median(fdvs)
    return 90 if ratio <= 0.2 else 70 if ratio <= 0.5 else 50 if ratio <= 1 else 30 if ratio <= 2 else 10


def score_catalyseurs(c):
    return min(len(c.get("catalyseurs") or []) * 25, 100)


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("fichier", help="audit/candidats/<slug>.yaml")
    options = analyseur.parse_args()

    candidat = yaml.safe_load(Path(options.fichier).read_text(encoding="utf-8")) or {}
    axes = {
        "produit": score_produit(candidat),
        "traction": score_traction(candidat),
        "tokenomics": score_tokenomics(candidat),
        "distribution": score_distribution(candidat),
        "valorisation": score_valorisation(candidat),
        "catalyseurs": score_catalyseurs(candidat),
    }

    notes = {axe: s for axe, s in axes.items() if s is not None}
    poids_total = sum(POIDS[axe] for axe in notes)
    total = round(sum(s * POIDS[axe] for axe, s in notes.items()) / poids_total, 1)

    print(f"Scoring v0 — {candidat.get('nom') or options.fichier} "
          f"({candidat.get('verticale') or 'verticale ?'})")
    for axe, s in axes.items():
        affiche = "non noté" if s is None else f"{s:>3}/100"
        print(f"  {axe:<13} {affiche}   (poids {POIDS[axe]:.0%})")
    print(f"  {'TOTAL':<13} {total}/100")
    if candidat.get("points_farming") and str(candidat["points_farming"]).lower() != "non":
        print("  Entrée pré-token possible (points) — souvent le meilleur timing.")
    print("Ce que le score ne voit pas : équipe, audits sécurité, régulation, momentum narratif.")


if __name__ == "__main__":
    main()
