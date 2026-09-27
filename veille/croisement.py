"""Croisement couche 2 × couche 3 — candidats : nouveaux protocoles × carte des problèmes.

Matching v0 purement local, sans LLM — HEURISTIQUE NON BACKTESTÉE, présélection,
pas un verdict : même verticale + recouvrement de mots-clés (minuscules, stopwords
FR/EN) entre le texte du protocole (nom, catégorie, description du CSV de veille)
et le contenu du cluster (titre + description de carte_problemes.md).
Force : fort = verticale + ≥ 2 mots-clés communs, moyen = + 1, faible = verticale seule.

Usage  : python veille/croisement.py [--csv data/veille/nouveaux_….csv]
         python veille/croisement.py --export-prompt   # affinage hebdo via Claude.ai
Sortie : veille/correspondances.csv (versionné).
         --export-prompt génère en plus veille/prompt_croisement.txt (hors dépôt) :
         Claude.ai confirme/infirme chaque correspondance forte ou moyenne, réponse
         à coller dans veille/correspondances_affinees.csv (hors dépôt).
"""

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).resolve().parents[1]
ETIQUETTE_METHODE = "v0 heuristique non backtestée"
RANG_FORCE = {"fort": 0, "moyen": 1, "faible": 2}

STOPWORDS = frozenset("""
le la les un une des du de au aux et ou où mais donc car ni ne pas plus moins très peu
sur sous dans par pour avec sans chez vers entre est sont être avoir fait faire qui que
quoi dont il elle ils elles nous vous tout tous toute toutes autre autres même aussi
comme quand alors ainsi encore déjà cela celui celle ceux celles leur leurs son ses
cette ces notre votre nos vos peut peuvent doit doivent via
the for with without and not are was were been being have has had this that these those
its they them their there here from which who whose what when where why how can could
may might must shall should will would more most less least very much many some any all
each other another same also just only over under between into out off than then such
protocol protocols protocole protocoles defi crypto cryptos blockchain chain chains
onchain token tokens tokenomics platform platforms plateforme plateformes finance
financial app application apps market markets marché marchés user users utilisateur
utilisateurs solution solutions connues aucune connue plainte plaintes export problème
problèmes poids fréquence intensité verticale decentralized decentralised permet
permettant offre propose based built launch launched launching enables allows provides
providing service services network project projects produit product products asset assets
""".split())


def mots_cles(texte):
    brut = re.findall(r"[a-zà-öø-ÿ0-9]{3,}", texte.lower())
    return {m for m in brut if m not in STOPWORDS and not m.isdigit()}


def lire_carte(fichier):
    """Clusters de carte_problemes.md : verticale, titre, poids, contenu (titre + description)."""
    clusters, verticale, courant = [], "?", None
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("### "):
            m = re.match(r"###\s+(.+?)\s+[—-]\s+poids\s+(\d+)\s*\(fréquence\s+(\d+)\s*[×x]\s*intensité\s+(\d+)\)",
                         ligne)
            courant = None
            if m:
                courant = {"titre": m.group(1), "poids": int(m.group(2)),
                           "verticale": verticale, "contenu": m.group(1)}
                clusters.append(courant)
        elif ligne.startswith("## "):
            verticale = ligne[3:].strip()
            courant = None
        elif courant is not None and ligne.strip() and not ligne.startswith("#"):
            courant["contenu"] += " " + ligne.strip()
    return clusters


def dernier_csv_veille():
    fichiers = sorted((RACINE / "data" / "veille").glob("nouveaux_*.csv"))
    return fichiers[-1] if fichiers else None


def lire_veille(fichier):
    with fichier.open(encoding="utf-8-sig", newline="") as entree:
        lecteur = csv.DictReader(entree, delimiter=";")
        if lecteur.fieldnames and "description" not in lecteur.fieldnames:
            print("  ! CSV sans colonne description (ancien format) — matching sur nom + "
                  "catégorie seulement ; relancez veille/nouveaux_projets.py")
        return list(lecteur)


def croiser(protocoles, clusters):
    lignes = []
    for p in protocoles:
        if p["verticale"] == "autre":
            continue  # la porte d'entrée du matching est la verticale : « autre » ne dit rien
        texte_p = mots_cles(f"{p['nom']} {p['categorie']} {p.get('description') or ''}")
        for c in clusters:
            if c["verticale"] != p["verticale"]:
                continue
            communs = sorted(texte_p & mots_cles(c["contenu"]))
            force = "fort" if len(communs) >= 2 else "moyen" if len(communs) == 1 else "faible"
            lignes.append({
                "protocole": p["nom"],
                "verticale": p["verticale"],
                "probleme_adresse": c["titre"],
                "force": force,
                "poids_probleme": c["poids"],
                "pre_tge": "oui" if (p.get("token") or "").startswith("aucun") else "non",
                "mots_communs": " ".join(communs),
                "tvl_usd": int(float(p.get("tvl_usd") or 0)),
                "methode": ETIQUETTE_METHODE,
            })
    lignes.sort(key=lambda l: (RANG_FORCE[l["force"]], l["pre_tge"] != "oui",
                               -l["poids_probleme"], -l["tvl_usd"]))
    return lignes


