"""Forward cadré — rituel hebdomadaire (protocole : forward/protocole.md,
précisions : forward/precisions.md).

Par défaut : collecte des forums de gouvernance, export du prompt de clustering
de la semaine, trace horodatée dans forward/rituels/semaine_NN.log (semaines du
protocole), commit immédiat de cette seule trace, puis checklist. La date de
commit de la trace fait foi : une semaine sans trace commitée pendant la semaine
est manquée, même journalisée après coup ; 3 semaines manquées rendent le test
invalide. Le script ne pousse pas : git push reste à faire.

Usage : python forward/rituel.py                  # rituel complet + trace commitée
        python forward/rituel.py --checklist      # checklist seule, sans trace
        python forward/rituel.py --gagnants       # gagnants par verticale (addendum 01)
            3 protocoles aux frais les plus élevés sur 30 jours par verticale (DefiLlama),
            dans forward/gagnants/AAAA-MM-JJ.md ; les déclinaisons d'un même protocole
            (V2, V3, perps…) sont regroupées sous leur parent DefiLlama (addendum 02).
        python forward/rituel.py --journaliser [--semaine N]
            journalise la semaine courante (après commit de sa trace) ou la précédente ;
            les semaines plus anciennes sans entrée sont notées « manquee ».
"""

import subprocess
import sys
from datetime import date, datetime, timezone

import requests
import yaml

from enregistrer import (JOURNAL, RACINE, REGISTRE, SEMAINES, TRACES, ajouter_ligne, bornes_semaine,
                         lire_csv, semaine_de, semaines_manquees, trace, trace_commitee,
                         verifier_protocole, verifier_registre)

OBJECTIF_FICHES = 2
LLAMA = "https://api.llama.fi"
ENTETES = {"User-Agent": "CryptoStonk/0.1 (outil interne)"}
GAGNANTS_PAR_VERTICALE = 3


def fiches_de_la_semaine(n):
    return sum(1 for l in lire_csv(REGISTRE) if semaine_de(date.fromisoformat(l["date"])) == n)


def ecrire_trace(n, codes):
    """Ajoute une ligne horodatée à la trace de la semaine et commite ce seul fichier."""
    TRACES.mkdir(parents=True, exist_ok=True)
    chemin = trace(n)
    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with chemin.open("a", encoding="utf-8") as sortie:
        sortie.write(f"{horodatage} ; semaine {n} ; " + " ; ".join(f"{k}={v}" for k, v in codes.items())
                     + f" ; fiches_semaine={fiches_de_la_semaine(n)}\n")
    relatif = chemin.relative_to(RACINE).as_posix()
    try:
        subprocess.run(["git", "add", relatif], cwd=RACINE, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Trace rituel forward semaine {n:02d}", "--", relatif],
                       cwd=RACINE, check=True, capture_output=True)
        print(f"Trace commitée : {relatif} (git push à faire)")
    except (OSError, subprocess.CalledProcessError) as erreur:
        print(f"ATTENTION : commit de la trace impossible ({erreur}). Commitez {relatif} "
              f"cette semaine : seule la date de commit fait foi.")


def compact_usd(montant):
    for seuil, suffixe in ((1e9, " Md$"), (1e6, " M$"), (1e3, " k$")):
        if montant >= seuil:
            return f"{montant / seuil:.1f}".replace(".", ",") + suffixe
    return f"{montant:.0f} $"


