"""Backtest v0 — étape 3 : préparer les sessions de notation (anti-hindsight).

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de
plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4,
pas la détection de problèmes.

Garde-fous méthodo :
- AUCUNE performance dans les prompts : uniquement id_coingecko (identifiant,
  nécessaire à la jointure des notes — deux tickers identiques existent),
  ticker, nom, date de TGE et catégorie. Les performances restent dans
  performances.csv et n'entrent JAMAIS dans une session.
- Ordre aléatoire à graine fixe (GRAINE), lots de 10, reproductibles.
- --stratifie : 40 tokens (10 meilleurs J+90 rel. BTC, 10 pires — morts imputés
  à -100 % compris —, 20 tirés au sort dans le reste), REMÉLANGÉS avant découpe
  pour qu'aucune session ne trahisse son groupe d'origine. La stratification
  INTERDIT toute lecture en taux de réussite absolu : elle mesure uniquement la
  capacité de la grille à discriminer bons et mauvais lancements.

Usage  : python backtest/preparer_sessions.py [--stratifie] [--taille 10]
Sortie : backtest/sessions/session_NN.txt (ou strat_NN.txt) — un prompt par
         session, à coller dans Claude.ai ; la réponse CSV se colle dans
         backtest/notes/<même nom>.csv
"""

import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
GRAINE = 20260927  # fixe : sessions reproductibles tant que l'échantillon ne change pas
JOURS_SANS_COTATION_MORT = 14

# Garder la grille alignée avec backtest/notation_retroactive.md
CONSIGNES = """Tu notes des tokens crypto À LA DATE DE LEUR TGE, pour un backtest. Règle absolue
(anti-rétrospective) : note l'état du projet AU MOMENT du TGE, uniquement à partir de
sources d'époque (annonces X du projet, articles de listing, docs versionnées, TVL
DefiLlama à la date, levées annoncées avant TGE). NE CHERCHE JAMAIS le prix, la
performance, le market cap ni le destin ultérieur du token ; si tu tombes dessus,
ignore-les. Un fait d'époque incertain -> confiance=basse, et dis pourquoi dans sources.

Grille (état au TGE) :
- produit_live : oui | testnet | non — produit utilisable en mainnet avant le token ?
- traction_tge : forte | moyenne | faible | nulle — TVL/volume/utilisateurs AVANT le
  TGE ; farming de points sans usage réel = faible.
- float_initial_pct : nombre — % du supply en circulation au listing.
- fees_vers_token : oui | partiel | non — capture de valeur (frais, burn, droits)
  active ou annoncée de façon engageante au TGE.
- backers : tier1 | tier2 | aucun — investisseurs annoncés avant TGE (tier1 = fonds
  majeurs, exchange, écosystème puissant).
- confiance : haute | basse — basse si les sources d'époque manquent ou se contredisent.

Réponds UNIQUEMENT en CSV point-virgule, en-tête compris, une ligne par token :
id_coingecko;ticker;produit_live;traction_tge;float_initial_pct;fees_vers_token;backers;confiance;sources"""


def lire_csv(chemin):
    with chemin.open(encoding="utf-8-sig", newline="") as entree:
        return list(csv.DictReader(entree, delimiter=";"))


def valeur_j90(ligne, seuil_mort):
    """J+90 rel. BTC mesuré, sinon -100 % si le token est mort avant sa fenêtre."""
    if ligne.get("rel_btc_j90_pct"):
        return float(ligne["rel_btc_j90_pct"])
    derniere = ligne.get("derniere_cotation") or ""
    if derniere and derniere < seuil_mort:
        cible = (date.fromisoformat(ligne["date_tge"]) + timedelta(days=90)).isoformat()
        if cible > derniere:
            return -100.0
    return None


def selection_stratifiee(echantillon, rng):
    """10 meilleurs + 10 pires J+90 rel. BTC (morts imputés compris) + 20 au sort."""
    perfs = lire_csv(RACINE / "backtest" / "performances.csv")
    seuil_mort = (date.today() - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()
    valeurs = {}
    for l in perfs:
        v = valeur_j90(l, seuil_mort)
        if v is not None:
            valeurs[l["id_coingecko"]] = v
    classes = sorted(valeurs, key=valeurs.get)
    pires, meilleurs = classes[:10], classes[-10:]
    reste = [i for i in classes[10:-10]]
    tirage = rng.sample(reste, min(20, len(reste)))
    ids = set(pires + meilleurs + tirage)
    retenus = [t for t in echantillon if t["id_coingecko"] in ids]
    if len(retenus) < 40:
        print(f"  ! seulement {len(retenus)} tokens stratifiables (J+90 mesuré ou imputé)")
    return retenus


def ecrire_sessions(tokens, prefixe, taille):
    dossier = RACINE / "backtest" / "sessions"
    dossier.mkdir(parents=True, exist_ok=True)
    for perime in dossier.glob(f"{prefixe}_*.txt"):
        perime.unlink()
    fichiers = []
    for rang, debut in enumerate(range(0, len(tokens), taille), 1):
        lot = tokens[debut:debut + taille]
        lignes = [f"{t['id_coingecko']} | {t['ticker']} | {t['nom']} | TGE {t['date_tge']} "
                  f"| {t['verticale']} ({t['categorie_cg']})" for t in lot]
        contenu = (CONSIGNES + "\n\nTokens à noter (id_coingecko | ticker | nom | TGE | catégorie) :\n\n"
                   + "\n".join(lignes) + "\n")
        fichier = dossier / f"{prefixe}_{rang:02d}.txt"
        fichier.write_text(contenu, encoding="utf-8")
        fichiers.append(fichier)
    return fichiers


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--stratifie", action="store_true",
                           help="40 tokens (10 meilleurs, 10 pires, 20 au sort) en 4 sessions")
    analyseur.add_argument("--taille", type=int, default=10, help="tokens par session (défaut 10)")
    options = analyseur.parse_args()

    echantillon = lire_csv(RACINE / "backtest" / "echantillon.csv")
    rng = random.Random(GRAINE)

    if options.stratifie:
        tokens = selection_stratifiee(echantillon, rng)
        prefixe = "strat"
    else:
        tokens = list(echantillon)
        prefixe = "session"
    rng.shuffle(tokens)  # aussi après stratification : aucune session ne trahit son groupe

    fichiers = ecrire_sessions(tokens, prefixe, options.taille)
    print(f"{len(tokens)} tokens -> {len(fichiers)} session(s) : "
          f"{fichiers[0].relative_to(RACINE)} … {fichiers[-1].relative_to(RACINE)}")
    print("Aucune performance dans les prompts ; réponses à coller dans "
          f"backtest/notes/{prefixe}_NN.csv")
    if options.stratifie:
        print("Rappel : passage stratifié — AUCUNE lecture en taux de réussite absolu, "
              "seule la discrimination de la grille se mesure.")


if __name__ == "__main__":
    main()