def ecrire_correspondances(lignes):
    fichier = RACINE / "veille" / "correspondances.csv"
    colonnes = ["protocole", "verticale", "probleme_adresse", "force", "poids_probleme",
                "pre_tge", "mots_communs", "tvl_usd", "methode"]
    with fichier.open("w", encoding="utf-8-sig", newline="") as sortie:
        redacteur = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";")
        redacteur.writeheader()
        redacteur.writerows(lignes)
    return fichier


def exporter_prompt(lignes, clusters, protocoles):
    """Prompt autoporteur pour Claude.ai : vérifier chaque correspondance forte ou moyenne."""
    retenues = [l for l in lignes if l["force"] in ("fort", "moyen")]
    if not retenues:
        print("Aucune correspondance forte ou moyenne à affiner.")
        return None
    contenu_cluster = {(c["verticale"], c["titre"]): c["contenu"] for c in clusters}
    detail_protocole = {p["nom"]: p for p in protocoles}

    blocs = []
    for i, l in enumerate(retenues, 1):
        p = detail_protocole.get(l["protocole"], {})
        blocs.append(
            f"[{i}] PROTOCOLE : {l['protocole']} ({l['verticale']}, TVL {l['tvl_usd']} $, "
            f"token : {p.get('token', '?')})\n"
            f"    Description : {p.get('description') or '(absente)'}\n"
            f"    PROBLÈME : {l['probleme_adresse']} (poids {l['poids_probleme']})\n"
            f"    Contexte du problème : {contenu_cluster.get((l['verticale'], l['probleme_adresse']), '')[:400]}\n"
            f"    Force locale : {l['force']} (mots communs : {l['mots_communs'] or 'aucun'})")

    prompt = f"""Tu vérifies des correspondances entre de NOUVEAUX protocoles crypto et des PROBLÈMES
utilisateurs non résolus. Chaque couple a été proposé par une heuristique locale v0
(même verticale + mots-clés communs), non backtestée : ton rôle est de juger sur le fond,
uniquement à partir des textes fournis. Critère : le protocole adresse-t-il réellement
CE problème (pas seulement la même verticale ou le même vocabulaire) ?

Réponds UNIQUEMENT avec un CSV séparé par des points-virgules, en-tête compris, une ligne
par couple et dans le même ordre, collable tel quel dans veille/correspondances_affinees.csv :

protocole;probleme_adresse;force_locale;verdict;justification

verdict : confirme | infirme | incertain. justification : une phrase, entre guillemets.

Couples à vérifier ({date.today().isoformat()}) :

{chr(10).join(blocs)}
"""
    fichier = RACINE / "veille" / "prompt_croisement.txt"
    fichier.write_text(prompt, encoding="utf-8")
    return fichier


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--csv", help="CSV de veille (défaut : dernier data/veille/nouveaux_*.csv)")
    analyseur.add_argument("--export-prompt", action="store_true",
                           help="génère veille/prompt_croisement.txt pour affiner via Claude.ai")
    options = analyseur.parse_args()

    carte = RACINE / "problemes" / "carte_problemes.md"
    if not carte.exists():
        print("Aucune carte des problèmes — lancez d'abord le clustering hebdo "
              "(problemes/clustering.py --export-prompt, puis coller la carte).")
        return
    clusters = lire_carte(carte)
    if not clusters:
        print("Carte présente mais aucun cluster lisible (format « ### titre — poids … »).")
        return

    fichier_veille = Path(options.csv) if options.csv else dernier_csv_veille()
    if not fichier_veille or not fichier_veille.exists():
        print("Aucun CSV de veille — lancez d'abord veille/nouveaux_projets.py")
        return
    protocoles = lire_veille(fichier_veille)

    lignes = croiser(protocoles, clusters)
    fichier = ecrire_correspondances(lignes)

    compte = {f: sum(1 for l in lignes if l["force"] == f) for f in ("fort", "moyen", "faible")}
    print(f"{len(protocoles)} protocoles × {len(clusters)} problèmes -> {len(lignes)} correspondances "
          f"(fort {compte['fort']}, moyen {compte['moyen']}, faible {compte['faible']}) — {ETIQUETTE_METHODE}")
    for l in [l for l in lignes if l["force"] in ("fort", "moyen")][:10]:
        marque = "pré-TGE" if l["pre_tge"] == "oui" else "token"
        print(f"  [{l['force']:<5}] {l['protocole']:<24} -> {l['probleme_adresse'][:44]:<44} "
              f"poids {l['poids_probleme']:>3}  {marque}")
    print(f"Écrit : {fichier.relative_to(RACINE)}")

    if options.export_prompt:
        fichier_prompt = exporter_prompt(lignes, clusters, protocoles)
        if fichier_prompt:
            print(f"Prompt d'affinage -> {fichier_prompt.relative_to(RACINE)}")
            print("À coller dans Claude.ai ; la réponse se colle telle quelle dans "
                  "veille/correspondances_affinees.csv")


if __name__ == "__main__":
    main()
