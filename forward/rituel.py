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
        python forward/rituel.py --journaliser [--semaine N]
            journalise la semaine courante (après commit de sa trace) ou la précédente ;
            les semaines plus anciennes sans entrée sont notées « manquee ».
"""

import subprocess
import sys
from datetime import date, datetime, timezone

from enregistrer import (JOURNAL, RACINE, REGISTRE, SEMAINES, TRACES, ajouter_ligne, bornes_semaine,
                         lire_csv, semaine_de, semaines_manquees, trace, trace_commitee,
                         verifier_protocole, verifier_registre)

OBJECTIF_FICHES = 2


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
  2. Optionnel : python veille/nouveaux_projets.py puis python veille/croisement.py (solutions candidates)
  3. Vérifier si une solution pré-token suivie a lancé son token (suivi descriptif manuel, hors verdict)
  4. Retenir 1 ou 2 problèmes ; une fiche par solution concurrente quand il y en a plusieurs
  5. Copier forward/gabarit_fiche.md vers forward/fiches/fiche_<date du jour>_NN.md et la remplir
     (3 sources datées et distinctes, métrique DefiLlama avec sa valeur J0, condition d'invalidation)
  6. Le jour même : python forward/enregistrer.py forward/fiches/fiche_<date>_NN.md
  7. Condition d'invalidation atteinte : python forward/enregistrer.py --sortie <id> "<constat>"
  8. En fin de semaine, même sans fiche : python forward/rituel.py --journaliser, puis git push""")


def main():
    arguments = sys.argv[1:]
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
