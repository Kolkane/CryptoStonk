"""Backtest v0 — bilan du passage complet de notation.

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de
plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4,
pas la détection de problèmes.

Une fois toutes les notes rendues, la jointure couvre l'échantillon mesurable
entier : la sur-représentation des extrêmes du passage stratifié est diluée
dans l'ensemble, la lecture absolue redevient légitime.

Sections : (a) état ; (b) lecture absolue J+90 ; (c) contrastes J+90, global
et hors plancher ; (d) mêmes contrastes à J+180 ; (e) float en tranches ;
(f) valeur du filtre plancher. Lecture seule : ne touche ni aux notes, ni à
l'échantillon, ni au scoring.

Usage  : python backtest/bilan_passage.py
Sortie : backtest/bilan_passage_complet.md
"""

import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

from analyser_notation import CRITERES, classer, contraste, est_fantome, lire_csv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
JOURS_SANS_COTATION_MORT = 14
FENETRES = (90, 180)
CRITERES_TOUS = list(CRITERES) + ["float_initial_pct"]
CHAMPS_NOTATION = ("produit_live", "traction_tge", "float_initial_pct",
                   "fees_vers_token", "backers", "confiance")
TRANCHES_FLOAT = ((0, 10, "< 10 %"), (10, 20, "10-20 %"), (20, 50, "20-50 %"),
                  (50, float("inf"), ">= 50 %"))
SEUIL_ZERO = -90.0  # % vs BTC : « quasi-zéro »


def charger_notes():
    """Toutes les notes ; arrêt sur divergence (même règle qu'analyser_notation)."""
    par_id = {}
    for fichier in sorted((RACINE / "backtest" / "notes").glob("*.csv")):
        for note in lire_csv(fichier):
            identifiant = (note.get("id_coingecko") or "").strip()
            if identifiant:
                par_id.setdefault(identifiant, []).append(note)

    def normalise(note, champ):
        return str(note.get(champ) or "").strip().lower().replace(",", ".")

    conflits = [i for i, versions in par_id.items()
                if any(normalise(v, c) != normalise(versions[0], c)
                       for v in versions[1:] for c in CHAMPS_NOTATION)]
    if conflits:
        print(f"Conflits de notation sur {', '.join(conflits)} — "
              f"lancez analyser_notation.py pour le détail.")
        sys.exit(1)
    return {i: versions[0] for i, versions in par_id.items()}


def valeur_jn(ligne, n, est_mort):
    """Perf rel. BTC mesurée à J+n ; sinon -100 % si le token est mort avant la
    fenêtre ; sinon None. Un token non mesurable n'est jamais imputé."""
    if (ligne.get("statut") or "") == "non_mesurable":
        return None, False
    if ligne.get(f"rel_btc_j{n}_pct"):
        return float(ligne[f"rel_btc_j{n}_pct"]), False
    if est_mort:
        cible = (date.fromisoformat(ligne["date_tge"]) + timedelta(days=n)).isoformat()
        if cible > (ligne.get("derniere_cotation") or ""):
            return -100.0, True
    return None, False


def lire_float(note):
    brut = re.sub(r"[%\s]", "", str(note.get("float_initial_pct") or "")).replace(",", ".")
    try:
        return float(brut)
    except ValueError:
        return None


def pct(part, total):
    return f"{100 * part / total:.0f} %" if total else "—"


def fmt(v):
    return f"{v:+.1f} %"


def ligne_contraste(nom, c):
    if not c:
        return f"| {nom} | — | — | incalculable (un groupe vide) |"
    return (f"| {nom} | {fmt(c['med_fav'])} (n={c['n_fav']}) "
            f"| {fmt(c['med_defav'])} (n={c['n_defav']}) | {c['ecart']:+.1f} pts |")


def contrastes(ids, notes, valeurs, scores):
    """Contrastes par critère + composite, split à la médiane des scores de `ids`."""
    lignes = ["| Critère | Favorable | Défavorable | Écart |", "|---|---|---|---|"]
    resultats = {}
    for critere in CRITERES_TOUS:
        c = contraste([(classer(notes[i], critere), valeurs[i]) for i in ids])
        resultats[critere] = c
        lignes.append(ligne_contraste(critere, c))
    mediane = statistics.median([scores[i] for i in ids])
    c = contraste([(1 if scores[i] > mediane else -1 if scores[i] < mediane else 0, valeurs[i])
                   for i in ids])
    resultats["composite"] = c
    lignes.append(ligne_contraste(f"**composite** (split à {mediane:+.1f})", c))
    return lignes, resultats


