"""Backtest farming — calcul des lectures TVL et volume (protocole.md, figé).

Ne s'exécute utilement qu'une fois les notes farming rendues dans
backtest/farming/notes/*.csv (format des sessions farm_NN.txt) : sans notes, il
s'arrête sans rien calculer.

Pour chaque token noté programme_pretge=oui : valeur de sortie
(airdrop_pct_farmers × airdrop_unlock_tge_pct × supply × médiane des clôtures
J+1 à J+7 ; supply = max_supply CoinGecko, sinon total_supply signalée
supply_proxy), puis selon base_eligibilite :
- tvl : rendement annualisé sur la TVL moyenne DefiLlama de la fenêtre ;
- volume : bps du volume cumulé pré-TGE des notes (ordre de grandeur) ;
- mixte : les deux lectures, hors Q1/Q2, en ligne de sensibilité ;
- taches : aucune lecture.
Q1 : médiane du rendement TVL contre 5 %/an. Q2 : traction_tge forte contre le
reste, backers tier1 contre le reste, pour chaque lecture.

Seuils : Q1 non concluante sous 8 lectures TVL principales ; Q2 calculée seulement
si chaque groupe compte au moins 3 lectures.

Usage  : python backtest/farming/calculer.py
         python backtest/farming/calculer.py --couverture   # comptes seulement, aucune valeur
Sortie : backtest/farming/resultats.md (--couverture : console seulement)
"""

import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

from preparer import DOSSIER, RACINE, lire_csv, serie_tvl

sys.path.insert(0, str(RACINE / "backtest"))
from bilan_passage import charger_notes  # noqa: E402
from mesurer_performance import appel_cg, serie_journaliere  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

CHAMPS_FARMING = ("programme_pretge", "debut_programme", "base_eligibilite",
                  "airdrop_pct_farmers", "airdrop_unlock_tge_pct",
                  "volume_cumule_pretge_usd", "confiance")
COUVERTURE_MIN = 0.9
JOURS_SORTIE = range(1, 8)
JOURS_SORTIE_MIN = 5
SEUIL_Q1 = 5.0  # %/an
Q1_N_MIN = 8
Q2_N_MIN = 3
SUFFIXES = {"k": 1e3, "m": 1e6, "md": 1e9, "mds": 1e9, "b": 1e9, "bn": 1e9, "t": 1e12}


def nombre(texte):
    brut = re.sub(r"[%\s]", "", str(texte or "")).replace(",", ".")
    try:
        return float(brut)
    except ValueError:
        return None


def montant(texte):
    """Montant en dollars ; tolère $, espaces, séparateurs et suffixes k/M/Md/B/T."""
    brut = re.sub(r"[\s$_  ]", "", str(texte or "")).lower()
    m = re.fullmatch(r"([\d.,]+)(k|m|mds|md|bn|b|t)?", brut)
    if not m:
        return None
    chiffres, suffixe = m.groups()
    if chiffres.count(",") == 1 and "." not in chiffres and len(chiffres.split(",")[1]) != 3:
        chiffres = chiffres.replace(",", ".")
    chiffres = chiffres.replace(",", "")
    try:
        return float(chiffres) * SUFFIXES.get(suffixe or "", 1)
    except ValueError:
        return None


def charger_notes_farming():
    """{id: note} ; arrêt sur divergence entre deux fichiers."""
    par_id = {}
    for fichier in sorted((DOSSIER / "notes").glob("*.csv")):
        for note in lire_csv(fichier):
            identifiant = (note.get("id_coingecko") or "").strip()
            if identifiant:
                par_id.setdefault(identifiant, []).append((fichier.name, note))
    conflits = [f"{i} ({', '.join(f for f, _ in v)})" for i, v in par_id.items()
                if any(str(n.get(c) or "").strip().lower() != str(v[0][1].get(c) or "").strip().lower()
                       for _, n in v[1:] for c in CHAMPS_FARMING)]
    if conflits:
        print("Conflits de notes farming, à résoudre à la main : " + " ; ".join(conflits))
        sys.exit(1)
    return {i: v[0][1] for i, v in par_id.items()}


