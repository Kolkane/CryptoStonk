"""Forward cadré — évaluation selon le protocole (forward/protocole.md, commit 3456162).

Vérifie d'abord le protocole, le registre de hash et la validité du test
(3 semaines manquées = test invalide). Avant les dates de lecture du protocole,
n'affiche que des comptes, aucune valeur : pas de lecture intermédiaire.

Q1, adéquation : croissance de la métrique d'adoption de J0 à J+90, fiches
d'adéquation forte contre faible (moyenne exclue). Au moins 8 fiches évaluables
par groupe ; signal si l'écart des médianes atteint +20 points ; sinon pas de
signal ; sous les minimums, non concluant. Lecture 90 jours après la dernière
fiche de la semaine 12 (fin de la semaine 12 à défaut).
Q2, positionnement : positions papier (adéquation forte, conviction haute, token
coté à J0) contre BTC à J+90 (principale) et J+180 (secondaire). Au moins 10
positions évaluables ; signal si la médiane est positive. Lectures 90 puis 180
jours après la dernière position.

Précisions d'implémentation : forward/precisions.md (commit b04c936), vérifiées
par empreinte comme le protocole :
- métrique DefiLlama : TVL du jour (±3 jours) ; volume DEX et frais en moyenne
  des 7 jours finissant à J0 et à J+90 (au moins 5 jours présents) ;
- prix : clôture CoinGecko de J0 (dernier prix du jour UTC), pas le prix indicatif
  de la fiche ;
- sortie sur invalidation (forward/sorties.csv) : la position passe en cash à la
  clôture CoinGecko du jour de sortie ; sa perf se compare au BTC sur tout l'horizon ;
- token sans cotation depuis 14 jours à la date mesurée : -100 % ;
- semaine manquée : semaine terminée sans trace de rituel commitée pendant la
  semaine (forward/rituels/semaine_NN.log), même journalisée après coup ;
- Q1 positif et Q2 non concluant : même décision que Q1 positif et Q2 négatif ;
- une fiche remplacée par une correction sort des calculs, la correction compte
  avec sa propre date comme J0.

Usage : python forward/evaluer.py
"""

import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests

from enregistrer import (DEBUT, DOSSIER, RACINE, REGISTRE, SEMAINES, SORTIES, bornes_semaine,
                         est_position_q2, lire_csv, lire_fiche, semaine_de, semaines_manquees, texte,
                         verifier_protocole, verifier_registre)

sys.path.insert(0, str(RACINE / "backtest"))
from mesurer_performance import serie_journaliere  # noqa: E402

LLAMA = "https://api.llama.fi"
ENTETES = {"User-Agent": "CryptoStonk/0.1 (outil interne)"}
Q1_N_MIN, Q1_ECART = 8, 20.0
Q2_N_MIN = 10
SEMAINES_MANQUEES_MAX = 3
JOURS_MORT = 14


