"""Veille des nouveaux protocoles — couche 3 (v0 : listings DefiLlama).

Croise les protocoles récemment listés avec nos verticales (config/verticals.yaml).
Les protocoles sans token sont marqués : candidats farming de points / entrée pré-TGE.

Usage  : python veille/nouveaux_projets.py [--jours 14] [--tvl-min 0]
Sortie : data/veille/nouveaux_AAAA-MM-JJ.csv + résumé console.
"""

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

import requests
import yaml

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).resolve().parents[1]
ENTETES = {"User-Agent": "CryptoStonk/0.1 (outil interne)"}


def correspondance_verticales():
    brut = yaml.safe_load((RACINE / "config" / "verticals.yaml").read_text(encoding="utf-8"))
    return {categorie.lower(): verticale for verticale, categories in brut.items() for categorie in categories}


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--jours", type=int, default=14, help="fenêtre de listing (défaut 14)")
    analyseur.add_argument("--tvl-min", type=float, default=0, help="TVL minimale en USD (défaut 0)")
    options = analyseur.parse_args()

    verticales = correspondance_verticales()
    reponse = requests.get("https://api.llama.fi/protocols", headers=ENTETES, timeout=120)
    reponse.raise_for_status()
    protocoles = reponse.json()
    seuil = time.time() - options.jours * 86400

    lignes = []
    for p in protocoles:
        liste_le = p.get("listedAt")
        if not liste_le or liste_le < seuil:
            continue
        tvl = p.get("tvl") or 0
        if tvl < options.tvl_min:
            continue
        symbole = (p.get("symbol") or "-").strip()
        lignes.append({
            "nom": p.get("name", ""),
            "verticale": verticales.get((p.get("category") or "").lower(), "autre"),
            "categorie": p.get("category", ""),
            "chaines": " / ".join((p.get("chains") or [])[:3]),
            "tvl_usd": round(tvl),
            "token": "aucun (pré-TGE ?)" if symbole in ("-", "") else symbole,
            "liste_le": date.fromtimestamp(liste_le).isoformat(),
            "site": p.get("url") or "",
            "twitter": p.get("twitter") or "",
        })

    suivies = sorted((l for l in lignes if l["verticale"] != "autre"), key=lambda l: -l["tvl_usd"])
    autres = sorted((l for l in lignes if l["verticale"] == "autre"), key=lambda l: -l["tvl_usd"])
    lignes = suivies + autres

    dossier = RACINE / "data" / "veille"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"nouveaux_{date.today().isoformat()}.csv"
    with fichier.open("w", encoding="utf-8-sig", newline="") as sortie:
        colonnes = ["nom", "verticale", "categorie", "chaines", "tvl_usd", "token", "liste_le", "site", "twitter"]
        redacteur = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";")
        redacteur.writeheader()
        redacteur.writerows(lignes)

    print(f"Nouveaux protocoles DefiLlama sur {options.jours} j : {len(lignes)} "
          f"(dont {len(suivies)} sur nos verticales)")
    for l in lignes[:15]:
        tvl = f"{l['tvl_usd']:,}".replace(",", " ")
        print(f"  {l['liste_le']}  {l['nom']:<28} {l['verticale']:<14} TVL {tvl:>13} $  {l['token']}")
    if len(lignes) > 15:
        print(f"  … et {len(lignes) - 15} autres dans le CSV")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