def valeur_sortie(identifiant, date_tge, note):
    """(valeur en $, détail, supply_proxy) ; valeur None si non mesurable."""
    pct, unlock = nombre(note.get("airdrop_pct_farmers")), nombre(note.get("airdrop_unlock_tge_pct"))
    if pct is None or unlock is None:
        return None, "airdrop_pct_farmers ou airdrop_unlock_tge_pct manquant", False
    marche = (appel_cg(f"/coins/{identifiant}", {"localization": "false", "tickers": "false",
                                                  "market_data": "true", "community_data": "false",
                                                  "developer_data": "false"})
              .get("market_data") or {})
    supply, proxy = marche.get("max_supply"), False
    if not supply:
        supply, proxy = marche.get("total_supply"), True
    if not supply:
        return None, "ni max_supply ni total_supply CoinGecko", False
    serie = serie_journaliere(identifiant)
    tge = date.fromisoformat(date_tge)
    clotures = [serie[j] for j in ((tge + timedelta(days=n)).isoformat() for n in JOURS_SORTIE)
                if j in serie]
    if len(clotures) < JOURS_SORTIE_MIN:
        return None, f"{len(clotures)} clôture(s) sur J+1..J+7", proxy
    prix = statistics.median(clotures)
    return pct / 100 * unlock / 100 * supply * prix, f"prix médian {prix:.4g} $", proxy


def lecture_tvl(candidat, debut, date_tge, valeur):
    """(rendement %/an ou None, texte)."""
    if not candidat["slug_defillama"]:
        return None, "absent de DefiLlama"
    points = [(j, v) for j, v in serie_tvl(candidat["genre_defillama"], candidat["slug_defillama"])
              if debut <= j < date_tge]
    jours = (date.fromisoformat(date_tge) - date.fromisoformat(debut)).days
    taux = len(points) / jours if jours > 0 else 0
    tvl_moy = statistics.mean(v for _, v in points) if points else 0
    if taux < COUVERTURE_MIN or tvl_moy <= 0:
        return None, f"couverture {taux:.0%} : non mesurable"
    rendement = valeur / (tvl_moy * jours / 365.25) * 100
    return rendement, f"{rendement:.1f} %/an (TVL moy. {tvl_moy:,.0f} $, {jours} j)"


def lecture_volume(note, valeur):
    """(bps ou None, texte) — ordre de grandeur, volume des notes."""
    volume = montant(note.get("volume_cumule_pretge_usd"))
    if not volume or volume <= 0:
        return None, "volume_cumule_pretge_usd absent"
    bps = valeur / volume * 10_000
    return bps, f"~{bps:.1f} bps (volume {volume:,.0f} $)"


def cellule(n_med, unite):
    n, med = n_med
    return f"n={n}, {med:.1f} {unite}" if med is not None else f"n={n}, —"


def mediane_groupes(valeurs, notes_backtest, champ, favorable):
    groupes = {"favorable": [], "reste": []}
    for identifiant, v in valeurs.items():
        cle = ("favorable" if str(notes_backtest.get(identifiant, {}).get(champ) or "").strip().lower()
               == favorable else "reste")
        groupes[cle].append(v)
    return {k: (len(v), statistics.median(v) if v else None) for k, v in groupes.items()}