def gagnants():
    """Les 3 protocoles aux frais les plus élevés sur 30 jours dans chaque verticale du projet."""
    verifier_protocole()
    aujourd_hui = date.today()
    if not 1 <= semaine_de(aujourd_hui) <= SEMAINES:
        sys.exit(f"Hors des semaines du test (semaine {semaine_de(aujourd_hui)}).")
    verticales = yaml.safe_load((RACINE / "config" / "verticals.yaml").read_text(encoding="utf-8"))
    vers_verticale = {c.lower(): v for v, categories in verticales.items() for c in categories}
    try:
        protocoles = requests.get(f"{LLAMA}/overview/fees", headers=ENTETES, timeout=120, params={
            "excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyFees"}).json()["protocols"]
        parents = {p["id"]: p["name"] for p in requests.get(
            f"{LLAMA}/lite/protocols2", headers=ENTETES, timeout=120).json().get("parentProtocols") or []}
    except (requests.RequestException, ValueError, KeyError) as erreur:
        sys.exit(f"DefiLlama indisponible ({erreur}) : relancer plus tard dans la journée.")

    regroupes = {}
    for p in protocoles:
        verticale = vers_verticale.get((p.get("category") or "").lower())
        frais = p.get("total30d") or 0
        if not verticale or frais <= 0:
            continue
        parent = p.get("parentProtocol")
        nom, slug = ((parents.get(parent, parent), parent.split("#", 1)[1]) if parent
                     else (p.get("displayName") or p["name"], p["slug"]))
        groupe = regroupes.setdefault((verticale, slug), {"nom": nom, "slug": slug, "frais": 0,
                                                         "declinaisons": []})
        groupe["frais"] += frais
        groupe["declinaisons"].append(p.get("displayName") or p["name"])

    L = [f"# Gagnants par verticale — {aujourd_hui.isoformat()}", "",
         f"_Relevés le jour du rituel (semaine {semaine_de(aujourd_hui)}), DefiLlama. Règle de l'addendum 01 : "
         f"les {GAGNANTS_PAR_VERTICALE} protocoles aux frais les plus élevés sur 30 jours dans chaque "
         f"verticale du projet. Frais d'un protocole = somme de ses déclinaisons DefiLlama classées dans "
         f"la verticale ; catégories par verticale : config/verticals.yaml._", "",
         "Axes d'examen des limites : conception (transparence, custody, latence, collatéral, actifs), "
         "accès (chaîne, géographie, KYC, taille minimale), coût (frais, funding), risques (centralisation, "
         "oracle, validateurs), plaintes de ses utilisateurs. Hypothèses non confirmées : "
         "forward/backlog_hypotheses.md.", ""]
    for verticale in verticales:
        tete = sorted((g for (v, _), g in regroupes.items() if v == verticale),
                      key=lambda g: -g["frais"])[:GAGNANTS_PAR_VERTICALE]
        L += [f"## {verticale}", ""]
        if not tete:
            L += ["Aucun protocole avec des frais sur 30 jours dans cette verticale.", ""]
            continue
        L += ["| Rang | Protocole | Slug DefiLlama | Frais 30 j | Déclinaisons |", "|---|---|---|---|---|"]
        for rang, g in enumerate(tete, 1):
            L.append(f"| {rang} | {g['nom']} | {g['slug']} | {compact_usd(g['frais'])} "
                     f"| {', '.join(sorted(g['declinaisons']))} |")
        L.append("")
    dossier = RACINE / "forward" / "gagnants"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"{aujourd_hui.isoformat()}.md"
    fichier.write_text("\n".join(L), encoding="utf-8")
    print(f"Écrit : {fichier.relative_to(RACINE).as_posix()} (à commiter avec le rituel)")


