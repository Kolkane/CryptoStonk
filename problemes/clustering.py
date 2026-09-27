"""Clustering IA des plaintes — couche 2 (carte vivante des problèmes).

Regroupe les plaintes de l'inbox (captures manuelles .md + collecte forums .jsonl)
en problèmes non résolus, pondérés par fréquence × intensité, via l'API Claude.

Usage  : python problemes/clustering.py [--jours 14] [--dry-run]
         --dry-run : 3 plaintes seulement, carte affichée en console, rien n'est écrit.
Écrit  : data/problemes/carte_AAAA-MM-JJ.json + problemes/carte_problemes.md
Erreurs : reprise avec backoff sur 429/5xx uniquement ; arrêt propre sinon,
jamais de reformulation automatique de la requête.
Identifiants : ANTHROPIC_API_KEY, ou profil « ant auth login » (détecté par le SDK).
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import anthropic

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).resolve().parents[1]
MODELE = "claude-haiku-4-5-20251001"  # snapshot épinglé ; alias : claude-haiku-4-5
TENTATIVES = 4

INSTRUCTIONS = """Tu analyses des plaintes d'utilisateurs de protocoles crypto (perps, options, RWA, bridges, lending, DEX…).
Regroupe-les en problèmes NON RÉSOLUS distincts. Un bon cluster désigne un manque concret
qu'un nouveau protocole pourrait combler, pas une humeur de marché ni un incident ponctuel.
Ignore le spam, le shilling et les demandes de support individuelles.

Réponds UNIQUEMENT avec un objet JSON, sans texte autour, au format :
{"clusters": [{
  "titre": "nom court du problème",
  "verticale": "perps|options|rwa|bridges|lending|dex|lsd_restaking|rendement|infra|autre",
  "description": "2-3 phrases : le manque, qui en souffre, pourquoi les leaders ne le règlent pas",
  "intensite": 1-5,
  "exemples": [numéros des plaintes concernées],
  "solutions_connues": "protocoles qui s'y attaquent déjà, ou « aucune connue »"
}]}
intensite : 5 = douleur bloquante exprimée avec véhémence, 1 = gêne mineure."""


def lire_md(fichier):
    """Un bloc par plainte : « ## source | verticale | date », verticale et date optionnelles."""
    correspondance = re.match(r"\d{4}-\d{2}-\d{2}", fichier.stem)
    date_fichier = correspondance.group(0) if correspondance else ""
    elements, source, verticale, jour, lignes = [], None, "", date_fichier, []

    def clore():
        if source and lignes:
            elements.append({"date": jour, "source": source, "verticale": verticale,
                             "texte": " ".join(lignes).strip(), "url": ""})

    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("## "):
            clore()
            parties = [p.strip() for p in ligne[3:].split("|")]
            source = parties[0] if parties and parties[0] else "inconnu"
            verticale = parties[1] if len(parties) > 1 else ""
            jour = parties[2] if len(parties) > 2 else date_fichier
            lignes = []
        elif source is not None and ligne.strip():
            lignes.append(ligne.strip())
    clore()
    return elements


def lire_jsonl(fichier):
    elements = []
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        brut = json.loads(ligne)
        texte = brut.get("texte", "")
        if brut.get("titre"):
            texte = f"{brut['titre']} — {texte}"
        elements.append({"date": brut.get("date", ""), "source": brut.get("source", ""),
                         "verticale": brut.get("verticale", ""), "texte": texte.strip(),
                         "url": brut.get("url", "")})
    return elements


def charger_inbox(jours):
    inbox = RACINE / "problemes" / "inbox"
    seuil = (date.today() - timedelta(days=jours)).isoformat()
    elements = []
    for fichier in sorted(inbox.glob("*.md")) + sorted(inbox.glob("*.jsonl")):
        if fichier.name.startswith("_"):
            continue
        elements += lire_md(fichier) if fichier.suffix == ".md" else lire_jsonl(fichier)
    # date vide = non datée, on garde ; les plaintes trop vieilles sortent de la fenêtre
    elements = [e for e in elements if e["texte"] and (not e["date"] or e["date"] >= seuil)]
    return elements[-150:]  # borne le coût d'appel


def appeler_avec_reprise(client, **parametres):
    """Reprise avec backoff sur 429/5xx uniquement ; toute autre erreur remonte telle quelle."""
    derniere = None
    for tentative in range(TENTATIVES):
        try:
            return client.messages.create(**parametres)
        except anthropic.RateLimitError as erreur:
            derniere = erreur
        except anthropic.APIStatusError as erreur:
            if erreur.status_code < 500:  # 4xx hors 429 : réessayer ne changera rien
                raise
            derniere = erreur  # 500/529 : surcharge, on retente
        if tentative < TENTATIVES - 1:
            attente = min(2 ** tentative * 2 + random.uniform(0, 1), 30)
            print(f"  API saturée ({type(derniere).__name__}), nouvel essai dans "
                  f"{attente:.0f} s ({tentative + 2}/{TENTATIVES})")
            time.sleep(attente)
    raise derniere


def extraire_json(texte):
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut == -1 or fin <= debut:
        raise ValueError("pas de JSON dans la réponse")
    return json.loads(texte[debut:fin + 1])