def couverture(notes):
    """Comptes d'éligibilité, sans réseau ni valeur calculée."""
    candidats = {c["id_coingecko"]: c for c in lire_csv(DOSSIER / "candidats.csv")}
    comptes = {"tvl": 0, "volume": 0, "mixte_tvl": 0, "mixte_volume": 0, "mixte": 0}
    motifs, bloques = {}, []
    for identifiant, note in sorted(notes.items()):
        c = candidats.get(identifiant, {})
        base = str(note.get("base_eligibilite") or "").strip().lower()
        if str(note.get("programme_pretge") or "").strip().lower() != "oui":
            manques = ["programme non"]
        elif base == "taches":
            manques = ["base taches"]
        elif base not in ("tvl", "volume", "mixte"):
            manques = ["base manquante"]
        else:
            communs = []
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(note.get("debut_programme") or "").strip()):
                communs.append("debut_programme")
            if nombre(note.get("airdrop_pct_farmers")) is None:
                communs.append("airdrop_pct_farmers")
            if nombre(note.get("airdrop_unlock_tge_pct")) is None:
                communs.append("airdrop_unlock_tge_pct")
            manque_tvl = communs + ([] if c.get("slug_defillama") else ["absent de DefiLlama"])
            manque_vol = communs + ([] if montant(note.get("volume_cumule_pretge_usd")) else ["volume"])
            ok_tvl, ok_vol = not manque_tvl, not manque_vol
            if base == "tvl" and ok_tvl:
                comptes["tvl"] += 1
                continue
            if base == "volume" and ok_vol:
                comptes["volume"] += 1
                continue
            if base == "mixte" and (ok_tvl or ok_vol):
                comptes["mixte"] += 1
                comptes["mixte_tvl"] += ok_tvl
                comptes["mixte_volume"] += ok_vol
                continue
            manques = (manque_tvl if base == "tvl" else manque_vol if base == "volume"
                       else sorted(set(manque_tvl) | set(manque_vol)))
        bloques.append((c.get("ticker") or identifiant, base or "?", manques))
        for m in manques:
            motifs[m] = motifs.get(m, 0) + 1

    print(f"Couverture — {len(notes)} ligne(s) notée(s), aucune valeur calculée")
    print(f"  éligibles lecture TVL principale    : {comptes['tvl']}  (seuil Q1 : {Q1_N_MIN})")
    print(f"  éligibles lecture volume principale : {comptes['volume']}")
    print(f"  éligibles sensibilité mixte         : {comptes['mixte']} "
          f"(TVL {comptes['mixte_tvl']}, volume {comptes['mixte_volume']})")
    print(f"  bloquées                            : {len(bloques)}")
    for motif, n in sorted(motifs.items(), key=lambda x: -x[1]):
        print(f"    {motif:<24} {n}")
    for ticker, base, manques in bloques:
        print(f"    - {ticker:<8} base {base:<7} : {', '.join(manques)}")
    print("  (la couverture DefiLlama de la fenêtre, 90 % des jours, n'est vérifiée qu'au calcul)")


