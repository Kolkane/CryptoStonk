"""Backtest farming — préparation : candidats, couverture DefiLlama, sessions de notation.

Protocole figé dans backtest/farming/protocole.md, avant toute mesure. Ce script ne
calcule aucun résultat : il liste les candidats, vérifie ce que DefiLlama couvre
et génère les sessions de notation farming (aucune performance affichée).

Candidats : tokens hors plancher joints à J+90 dont le champ sources des notes
mentionne points, airdrop, saison, season, farming, kPoints, Bricks, XP ou
genesis. Le texte complet des sources est reconstitué : il contient des « ; »
que le CSV coupe en colonnes supplémentaires.

Correspondance DefiLlama : d'abord backtest/farming/correspondances.csv
(vérifiées à la main, versionnées), puis gecko_id d'un protocole, d'un protocole
parent ou d'une chaîne. Pas de repli par nom ou symbole : il produisait des
homonymes (Rangers Bridge pour Ranger, CoinCollect pour Fanable…).

Volumes : dexs, aggregators et aggregator-derivatives sont gratuits ; les
volumes perps (derivatives) sont payants chez DefiLlama (HTTP 402). Pour un
protocole perps, seule une série aggregator-derivatives est retenue : sa série
spot gratuite ne mesure pas le volume qui rapportait les points.

Usage  : python backtest/farming/preparer.py
Sortie : backtest/farming/candidats.csv, backtest/farming/sessions/farm_NN.txt
"""

import csv
import random
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "backtest"))
from analyser_notation import est_fantome, lire_csv  # noqa: E402
from bilan_passage import JOURS_SANS_COTATION_MORT, charger_notes, valeur_jn  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DOSSIER = RACINE / "backtest" / "farming"
LLAMA = "https://api.llama.fi"
ENTETES = {"User-Agent": "CryptoStonk/0.1 (outil interne)"}
GRAINE = 20260927
TAILLE_SESSION = 10
MOTS_PROGRAMME = re.compile(
    r"\b(points|airdrops?|saisons?|seasons?|farming|kpoints|bricks|xp|genesis)\b", re.I)
TYPES_VOLUME_GRATUITS = ("dexs", "aggregators", "aggregator-derivatives")
JOURS_COUVERTURE_MIN = 30

CONSIGNES = """Tu documentes le programme de farming (points, saisons, airdrop) de tokens crypto
AVANT leur TGE, pour un backtest. Règle absolue (anti-rétrospective) : ne cherche JAMAIS
le prix, la performance, le market cap ni le destin du token après le TGE ; si tu tombes
dessus, ignore-les. Uniquement des faits sur le programme et sur la distribution au TGE,
tirés de sources d'époque (annonces du projet, docs de tokenomics, articles de TGE).

Champs à renseigner :
- programme_pretge : oui | non — un programme a-t-il récompensé les utilisateurs avant le
  TGE par une allocation de tokens (points, saisons, farming, airdrop d'usage) ?
- debut_programme : date AAAA-MM-JJ du lancement du programme (saison 1, ouverture des
  points) ; vide si inconnu.
- base_eligibilite : tvl | volume | mixte | taches — ce qui rapportait les points :
  dépôts/liquidité (tvl), trading (volume), les deux de façon significative (mixte),
  quêtes/social/testnet sans capital (taches).
- airdrop_pct_farmers : % du supply TOTAL alloué aux participants du programme pré-TGE
  (hors équipe, investisseurs, trésorerie, réserves pour de futures saisons).
- airdrop_unlock_tge_pct : % de cette allocation débloqué au TGE (100 si tout est liquide).
- confiance : haute | basse — basse si une valeur est estimée ou si les sources divergent.
- sources : références d'époque. N'utilise JAMAIS de point-virgule dans ce champ
  (virgules uniquement) : le fichier est séparé par des points-virgules.

Réponds UNIQUEMENT en CSV point-virgule, en-tête compris, une ligne par token :
id_coingecko;ticker;programme_pretge;debut_programme;base_eligibilite;airdrop_pct_farmers;airdrop_unlock_tge_pct;confiance;sources"""


def texte_sources(note):
    return ";".join([note.get("sources") or ""] + [str(x) for x in (note.get(None) or [])])