def construire_md(clusters, nb_plaintes, jours, note_detail):
    aujourdhui = date.today().isoformat()
    lignes = ["# Carte des problèmes non résolus", "",
              f"_Générée le {aujourdhui} — fenêtre {jours} j — {nb_plaintes} plaintes — "
              f"{len(clusters)} problèmes. Poids = fréquence × intensité._", ""]
    verticales = []
    for c in clusters:
        if c["verticale"] not in verticales:
            verticales.append(c["verticale"])
    for verticale in verticales:
        lignes.append(f"## {verticale}")
        lignes.append("")
        for c in (c for c in clusters if c["verticale"] == verticale):
            lignes.append(f"### {c['titre']} — poids {c['poids']} "
                          f"(fréquence {c['frequence']} × intensité {c['intensite']})")
            lignes.append(c["description"])
            lignes.append(f"*Solutions connues : {c['solutions_connues']}*")
            refs = ", ".join(f"n° {n}" for n in c["exemples"][:8])
            lignes.append(f"*Plaintes : {refs} ({note_detail})*")
            lignes.append("")
    return "\n".join(lignes)


def ecrire_carte(clusters, elements, jours):
    aujourdhui = date.today().isoformat()
    dossier = RACINE / "data" / "problemes"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier_json = dossier / f"carte_{aujourdhui}.json"
    fichier_json.write_text(json.dumps(
        {"date": aujourdhui, "fenetre_jours": jours, "clusters": clusters,
         "plaintes": [{**e, "texte": e["texte"][:300]} for e in elements]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    fichier_md = RACINE / "problemes" / "carte_problemes.md"
    fichier_md.write_text(
        construire_md(clusters, len(elements), jours,
                      f"détail dans data/problemes/carte_{aujourdhui}.json"),
        encoding="utf-8")
    return fichier_json, fichier_md


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--jours", type=int, default=14, help="fenêtre d'analyse (défaut 14)")
    analyseur.add_argument("--dry-run", action="store_true",
                           help="3 plaintes, carte en console, rien n'est écrit")
    options = analyseur.parse_args()

    elements = charger_inbox(options.jours)
    if not elements:
        print("Inbox vide sur la fenêtre : lancez collecte_forums.py ou collez des captures "
              "dans problemes/inbox/AAAA-MM-JJ.md")
        return
    if options.dry_run:
        elements = elements[-3:]

    corpus = "\n\n".join(
        f"[{i}] ({e['source']}, {e['verticale'] or '?'}, {e['date'] or '?'}) {e['texte'][:600]}"
        for i, e in enumerate(elements, 1))

    try:
        client = anthropic.Anthropic(max_retries=0)  # la reprise est gérée ici, pas par le SDK
        reponse = appeler_avec_reprise(
            client,
            model=MODELE,
            max_tokens=16000,
            system=INSTRUCTIONS,
            messages=[{"role": "user", "content":
                       f"Plaintes des {options.jours} derniers jours :\n\n{corpus}"}],
        )
    except anthropic.AuthenticationError:
        print("Identifiants absents ou invalides : setx ANTHROPIC_API_KEY \"sk-ant-…\" "
              "(puis rouvrir le terminal), ou « ant auth login ».")
        sys.exit(1)
    except TypeError as erreur:
        # SDK sans identifiants : « Could not resolve authentication method »
        if "authentication method" not in str(erreur):
            raise
        print("Aucun identifiant trouvé : setx ANTHROPIC_API_KEY \"sk-ant-…\" "
              "(puis rouvrir le terminal), ou « ant auth login ».")
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("Pas de réseau vers l'API Claude.")
        sys.exit(1)
    except anthropic.AnthropicError as erreur:
        print(f"Erreur API, pas de reprise possible : {erreur}")
        sys.exit(1)

    if reponse.stop_reason == "refusal":
        print("Requête refusée par l'API (stop_reason=refusal) — pas de reformulation "
              "automatique, à examiner à la main.")
        sys.exit(1)

    texte = "".join(bloc.text for bloc in reponse.content if bloc.type == "text")
    try:
        brut = extraire_json(texte)
    except (ValueError, json.JSONDecodeError):
        if options.dry_run:
            print("Réponse non parsable (dry-run, rien n'est écrit) :\n" + texte)
            sys.exit(1)
        secours = RACINE / "data" / "problemes" / "reponse_brute.txt"
        secours.parent.mkdir(parents=True, exist_ok=True)
        secours.write_text(texte, encoding="utf-8")
        print(f"Réponse non parsable, sauvegardée dans {secours.relative_to(RACINE)}")
        sys.exit(1)

    clusters = []
    for c in brut.get("clusters", []):
        exemples = [n for n in c.get("exemples", []) if isinstance(n, int) and 1 <= n <= len(elements)]
        intensite = min(5, max(1, int(c.get("intensite", 1))))
        clusters.append({
            "titre": c.get("titre", "sans titre"),
            "verticale": c.get("verticale", "autre"),
            "description": c.get("description", ""),
            "intensite": intensite,
            "frequence": len(exemples),
            "poids": len(exemples) * intensite,
            "exemples": exemples,
            "solutions_connues": c.get("solutions_connues", ""),
        })
    clusters.sort(key=lambda c: -c["poids"])

    entree, sortie = reponse.usage.input_tokens, reponse.usage.output_tokens
    if options.dry_run:
        print("— dry-run : rien n'est écrit —\n")
        print(construire_md(clusters, len(elements), options.jours, "dry-run"))
        print(f"\n[dry-run] {len(elements)} plaintes -> {len(clusters)} problèmes "
              f"({entree} tokens entrée / {sortie} sortie, modèle {MODELE})")
        return

    fichier_json, fichier_md = ecrire_carte(clusters, elements, options.jours)
    print(f"{len(elements)} plaintes -> {len(clusters)} problèmes "
          f"({entree} tokens entrée / {sortie} sortie, modèle {MODELE})")
    for c in clusters[:8]:
        print(f"  [{c['verticale']:<13}] poids {c['poids']:>3}  {c['titre']}")
    print(f"Écrit : {fichier_md.relative_to(RACINE)} et {fichier_json.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