def journaliser(n):
    verifier_protocole()
    verifier_registre()
    courante = semaine_de(date.today())
    if n not in (courante, courante - 1) or not 1 <= n <= SEMAINES:
        sys.exit(f"REFUS : seule la semaine courante ({courante}) ou la précédente se journalise, "
                 f"dans les semaines 1 à {SEMAINES}.")
    entrees = {int(l["semaine"]) for l in lire_csv(JOURNAL)}
    if n in entrees:
        sys.exit(f"REFUS : la semaine {n} est déjà journalisée.")
    commitee = trace_commitee(n)
    if n == courante and not commitee:
        sys.exit(f"REFUS : aucune trace de rituel commitée pour la semaine {n}. "
                 f"Lancez python forward/rituel.py avant de journaliser.")
    for ancienne in range(1, min(courante - 1, SEMAINES + 1)):
        if ancienne not in entrees and ancienne != n:
            ajouter_ligne(JOURNAL, [ancienne, date.today().isoformat(), 0, "manquee"])
            print(f"  semaine {ancienne} sans entrée : notée manquee")
    nb = fiches_de_la_semaine(n)
    statut = ("faite" if nb else "vide") if commitee else "manquee"
    ajouter_ligne(JOURNAL, [n, date.today().isoformat(), nb, statut])
    print(f"Semaine {n} journalisée : {nb} fiche(s), statut {statut}"
          + ("" if commitee else " (pas de trace de rituel commitée pendant la semaine)") + ".")


def checklist():
    aujourd_hui = date.today()
    n = semaine_de(aujourd_hui)
    if not 1 <= n <= SEMAINES:
        print(f"Hors des semaines du test (semaine {n}) : plus de rituel. Lecture : python forward/evaluer.py")
        return
    debut, fin = bornes_semaine(n)
    manquees = semaines_manquees(aujourd_hui)
    print(f"\nRituel forward — semaine {n}/{SEMAINES} (du {debut} au {fin})")
    print(f"  trace du rituel commitée cette semaine : {'oui' if trace_commitee(n) else 'non'}")
    print(f"  fiches enregistrées cette semaine : {fiches_de_la_semaine(n)} / objectif {OBJECTIF_FICHES}")
    print(f"  semaines manquées : {len(manquees)}{' ' + str(manquees) if manquees else ''} "
          f"(test invalide à 3)")
    print("""
  1. Coller problemes/prompt_clustering.txt dans Claude.ai, la réponse dans problemes/carte_problemes.md
  2. Dérivation (addendum 01) : python forward/rituel.py --gagnants, examiner les limites des gagnants
     sur les 5 axes ; hypothèse non confirmée par 3 sources -> forward/backlog_hypotheses.md
  3. Optionnel : python veille/nouveaux_projets.py puis python veille/croisement.py (solutions candidates)
  4. Vérifier si une solution pré-token suivie a lancé son token (suivi descriptif manuel, hors verdict)
  5. Retenir 1 ou 2 problèmes ; une fiche par solution concurrente quand il y en a plusieurs
  6. Copier forward/gabarit_fiche.md vers forward/fiches/fiche_<date du jour>_NN.md et la remplir
     (origine, 3 sources datées et distinctes, métrique DefiLlama avec sa valeur J0, invalidation)
  7. Le jour même : python forward/enregistrer.py forward/fiches/fiche_<date>_NN.md
  8. Condition d'invalidation atteinte : python forward/enregistrer.py --sortie <id> "<constat>"
  9. En fin de semaine, même sans fiche : python forward/rituel.py --journaliser, puis git push""")


def main():
    arguments = sys.argv[1:]
    if arguments[:1] == ["--gagnants"]:
        gagnants()
        return
    if arguments[:1] == ["--journaliser"]:
        n = semaine_de(date.today())
        if arguments[1:2] == ["--semaine"] and len(arguments) == 3:
            n = int(arguments[2])
        journaliser(n)
        return
    if arguments[:1] != ["--checklist"]:
        verifier_protocole()
        n = semaine_de(date.today())
        if not 1 <= n <= SEMAINES:
            sys.exit(f"Hors des semaines du test (semaine {n}) : plus de rituel.")
        codes = {}
        for nom, commande in (("collecte_forums", ["problemes/collecte_forums.py"]),
                              ("export_prompt", ["problemes/clustering.py", "--export-prompt", "--jours", "7"])):
            print(f"> python {' '.join(commande)}")
            codes[nom] = subprocess.run([sys.executable, *commande], cwd=RACINE, check=False).returncode
        ecrire_trace(n, codes)
    checklist()


if __name__ == "__main__":
    main()