def jour(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()


def get(chemin, params=None):
    time.sleep(0.3)
    reponse = requests.get(f"{LLAMA}{chemin}", params=params, headers=ENTETES, timeout=120)
    if reponse.status_code != 200:
        return None
    return reponse.json()


def candidats():
    seuil = (date.today() - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()
    notes = charger_notes()
    noms = {l["id_coingecko"]: l for l in lire_csv(RACINE / "backtest" / "echantillon.csv")}
    liste = []
    for ligne in lire_csv(RACINE / "backtest" / "performances.csv"):
        identifiant = ligne["id_coingecko"]
        derniere = ligne.get("derniere_cotation") or ""
        v90, _ = valeur_jn(ligne, 90, bool(derniere) and derniere < seuil)
        if identifiant not in notes or v90 is None or est_fantome(notes[identifiant]):
            continue
        mots = sorted({m.lower() for m in MOTS_PROGRAMME.findall(texte_sources(notes[identifiant]))})
        if mots:
            liste.append({"id_coingecko": identifiant, "ticker": ligne["ticker"],
                          "nom": noms.get(identifiant, {}).get("nom", ""),
                          "categorie": noms.get(identifiant, {}).get("categorie_cg", ""),
                          "verticale": ligne["verticale"], "date_tge": ligne["date_tge"],
                          "mots": " ".join(mots)})
    return liste


def correspondances(liste):
    manuelles = {l["id_coingecko"]: l for l in lire_csv(DOSSIER / "correspondances.csv")}
    protocoles = get("/protocols") or []
    parents = (get("/lite/protocols2") or {}).get("parentProtocols") or []
    chaines = get("/v2/chains") or []
    for c in liste:
        cible = c["id_coingecko"]
        trouve = None
        if cible in manuelles:
            m = manuelles[cible]
            trouve = (("", "", "", "manuelle : absent") if m["genre"] == "aucun"
                      else (m["genre"], m["slug"], m["slug"], "manuelle"))
        if not trouve:
            for p in protocoles:
                if p.get("gecko_id") == cible:
                    trouve = ("protocole", p["slug"], p.get("name"), "gecko_id")
                    break
        if not trouve:
            for p in parents:
                if p.get("gecko_id") == cible:
                    trouve = ("parent", p["id"].split("#", 1)[1], p.get("name"), "gecko_id")
                    break
        if not trouve:
            for ch in chaines:
                if ch.get("gecko_id") == cible:
                    trouve = ("chaine", ch["name"], ch.get("name"), "gecko_id")
                    break
        c["genre_defillama"], c["slug_defillama"], c["nom_defillama"], c["methode"] = \
            trouve or ("", "", "", "non trouvé")
        categories = {p.get("category") for p in protocoles
                      if (c["genre_defillama"] == "protocole" and p.get("slug") == c["slug_defillama"])
                      or (c["genre_defillama"] == "parent"
                          and p.get("parentProtocol") == f"parent#{c['slug_defillama']}")}
        c["perps"] = c["verticale"] == "perps" or "Derivatives" in categories
    return liste


def serie_tvl(genre, slug):
    """[(jour, tvl)] depuis DefiLlama ; protocole ou parent via /protocol, chaîne via /v2."""
    if genre == "chaine":
        brut = get(f"/v2/historicalChainTvl/{slug}") or []
        return [(jour(p["date"]), p.get("tvl") or 0) for p in brut]
    brut = (get(f"/protocol/{slug}") or {}).get("tvl") or []
    return [(jour(p["date"]), p.get("totalLiquidityUSD") or 0) for p in brut]


def index_volumes():
    """{type: [entrées]} des volumes gratuits, pour retrouver les slugs enfants d'un parent."""
    index = {}
    for type_volume in TYPES_VOLUME_GRATUITS:
        brut = get(f"/overview/{type_volume}", {"excludeTotalDataChart": "true",
                                                "excludeTotalDataChartBreakdown": "true",
                                                "dataType": "dailyVolume"}) or {}
        index[type_volume] = brut.get("protocols") or []
    return index


def sources_volume(c, index):
    """['type/slug', …] couvrant le candidat dans les volumes gratuits."""
    if c["genre_defillama"] not in ("protocole", "parent"):
        return []
    trouves = []
    parent_id = f"parent#{c['slug_defillama']}" if c["genre_defillama"] == "parent" else None
    for type_volume, entrees in index.items():
        for e in entrees:
            if (c["genre_defillama"] == "protocole" and e.get("slug") == c["slug_defillama"]) \
                    or (parent_id and e.get("parentProtocol") == parent_id):
                trouves.append(f"{type_volume}/{e['slug']}")
    return trouves


def serie_volume(sources):
    """[(jour, volume)] sommé sur les sources gratuites."""
    total = {}
    for source in sources:
        type_volume, slug = source.split("/", 1)
        brut = get(f"/summary/{type_volume}/{slug}", {"dataType": "dailyVolume",
                                                        "excludeTotalDataChartBreakdown": "true"}) or {}
        for ts, v in brut.get("totalDataChart") or []:
            total[jour(ts)] = total.get(jour(ts), 0) + (v or 0)
    return sorted(total.items())


def couverture(serie, date_tge):
    positifs = [j for j, v in serie if v > 0]
    if not positifs:
        return "", 0, "non"
    premier = positifs[0]
    jours_pre = sum(1 for j in positifs if j < date_tge)
    verdict = "oui" if jours_pre >= JOURS_COUVERTURE_MIN else "partiel" if jours_pre else "non"
    return premier, jours_pre, verdict


def ecrire_sessions(liste):
    dossier = DOSSIER / "sessions"
    dossier.mkdir(parents=True, exist_ok=True)
    for perime in dossier.glob("farm_*.txt"):
        perime.unlink()
    tokens = list(liste)
    random.Random(GRAINE).shuffle(tokens)
    for rang, debut in enumerate(range(0, len(tokens), TAILLE_SESSION), 1):
        lignes = [f"{t['id_coingecko']} | {t['ticker']} | {t['nom']} | TGE {t['date_tge']} "
                  f"| {t['verticale']} ({t['categorie']})" for t in tokens[debut:debut + TAILLE_SESSION]]
        (dossier / f"farm_{rang:02d}.txt").write_text(
            CONSIGNES + "\n\nTokens à documenter (id_coingecko | ticker | nom | TGE | catégorie) :\n\n"
            + "\n".join(lignes) + "\n", encoding="utf-8")
    return (len(tokens) + TAILLE_SESSION - 1) // TAILLE_SESSION


def main():
    liste = correspondances(candidats())
    index = index_volumes()
    for c in liste:
        c["perps"] = "oui" if c["perps"] else "non"
        if c["slug_defillama"]:
            c["tvl_premier_jour"], c["tvl_jours_pre_tge"], c["couverture_tvl"] = \
                couverture(serie_tvl(c["genre_defillama"], c["slug_defillama"]), c["date_tge"])
        else:
            c["tvl_premier_jour"], c["tvl_jours_pre_tge"], c["couverture_tvl"] = "", 0, "non"
        sources = sources_volume(c, index)
        spot_ignore = False
        if c["perps"] == "oui":
            valides = [s for s in sources if s.startswith("aggregator-derivatives/")]
            spot_ignore = len(valides) < len(sources)
            sources = valides
        c["volume_sources"] = "|".join(sources)
        if sources:
            c["volume_premier_jour"], c["volume_jours_pre_tge"], c["couverture_volume"] = \
                couverture(serie_volume(sources), c["date_tge"])
        else:
            c["volume_premier_jour"], c["volume_jours_pre_tge"] = "", 0
            c["couverture_volume"] = (
                "payant (perps, HTTP 402)" + (" — série spot gratuite écartée" if spot_ignore else "")
                if c["perps"] == "oui" else "aucune série gratuite")
        print(f"  {c['ticker']:<8} {c['verticale']:<13} {c['methode']:<22} "
              f"{c['slug_defillama'] or '—':<22} TVL {c['couverture_tvl']:<8} "
              f"volume {c['couverture_volume']}")

    colonnes = ["id_coingecko", "ticker", "nom", "verticale", "date_tge", "mots",
                "genre_defillama", "slug_defillama", "nom_defillama", "methode", "perps",
                "tvl_premier_jour", "tvl_jours_pre_tge", "couverture_tvl",
                "volume_sources", "volume_premier_jour", "volume_jours_pre_tge", "couverture_volume"]
    with (DOSSIER / "candidats.csv").open("w", encoding="utf-8-sig", newline="") as sortie:
        redacteur = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
        redacteur.writeheader()
        redacteur.writerows(liste)
    sessions = ecrire_sessions(liste)
    print(f"{len(liste)} candidats -> backtest/farming/candidats.csv ; {sessions} session(s) "
          f"farm_NN.txt (aucune performance affichée)")


if __name__ == "__main__":
    main()
