"""Forward cadré — rituel hebdomadaire (protocole : forward/protocole.md).

Par défaut : collecte des forums de gouvernance, export du prompt de clustering
de la semaine, puis checklist. Le journal tient une ligne par semaine, même vide :
3 semaines manquées sur 12 rendent le test invalide.

Usage : python forward/rituel.py                  # collecte + prompt + checklist
        python forward/rituel.py --checklist      # checklist seule
        python forward/rituel.py --journaliser [--semaine N]
            clôt la semaine courante (ou la précédente, délai de grâce d'une semaine) ;
            les semaines plus anciennes sans entrée sont notées « manquee ».
"""

import subprocess
import sys
from datetime import date

from enregistrer import (JOURNAL, REGISTRE, SEMAINES, ajouter_ligne, bornes_semaine, lire_csv,
                         semaine_de, verifier_protocole, verifier_registre, RACINE)

OBJECTIF_FICHES = 2


def fiches_de_la_semaine(n):
    return sum(1 for l in lire_csv(REGISTRE) if semaine_de(date.fromisoformat(l["date"])) == n)


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
    for ancienne in range(1, min(courante - 1, SEMAINES + 1)):
        if ancienne not in entrees and ancienne != n:
            ajouter_ligne(JOURNAL, [ancienne, date.today().isoformat(), 0, "manquee"])
            print(f"  semaine {ancienne} sans entrée : notée manquee")
    nb = fiches_de_la_semaine(n)
    statut = "faite" if nb else "vide"
    ajouter_ligne(JOURNAL, [n, date.today().isoformat(), nb, statut])
    print(f"Semaine {n} journalisée : {nb} fiche(s), statut {statut}.")


def checklist():
    aujourd_hui = date.today()
    n = semaine_de(aujourd_hui)
    if not 1 <= n <= SEMAINES:
        print(f"Hors des semaines du test (semaine {n}) : plus de rituel. Lecture : python forward/evaluer.py")
        return
    debut, fin = bornes_semaine(n)
    entrees = {int(l["semaine"]): l["statut"] for l in lire_csv(JOURNAL)}
    manquees = [s for s in range(1, SEMAINES + 1)
                if entrees.get(s) == "manquee" or (s <= n - 2 and s not in entrees)]
    print(f"\nRituel forward — semaine {n}/{SEMAINES} (du {debut} au {fin})")
    print(f"  fiches enregistrées cette semaine : {fiches_de_la_semaine(n)} / objectif {OBJECTIF_FICHES}")
    print(f"  semaines manquées : {len(manquees)} (test invalide à 3)"
          + (f" — semaine {n - 1} à journaliser" if n > 1 and (n - 1) not in entrees else ""))
    print("""
  1. Coller problemes/prompt_clustering.txt dans Claude.ai, la réponse dans problemes/carte_problemes.md
  2. Optionnel : python veille/nouveaux_projets.py puis python veille/croisement.py (solutions candidates)
  3. Retenir 1 ou 2 problèmes ; une fiche par solution concurrente quand il y en a plusieurs
  4. Copier forward/gabarit_fiche.md vers forward/fiches/fiche_<date du jour>_NN.md et la remplir
     (3 sources datées et distinctes, métrique DefiLlama avec sa valeur J0, condition d'invalidation)
  5. Le jour même : python forward/enregistrer.py forward/fiches/fiche_<date>_NN.md
  6. Condition d'invalidation atteinte : python forward/enregistrer.py --sortie <id> "<motif>"
  7. En fin de semaine, même sans fiche : python forward/rituel.py --journaliser""")


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
        for commande in (["problemes/collecte_forums.py"],
                         ["problemes/clustering.py", "--export-prompt", "--jours", "7"]):
            print(f"> python {' '.join(commande)}")
            subprocess.run([sys.executable, *commande], cwd=RACINE, check=False)
    checklist()


if __name__ == "__main__":
    main()