def jour(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()


def get_llama(chemin, params=None):
    time.sleep(0.3)
    reponse = requests.get(f"{LLAMA}{chemin}", params=params, headers=ENTETES, timeout=120)
    return reponse.json() if reponse.status_code == 200 else None


def serie_metrique(nature, slug):
    """{jour: valeur} depuis DefiLlama (gratuit)."""
    if nature == "tvl" and slug.startswith("chain:"):
        brut = get_llama(f"/v2/historicalChainTvl/{slug[6:]}") or []
        return {jour(p["date"]): p.get("tvl") or 0 for p in brut}
    if nature == "tvl":
        brut = (get_llama(f"/protocol/{slug}") or {}).get("tvl") or []
        return {jour(p["date"]): p.get("totalLiquidityUSD") or 0 for p in brut}
    chemin, type_donnee = (("/summary/dexs", "dailyVolume") if nature == "volume_dex"
                           else ("/summary/fees", "dailyFees"))
    brut = (get_llama(f"{chemin}/{slug}", {"dataType": type_donnee,
                                           "excludeTotalDataChartBreakdown": "true"}) or {})
    return {jour(ts): v or 0 for ts, v in brut.get("totalDataChart") or []}


def valeur_metrique(serie, nature, jour_mesure):
    if nature == "tvl":
        for decalage in (0, -1, 1, -2, 2, -3, 3):
            j = (jour_mesure + timedelta(days=decalage)).isoformat()
            if j in serie:
                return serie[j]
        return None
    fenetre = [serie[j] for j in ((jour_mesure - timedelta(days=d)).isoformat() for d in range(7))
               if j in serie]
    return statistics.mean(fenetre) if len(fenetre) >= 5 else None


def prix_au(serie, jour_mesure):
    for decalage in (0, -1, 1, -2, 2, -3, 3):
        j = (jour_mesure + timedelta(days=decalage)).isoformat()
        if j in serie:
            return serie[j]
    return None


def fiches_actives():
    """Fiches enregistrées des semaines 1 à 12, hors fiches remplacées par une correction."""
    fiches = []
    for ligne in lire_csv(REGISTRE):
        fiche = lire_fiche(DOSSIER / ligne["fichier"])
        fiche["_j0"] = date.fromisoformat(ligne["date"])
        fiches.append(fiche)
    remplacees = {texte(f.get("remplace")) for f in fiches if texte(f.get("remplace"))}
    return [f for f in fiches if texte(f.get("id")) not in remplacees
            and 1 <= semaine_de(f["_j0"]) <= SEMAINES]


def croissance_q1(fiche):
    m = fiche.get("metrique") or {}
    nature, slug = texte(m.get("nature")), texte(m.get("slug_defillama"))
    if not nature or not slug:
        return None
    serie = serie_metrique(nature, slug)
    v0 = valeur_metrique(serie, nature, fiche["_j0"])
    v90 = valeur_metrique(serie, nature, fiche["_j0"] + timedelta(days=90))
    if not v0 or v0 <= 0 or v90 is None:
        return None
    return (v90 / v0 - 1) * 100


def perf_q2(fiche, horizon, btc, sorties):
    """Perf vs BTC de J0 à J0+horizon, sortie sur invalidation comprise."""
    token = texte((fiche.get("position") or {}).get("token"))
    serie = serie_journaliere(token)
    j0, jh = fiche["_j0"], fiche["_j0"] + timedelta(days=horizon)
    sortie = sorties.get(texte(fiche.get("id")))
    j_sortie = min(jh, date.fromisoformat(sortie)) if sortie else jh
    p0, b0, bh = prix_au(serie, j0), prix_au(btc, j0), prix_au(btc, jh)
    if not (p0 and b0 and bh):
        return None
    p_sortie = prix_au(serie, j_sortie)
    if p_sortie is None:
        derniere = max(serie) if serie else ""
        if derniere and derniere < (j_sortie - timedelta(days=JOURS_MORT)).isoformat():
            return -100.0
        return None
    return ((p_sortie / p0) / (bh / b0) - 1) * 100


def main():
    verifier_protocole()
    verifier_registre()
    aujourd_hui = date.today()
    manquees = semaines_manquees(aujourd_hui)
    fiches = fiches_actives()
    print(f"Forward v1 — {aujourd_hui}, semaine {semaine_de(aujourd_hui)} (test : semaines 1 à "
          f"{SEMAINES}, du {DEBUT} au {bornes_semaine(SEMAINES)[1]})")
    print(f"  Protocole, précisions et registre intacts ; {len(fiches)} fiche(s) active(s) ; semaines manquées : "
          f"{len(manquees)}/{SEMAINES_MANQUEES_MAX} tolérées")
    if len(manquees) >= SEMAINES_MANQUEES_MAX:
        print(f"TEST INVALIDE : semaines manquées {manquees} (règle : 3 sur 12).")
        return

    # Q1
    groupes = {"forte": [f for f in fiches if texte(f.get("adequation")) == "forte"],
               "faible": [f for f in fiches if texte(f.get("adequation")) == "faible"]}
    moyennes = sum(1 for f in fiches if texte(f.get("adequation")) == "moyenne")
    semaine12 = [f["_j0"] for f in fiches if semaine_de(f["_j0"]) == SEMAINES]
    lecture_q1 = (max(semaine12) if semaine12 else bornes_semaine(SEMAINES)[1]) + timedelta(days=90)
    print(f"\nQ1, adéquation — lecture le {lecture_q1}"
          f"{'' if semaine12 else ' au plus tôt (fin de semaine 12)'}")
    print(f"  fiches : forte {len(groupes['forte'])}, faible {len(groupes['faible'])}, "
          f"moyenne {moyennes} (suivies, hors contraste)")
    if aujourd_hui < lecture_q1 or semaine_de(aujourd_hui) <= SEMAINES:
        echues = {g: sum(1 for f in l if f["_j0"] + timedelta(days=90) <= aujourd_hui)
                  for g, l in groupes.items()}
        print(f"  avant la date de lecture : comptes seulement (J+90 atteint : forte {echues['forte']}, "
              f"faible {echues['faible']})")
        q1 = None
    else:
        valeurs = {g: [c for c in (croissance_q1(f) for f in l) if c is not None]
                   for g, l in groupes.items()}
        n_forte, n_faible = len(valeurs["forte"]), len(valeurs["faible"])
        if min(n_forte, n_faible) < Q1_N_MIN:
            q1 = "non concluant"
            print(f"  NON CONCLUANT : {n_forte} forte / {n_faible} faible évaluables (minimum {Q1_N_MIN} par groupe)")
        else:
            m_forte, m_faible = statistics.median(valeurs["forte"]), statistics.median(valeurs["faible"])
            ecart = m_forte - m_faible
            q1 = "signal" if ecart >= Q1_ECART else "pas de signal"
            print(f"  forte {m_forte:+.1f} % (n={n_forte}), faible {m_faible:+.1f} % (n={n_faible}), "
                  f"écart {ecart:+.1f} pts -> {q1.upper()}")

    # Q2
    positions = [f for f in fiches if est_position_q2(f)]
    sorties = {l["id_fiche"]: l["date"] for l in lire_csv(SORTIES)}
    print(f"\nQ2, positionnement — {len(positions)} position(s) papier, {len(sorties)} sortie(s) sur invalidation")
    q2 = {}
    if not positions:
        print("  aucune position : rien à lire")
    else:
        derniere = max(f["_j0"] for f in positions)
        btc = None
        for horizon, nom in ((90, "principale"), (180, "secondaire")):
            lecture = derniere + timedelta(days=horizon)
            if aujourd_hui < lecture or semaine_de(aujourd_hui) <= SEMAINES:
                echues = sum(1 for f in positions if f["_j0"] + timedelta(days=horizon) <= aujourd_hui)
                print(f"  issue {nom} J+{horizon} : lecture le {lecture} au plus tôt — comptes seulement "
                      f"({echues} position(s) à l'horizon)")
                continue
            btc = btc or serie_journaliere("bitcoin")
            valeurs = [p for p in (perf_q2(f, horizon, btc, sorties) for f in positions) if p is not None]
            if len(valeurs) < Q2_N_MIN:
                q2[horizon] = "non concluant"
                print(f"  issue {nom} J+{horizon} : NON CONCLUANT ({len(valeurs)} évaluables, minimum {Q2_N_MIN})")
            else:
                mediane = statistics.median(valeurs)
                q2[horizon] = "signal" if mediane > 0 else "pas de signal"
                print(f"  issue {nom} J+{horizon} : médiane {mediane:+.1f} % vs BTC (n={len(valeurs)}) "
                      f"-> {q2[horizon].upper()}")

    # Décision (issue principale de Q2)
    if q1 is None:
        print("\nDécision : en attente de la lecture Q1.")
    elif q1 != "signal":
        print("\nDécision : Q1 négatif ou non concluant -> arrêt de CryptoStonk comme outil de positionnement.")
    elif positions and 90 not in q2:
        print("\nDécision : Q1 positif ; en attente de la lecture Q2 à J+90.")
    elif q2.get(90) == "signal":
        print("\nDécision : Q1 et Q2 positifs -> l'outil peut servir à se positionner ; "
              "la question du capital réel est ouverte.")
    else:
        cas = "négatif" if q2.get(90) == "pas de signal" else "non concluant (ou sans position)"
        print(f"\nDécision : Q1 positif, Q2 {cas} -> l'analyse fonctionne mais ne se monétise pas par "
              "le token ; le radar reste comme outil d'analyse. Prolonger Q2 exige un nouveau protocole "
              "figé avant toute nouvelle position.")


if __name__ == "__main__":
    main()
