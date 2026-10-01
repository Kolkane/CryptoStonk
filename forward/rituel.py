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
        python forward/rituel.py --gagnants       # gagnants (addendums 01 à 04)
            dans forward/gagnants/AAAA-MM-JJ.md, frais sur 30 jours (DefiLlama) : 3 premiers par
            verticale du projet, 20 premiers toutes catégories (liste a), 3 premiers de chaque
            catégorie dont le leader dépasse 1 M$ (liste b), 10 premières chaînes (liste c) ;
            déclinaisons regroupées par parent.
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
CHAINES_LISTE_C = 10


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


def regrouper(protocoles, parents, cle):
    """Frais 30 j regroupés par parent DefiLlama (addendum 02), sous la clé cle(p) ; None = ignoré."""
    groupes = {}
    for p in protocoles:
        rubrique = cle(p)
        frais = p.get("total30d") or 0
        if rubrique is None or frais <= 0:
            continue
        parent = p.get("parentProtocol")
        nom, slug = ((parents.get(parent, parent), parent.split("#", 1)[1]) if parent
                     else (p.get("displayName") or p["name"], p["slug"]))
        groupe = groupes.setdefault((rubrique, slug), {"nom": nom, "slug": slug, "frais": 0,
                                                       "declinaisons": [], "categories": set()})
        groupe["frais"] += frais
        groupe["declinaisons"].append(p.get("displayName") or p["name"])
        groupe["categories"].add(p.get("category") or "?")
    return groupes


def tete(groupes, rubrique, n):
    return sorted((g for (r, _), g in groupes.items() if r == rubrique), key=lambda g: -g["frais"])[:n]


def gagnants():
    """Gagnants par frais sur 30 jours : verticales du projet (addendum 01), tout le périmètre
    DefiLlama (addendum 03), chaînes à part (addendum 04) ; déclinaisons regroupées par parent (addendum 02)."""
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
    # addendum 04 : les chaînes (protocolType « chain ») sortent des listes a et b et forment la liste c
    chaines = sorted((p for p in protocoles if p.get("protocolType") == "chain" and (p.get("total30d") or 0) > 0),
                     key=lambda p: -(p.get("total30d") or 0))[:CHAINES_LISTE_C]
    protocoles = [p for p in protocoles if p.get("protocolType") != "chain"]

    par_verticale = regrouper(protocoles, parents,
                              lambda p: vers_verticale.get((p.get("category") or "").lower()))
    tous = regrouper(protocoles, parents, lambda p: "tous")
    par_categorie = regrouper(protocoles, parents, lambda p: p.get("category") or "?")

    L = [f"# Gagnants — {aujourd_hui.isoformat()}", "",
         f"_Relevés le jour du rituel (semaine {semaine_de(aujourd_hui)}), DefiLlama, frais sur 30 jours. "
         f"Addendum 01 : {GAGNANTS_PAR_VERTICALE} premiers par verticale du projet (catégories : "
         f"config/verticals.yaml). Addendum 03 : 20 premiers toutes catégories (liste a), 3 premiers de "
         f"chaque catégorie DefiLlama dont le leader dépasse 1 M$ (liste b). Addendum 02 : déclinaisons "
         f"d'un même protocole regroupées sous leur parent DefiLlama. Addendum 04 : les chaînes sont exclues "
         f"des listes a et b et forment la liste c ({CHAINES_LISTE_C} premières par frais), utilisables comme "
         f"gagnant de référence avec le slug chain:Nom._", "",
         "Axes d'examen des limites : conception (transparence, custody, latence, collatéral, actifs), "
         "accès (chaîne, géographie, KYC, taille minimale), coût (frais, funding), risques (centralisation, "
         "oracle, validateurs), plaintes de ses utilisateurs. Hypothèses non confirmées : "
         "forward/backlog_hypotheses.md.", "",
         "# Verticales du projet (addendum 01)", ""]
    for verticale in verticales:
        L += [f"## {verticale}", ""]
        premiers = tete(par_verticale, verticale, GAGNANTS_PAR_VERTICALE)
        if not premiers:
            L += ["Aucun protocole avec des frais sur 30 jours dans cette verticale.", ""]
            continue
        L += ["| Rang | Protocole | Slug DefiLlama | Frais 30 j | Déclinaisons |", "|---|---|---|---|---|"]
        for rang, g in enumerate(premiers, 1):
            L.append(f"| {rang} | {g['nom']} | {g['slug']} | {compact_usd(g['frais'])} "
                     f"| {', '.join(sorted(g['declinaisons']))} |")
        L.append("")

    L += ["# Liste a — 20 premiers, toutes catégories (addendum 03)", "",
          "| Rang | Protocole | Slug DefiLlama | Catégories DefiLlama | Frais 30 j | Déclinaisons |",
          "|---|---|---|---|---|---|"]
    for rang, g in enumerate(tete(tous, "tous", 20), 1):
        L.append(f"| {rang} | {g['nom']} | {g['slug']} | {', '.join(sorted(g['categories']))} "
                 f"| {compact_usd(g['frais'])} | {', '.join(sorted(g['declinaisons']))} |")

    categories = sorted({r for r, _ in par_categorie},
                        key=lambda c: -tete(par_categorie, c, 1)[0]["frais"])
    retenues = [c for c in categories if tete(par_categorie, c, 1)[0]["frais"] > 1e6]
    L += ["", f"# Liste b — 3 premiers par catégorie DefiLlama, leader au-dessus de 1 M$ (addendum 03)", "",
          f"{len(retenues)} catégorie(s) retenue(s) sur {len(categories)}, classées par frais du leader.", "",
          "| Catégorie DefiLlama | Rang | Protocole | Slug DefiLlama | Frais 30 j |", "|---|---|---|---|---|"]
    for categorie in retenues:
        for rang, g in enumerate(tete(par_categorie, categorie, 3), 1):
            L.append(f"| {categorie} | {rang} | {g['nom']} | {g['slug']} | {compact_usd(g['frais'])} |")
    L += ["", f"# Liste c — {CHAINES_LISTE_C} chaînes aux frais les plus élevés (addendum 04)", "",
          "| Rang | Chaîne | Slug (gagnant de référence) | Frais 30 j |", "|---|---|---|---|"]
    for rang, c in enumerate(chaines, 1):
        nom = c.get("displayName") or c["name"]
        L.append(f"| {rang} | {nom} | chain:{c['name']} | {compact_usd(c.get('total30d') or 0)} |")
    L.append("")

    dossier = RACINE / "forward" / "gagnants"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"{aujourd_hui.isoformat()}.md"
    fichier.write_text("\n".join(L), encoding="utf-8")
    print(f"Écrit : {fichier.relative_to(RACINE).as_posix()} (à commiter avec le rituel) — "
          f"liste a : 20 protocoles, liste b : {len(retenues)} catégories, liste c : {len(chaines)} chaînes")


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
     en suivant forward/guide_fiches.md (choix de la métrique, 3 questions avant une conviction haute)
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
