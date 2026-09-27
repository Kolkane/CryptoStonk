"""Collecte des forums de gouvernance — couche 2 (partie automatique).

Interroge l'API JSON publique des forums Discourse listés dans config/sources.yaml
et verse les sujets récents dans l'inbox, dédoublonnés via data/problemes/deja_vus.json.

Usage  : python problemes/collecte_forums.py [--jours 7] [--max-sujets 8]
Sortie : problemes/inbox/forums_AAAA-MM-JJ.jsonl
"""

import argparse
import html
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).resolve().parents[1]
ENTETES = {"User-Agent": "CryptoStonk/0.1 (outil interne)"}


def nettoyer(html_brut):
    texte = re.sub(r"<[^>]+>", " ", html_brut)
    return re.sub(r"\s+", " ", html.unescape(texte)).strip()


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--jours", type=int, default=7, help="ancienneté maximale des sujets (défaut 7)")
    analyseur.add_argument("--max-sujets", type=int, default=8, help="sujets retenus par forum (défaut 8)")
    options = analyseur.parse_args()

    forums = yaml.safe_load((RACINE / "config" / "sources.yaml").read_text(encoding="utf-8"))["forums"]
    fichier_vus = RACINE / "data" / "problemes" / "deja_vus.json"
    deja_vus = set(json.loads(fichier_vus.read_text(encoding="utf-8"))) if fichier_vus.exists() else set()
    seuil = datetime.now(timezone.utc) - timedelta(days=options.jours)

    nouveaux = []
    for forum in forums:
        base = forum["url"].rstrip("/")
        try:
            derniers = requests.get(f"{base}/latest.json", headers=ENTETES, timeout=30)
            derniers.raise_for_status()
            sujets = derniers.json()["topic_list"]["topics"]
        except Exception as erreur:
            print(f"  ! {forum['nom']} : {erreur}")
            continue

        retenus = 0
        for sujet in sujets:
            if retenus >= options.max_sujets:
                break
            if sujet.get("pinned"):
                continue
            cree = sujet.get("created_at") or ""
            try:
                if datetime.fromisoformat(cree.replace("Z", "+00:00")) < seuil:
                    continue
            except ValueError:
                continue
            url_sujet = f"{base}/t/{sujet['slug']}/{sujet['id']}"
            if url_sujet in deja_vus:
                continue
            time.sleep(0.7)  # politesse envers les forums
            try:
                detail = requests.get(f"{base}/t/{sujet['id']}.json", headers=ENTETES, timeout=30).json()
                premier = detail["post_stream"]["posts"][0].get("cooked", "")
            except Exception:
                premier = ""
            nouveaux.append({
                "date": cree[:10],
                "source": forum["nom"],
                "verticale": forum.get("verticale", ""),
                "titre": sujet.get("title", ""),
                "texte": nettoyer(premier)[:1500],
                "url": url_sujet,
            })
            deja_vus.add(url_sujet)
            retenus += 1
        print(f"  {forum['nom']} : {retenus} sujet(s) retenu(s)")

    if not nouveaux:
        print("Rien de nouveau.")
        return

    inbox = RACINE / "problemes" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    fichier = inbox / f"forums_{date.today().isoformat()}.jsonl"
    with fichier.open("a", encoding="utf-8") as sortie:
        for element in nouveaux:
            sortie.write(json.dumps(element, ensure_ascii=False) + "\n")

    fichier_vus.parent.mkdir(parents=True, exist_ok=True)
    fichier_vus.write_text(json.dumps(sorted(deja_vus), ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(nouveaux)} sujet(s) ajouté(s) à {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