def main():
    notes = charger_notes_farming()
    if "--couverture" in sys.argv[1:]:
        if not notes:
            print("Aucune note farming : rien à compter.")
            return
        couverture(notes)
        return
    if not notes:
        print("Aucune note farming dans backtest/farming/notes/ : rien à calculer "
              "(protocole figé, sessions dans backtest/farming/sessions/).")
        return

    candidats = {c["id_coingecko"]: c for c in lire_csv(DOSSIER / "candidats.csv")}
    non_notes = set(candidats) - set(notes)
    if non_notes:
        print(f"Calcul bloqué : {len(candidats) - len(non_notes)}/{len(candidats)} candidats notés. "
              f"Le protocole interdit tout rendement avant la fin des sessions ; "
              f"utilisez --couverture.")
        sys.exit(1)
    dates_tge = {l["id_coingecko"]: l["date_tge"]
                 for l in lire_csv(RACINE / "backtest" / "performances.csv")}
    notes_backtest = charger_notes()

    lignes, obtenues = [], []
    principales = {"tvl": {}, "volume": {}}
    sensibilite = {"tvl": {}, "volume": {}}
    for identifiant, note in sorted(notes.items()):
        c = candidats.get(identifiant)
        if not c or str(note.get("programme_pretge") or "").strip().lower() != "oui":
            continue
        date_tge = dates_tge.get(identifiant)
        base = str(note.get("base_eligibilite") or "").strip().lower()
        debut = str(note.get("debut_programme") or "").strip()
        if debut and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", debut):
            debut = ""  # format invalide : traité comme manquant
        valeur, detail, proxy = valeur_sortie(identifiant, date_tge, note)
        ligne = {"ticker": c["ticker"], "base": base or "?", "valeur": valeur, "detail": detail,
                 "supply": ("supply_proxy" if proxy else "max_supply") if valeur is not None else "—", "tvl": "—", "volume": "—"}
        cible = sensibilite if base == "mixte" else principales

        if valeur is not None and not debut and base in ("tvl", "volume", "mixte"):
            ligne["tvl"] = ligne["volume"] = "debut_programme manquant"
        elif valeur is not None:
            statut = "mixte, sensibilité" if base == "mixte" else "principale"
            if base in ("tvl", "mixte"):
                rendement, ligne["tvl"] = lecture_tvl(c, debut, date_tge, valeur)
                if rendement is not None:
                    cible["tvl"][identifiant] = rendement
                    obtenues.append((c["ticker"], f"TVL ({statut})", ligne["tvl"]))
            if base in ("volume", "mixte"):
                bps, ligne["volume"] = lecture_volume(note, valeur)
                if bps is not None:
                    cible["volume"][identifiant] = bps
                    obtenues.append((c["ticker"], f"volume ({statut}, ordre de grandeur)",
                                     ligne["volume"]))
        lignes.append(ligne)
        print(f"  {c['ticker']:<8} {base or '?':<7} TVL : {ligne['tvl']} | volume : {ligne['volume']}")

    L = ["# Backtest farming — résultats", "",
         f"_Calculé le {date.today().isoformat()} selon `protocole.md` (figé avant mesure)._", "",
         "| Token | Base | Valeur de sortie | Supply | Lecture TVL | Lecture volume (ordre de grandeur) |",
         "|---|---|---|---|---|---|"]
    for l in lignes:
        valeur = (f"{l['valeur']:,.0f} $ ({l['detail']})" if l["valeur"] is not None
                  else f"non mesurable ({l['detail']})")
        L.append(f"| {l['ticker']} | {l['base']} | {valeur} | {l['supply']} | {l['tvl']} "
                 f"| {l['volume']} |")

    L += ["", "## Q1 — rendement annualisé TVL contre 5 %/an (base tvl)", ""]
    n_tvl = len(principales["tvl"])
    concluant = n_tvl >= Q1_N_MIN
    if not concluant:
        L.append(f"**Non concluante** : {n_tvl} lecture(s) TVL principale(s), seuil {Q1_N_MIN}. "
                 f"Les lectures obtenues sont rapportées plus bas comme cas isolés, non "
                 f"généralisables : ni médiane, ni comparaison à {SEUIL_Q1:.0f} %/an.")
    else:
        mediane = statistics.median(principales["tvl"].values())
        L.append(f"Médiane : **{mediane:.1f} %/an** (n={n_tvl}), "
                 f"{'au-dessus' if mediane > SEUIL_Q1 else 'en dessous'} de {SEUIL_Q1:.0f} %/an.")

    L += ["", "## Q2 — traction forte et backers tier1 contre le reste (bases tvl et volume)", "",
          "| Lecture | Découpage | Favorable (n, médiane) | Reste (n, médiane) |", "|---|---|---|---|"]
    for nom, unite in (("tvl", "%/an"), ("volume", "bps")):
        for champ, favorable in (("traction_tge", "forte"), ("backers", "tier1")):
            g = mediane_groupes(principales[nom], notes_backtest, champ, favorable)
            if min(g["favorable"][0], g["reste"][0]) < Q2_N_MIN:
                L.append(f"| {nom} | {champ} = {favorable} | n={g['favorable'][0]} "
                         f"| n={g['reste'][0]} — non calculée (moins de {Q2_N_MIN} par groupe) |")
                continue
            L.append(f"| {nom} | {champ} = {favorable} | {cellule(g['favorable'], unite)} "
                     f"| {cellule(g['reste'], unite)} |")

    L += ["", "## Sensibilité — base mixte (hors Q1 et Q2)", ""]
    for nom, unite in (("tvl", "%/an"), ("volume", "bps")):
        valeurs = list(sensibilite[nom].values())
        if not valeurs:
            L.append(f"- Lecture {nom} : aucune lecture mesurable")
        elif concluant:
            L.append(f"- Lecture {nom} : n={len(valeurs)}, médiane {statistics.median(valeurs):.1f} {unite}")
        else:
            L.append(f"- Lecture {nom} : n={len(valeurs)}, rapportée dans les cas isolés (pas de médiane)")

    if not concluant:
        L += ["", "## Cas isolés — non généralisables", ""]
        L += ([f"- {ticker} — {genre} : {texte}" for ticker, genre, texte in obtenues]
              or ["Aucune lecture obtenue."])

    fichier = DOSSIER / "resultats.md"
    fichier.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