def main():
    aujourd_hui = date.today()
    seuil_mort = (aujourd_hui - timedelta(days=JOURS_SANS_COTATION_MORT)).isoformat()
    echantillon = lire_csv(RACINE / "backtest" / "echantillon.csv")
    perfs = {l["id_coingecko"]: l for l in lire_csv(RACINE / "backtest" / "performances.csv")}
    notes = charger_notes()
    ids_echantillon = {l["id_coingecko"] for l in echantillon}
    ticker = {l["id_coingecko"]: l["ticker"] for l in echantillon}

    non_notes = sorted(ticker[i] for i in ids_echantillon - set(notes))
    notes_purgees = len(set(notes) - ids_echantillon)
    non_mesurables = sorted(ticker[i] for i in ids_echantillon
                            if (perfs.get(i, {}).get("statut") or "") == "non_mesurable")
    morts = {i for i in ids_echantillon
             if (perfs.get(i, {}).get("derniere_cotation") or "")
             and perfs[i]["derniere_cotation"] < seuil_mort}

    valeurs = {n: {} for n in FENETRES}
    imputes = {n: 0 for n in FENETRES}
    for i in ids_echantillon:
        if i not in perfs:
            continue
        for n in FENETRES:
            v, impute = valeur_jn(perfs[i], n, i in morts)
            if v is not None:
                valeurs[n][i] = v
                imputes[n] += impute
    joints = {n: sorted(i for i in valeurs[n] if i in notes) for n in FENETRES}
    scores = {i: sum(classer(notes[i], c) for c in CRITERES_TOUS) for i in notes}
    basses = sum(1 for i in joints[90]
                 if str(notes[i].get("confiance") or "").strip().lower() == "basse")

    L = ["# Bilan du passage complet de notation — backtest v0", "",
         f"_Généré le {aujourd_hui.isoformat()} par backtest/bilan_passage.py. Lecture seule : "
         f"notes, échantillon et scoring inchangés._", "",
         "Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de "
         "plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4, "
         "pas la détection de problèmes.", ""]

    # (a) état
    L += ["## a. État", "",
          f"- Échantillon final : **{len(ids_echantillon)}** tokens (après purges tracées dans "
          f"`exclusions.csv`).",
          f"- Notes : **{len(notes)}** ids notés, dont {notes_purgees} purgés depuis (hors "
          f"échantillon) ; tokens de l'échantillon sans note : "
          f"**{len(non_notes)}**{' — ' + ', '.join(non_notes) if non_notes else ''}.",
          f"- Jointes à une perf J+90 : **{len(joints[90])}** (dont {basses} en confiance basse) ; "
          f"à J+180 : **{len(joints[180])}**.",
          f"- Non mesurables (vraie date de TGE avant l'historique CoinGecko) : "
          f"**{len(non_mesurables)}** — {', '.join(non_mesurables) or 'aucun'}.",
          f"- Morts (aucune cotation depuis {JOURS_SANS_COTATION_MORT} j) : **{len(morts)}** — "
          f"{', '.join(sorted(ticker[i] for i in morts)) or 'aucun'} ; imputations à -100 % : "
          f"{imputes[90]} à J+90, {imputes[180]} à J+180.", ""]

    # (b) lecture absolue J+90
    v90 = [valeurs[90][i] for i in joints[90]]
    positifs = sum(1 for v in v90 if v > 0)
    zeros = sum(1 for v in v90 if v <= SEUIL_ZERO)
    L += ["## b. Lecture absolue — perf J+90 vs BTC, toutes les jointes", "",
          "Le passage complet couvre l'échantillon mesurable entier : la lecture en niveau "
          "est légitime, contrairement au seul passage stratifié.", "",
          f"- n = **{len(v90)}**",
          f"- Médiane : **{fmt(statistics.median(v90))}**",
          f"- Part positive (bat BTC) : **{pct(positifs, len(v90))}** ({positifs})",
          f"- Part à {SEUIL_ZERO:.0f} % ou pire : **{pct(zeros, len(v90))}** ({zeros})", ""]

    # (c) contrastes J+90
    hors_plancher = {n: [i for i in joints[n] if not est_fantome(notes[i])] for n in FENETRES}
    tab_g90, res_g90 = contrastes(joints[90], notes, valeurs[90], scores)
    tab_h90, res_h90 = contrastes(hors_plancher[90], notes, valeurs[90], scores)
    L += ["## c. Contrastes J+90 vs BTC (médianes, favorable vs défavorable)", "",
          f"### Global (n = {len(joints[90])})", ""] + tab_g90 + [
          "", f"### Hors plancher (n = {len(hors_plancher[90])}, "
          f"{len(joints[90]) - len(hors_plancher[90])} profils fantômes exclus : "
          f"produit_live=non ET traction_tge=nulle ET backers=aucun ; split à la médiane du "
          f"sous-ensemble)", ""] + tab_h90 + [""]

    # (d) contrastes J+180
    tab_g180, res_g180 = contrastes(joints[180], notes, valeurs[180], scores)
    L += ["## d. Mêmes contrastes à J+180 (là où la mesure existe)", "",
          f"### Global (n = {len(joints[180])})", ""] + tab_g180
    if len(hors_plancher[180]) >= 4:
        tab_h180, res_h180 = contrastes(hors_plancher[180], notes, valeurs[180], scores)
        L += ["", f"### Hors plancher (n = {len(hors_plancher[180])})", ""] + tab_h180
    else:
        res_h180 = {}
        L += ["", "Hors plancher : trop peu de mesures."]
    L += [""]

    # (e) float en tranches
    tranches, inconnus = {etiq: [] for _, _, etiq in TRANCHES_FLOAT}, 0
    for i in joints[90]:
        f = lire_float(notes[i])
        if f is None:
            inconnus += 1
            continue
        for bas, haut, etiq in TRANCHES_FLOAT:
            if bas <= f < haut:
                tranches[etiq].append(valeurs[90][i])
                break
    L += ["## e. Float initial en tranches — perf J+90 vs BTC", "",
          f"Float inconnu : {inconnus} token(s), hors tranches.", "",
          "| Tranche | n | Médiane J+90 | Part positive |", "|---|---|---|---|"]
    medianes_tranches = {}
    for _, _, etiq in TRANCHES_FLOAT:
        vals = tranches[etiq]
        if vals:
            medianes_tranches[etiq] = statistics.median(vals)
            L.append(f"| {etiq} | {len(vals)} | {fmt(medianes_tranches[etiq])} "
                     f"| {pct(sum(1 for v in vals if v > 0), len(vals))} |")
        else:
            L.append(f"| {etiq} | 0 | — | — |")
    L += [""]

    # (f) valeur du filtre
    plancher = [i for i in joints[90] if est_fantome(notes[i])]
    hp = hors_plancher[90]
    z_pl = sum(1 for i in plancher if valeurs[90][i] <= SEUIL_ZERO)
    z_hp = sum(1 for i in hp if valeurs[90][i] <= SEUIL_ZERO)
    L += ["## f. Valeur du filtre plancher", "",
          f"| Groupe | n | Médiane J+90 | Part à {SEUIL_ZERO:.0f} % ou pire |", "|---|---|---|---|",
          f"| Plancher (fantômes) | {len(plancher)} | "
          f"{fmt(statistics.median([valeurs[90][i] for i in plancher])) if plancher else '—'} "
          f"| {pct(z_pl, len(plancher))} ({z_pl}) |",
          f"| Hors plancher | {len(hp)} | "
          f"{fmt(statistics.median([valeurs[90][i] for i in hp])) if hp else '—'} "
          f"| {pct(z_hp, len(hp))} ({z_hp}) |", "",
          f"Sur les {zeros} tokens à {SEUIL_ZERO:.0f} % ou pire, {z_pl} sont des fantômes "
          f"({pct(z_pl, zeros)}) : c'est la part des quasi-zéros que le filtre aurait écartés.", ""]

    # lecture
    L += ["## Lecture", ""]
    cg, ch = res_g90["composite"], res_h90["composite"]
    if cg and ch:
        L.append(f"- Le composite sépare les tokens de **{cg['ecart']:+.1f} pts** sur l'ensemble, "
                 f"de **{ch['ecart']:+.1f} pts** hors plancher."
                 + (" Au-dessus du plancher, la grille ne classe pas : son pouvoir discriminant "
                    "vient de la séparation entre fantômes et projets réels."
                    if abs(ch["ecart"]) < 5 else ""))
    if res_g90.get("produit_live") and not res_h90.get("produit_live"):
        L.append("- `produit_live` n'est pas testable hors plancher : toutes ses notes "
                 "défavorables sont des fantômes. Son signal global vient entièrement du plancher.")
    stables = [c for c in ("traction_tge", "fees_vers_token", "backers")
               if res_h90.get(c) and res_h180.get(c)
               and res_h90[c]["ecart"] > 5 and res_h180[c]["ecart"] > 5]
    if stables:
        L.append("- Seul(s) critère(s) positif(s) au-dessus du plancher sur les deux fenêtres : "
                 + ", ".join(f"`{c}` ({res_h90[c]['ecart']:+.1f} pts à J+90, "
                             f"{res_h180[c]['ecart']:+.1f} à J+180)" for c in stables)
                 + ". Signal modeste.")
    fh, fh180 = res_h90.get("fees_vers_token"), res_h180.get("fees_vers_token")
    if fh and fh["ecart"] < -5:
        if fh180 and fh180["ecart"] > 5:
            L.append(f"- `fees_vers_token` hors plancher : {fh['ecart']:+.1f} pts à J+90 mais "
                     f"{fh180['ecart']:+.1f} à J+180. Le signe change d'une fenêtre à l'autre : "
                     f"pas de signal stable sur la capture de valeur.")
        else:
            L.append(f"- `fees_vers_token` s'inverse hors plancher ({fh['ecart']:+.1f} pts) : "
                     f"la capture de valeur promise au TGE n'a pas protégé les tokens.")
    if cg and res_g180.get("composite"):
        c180 = res_g180["composite"]
        texte = (f"- À J+180, le composite global donne {c180['ecart']:+.1f} pts "
                 f"(n={c180['n_fav'] + c180['n_defav']}) contre {cg['ecart']:+.1f} à J+90")
        if res_h180.get("composite"):
            h180 = res_h180["composite"]["ecart"]
            texte += f", et {h180:+.1f} pts hors plancher"
            if abs(h180) < 5:
                texte += (" : le plancher pèse encore plus à six mois (les fantômes finissent de "
                          "s'effondrer), mais au-dessus rien ne classe")
        L.append(texte + ".")
    ordre = [medianes_tranches.get(e) for _, _, e in TRANCHES_FLOAT]
    if all(m is not None for m in ordre):
        extremes, milieux = [ordre[0], ordre[3]], [ordre[1], ordre[2]]
        if all(a > b for a, b in zip(ordre, ordre[1:])):
            verdict = ("pas de cloche : la relation est monotone, plus le float initial est "
                       "élevé, plus la perf J+90 est mauvaise")
            n_bas = len(tranches["< 10 %"])
            if n_bas < 5:
                verdict += (f". La tranche < 10 % ne compte que {n_bas} token(s), mais la pente "
                            f"tient sur les trois autres tranches")
        elif min(milieux) > max(extremes):
            verdict = ("compatible avec l'hypothèse en cloche (les tranches du milieu battent "
                       "les deux extrêmes)")
        else:
            verdict = "non concluant pour la cloche"
        L.append(f"- Float en tranches : {verdict}. Effectifs faibles, à lire comme une tendance.")
    if plancher and hp:
        L.append(f"- Filtre plancher : {pct(z_pl, len(plancher))} de quasi-zéros dans le plancher "
                 f"contre {pct(z_hp, len(hp))} hors plancher. C'est ce que la grille sait faire.")
    L += ["", "## Limites", "",
          "- Une seule fenêtre de marché (TGE d'octobre 2025 à juin 2026), baissière pour les "
          "lancements : les écarts sont relatifs à ce régime.",
          "- Couverture de l'univers réel limitée (voir `controle_echantillon.md`), proxy de date "
          "de TGE corrigé seulement là où la notation a trouvé mieux (`overrides_tge.csv`, dont "
          "Baseline sur source secondaire).",
          "- Notes rétroactives en un seul passage, sans double notation ; près de la moitié en "
          "confiance basse, concentrée sur les fantômes.",
          "- Contrastes sur médianes de petits groupes : quelques extrêmes (ZSWAP, NEST, BTW) "
          "pèsent lourd.",
          "", "Scoring inchangé : le TODO float d'`audit/scoring.py` et le poids de la capture de "
          "valeur restent à décider sur la base de ce bilan."]

    fichier = RACINE / "backtest" / "bilan_passage_complet.md"
    fichier.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Écrit : {fichier.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
