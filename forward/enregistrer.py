"""Forward cadré — enregistrement des fiches dans le registre de hash.

Protocole : forward/protocole.md (PROTOCOLE FORWARD v1, commit 3456162).
Précisions d'implémentation : forward/precisions.md (commit b04c936).
Les deux fichiers sont vérifiés par empreinte avant toute opération.

Une fiche est figée à son enregistrement : son empreinte SHA-256 entre dans
forward/registre.csv. Avant tout enregistrement, le script vérifie le protocole
et toutes les fiches déjà enregistrées ; il refuse si l'une d'elles a changé.
Une fiche n'est enregistrable que le jour de sa date (J0 = jour d'enregistrement),
dans les semaines 1 à 12. Une correction passe par une nouvelle fiche dont le
champ « remplace » donne l'id de l'ancienne.

Les sorties de positions papier (condition d'invalidation atteinte) s'enregistrent
aussi ici, datées du jour même, dans forward/sorties.csv, qui cite la condition
d'invalidation de la fiche à côté du constat.

Usage : python forward/enregistrer.py forward/fiches/fiche_AAAA-MM-JJ_NN.md
        python forward/enregistrer.py --sortie <id_fiche> "<constat>"
        python forward/enregistrer.py --verifier
"""

import csv
import hashlib
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "forward"
DEBUT = date(2026, 10, 1)
SEMAINES = 12
PROTOCOLE_COMMIT = "34561621ec52d6a41468697a717d865953fc20c1"
PROTOCOLE_SHA256 = "8372f2e817661e66d21dc4383f5bf85541f3c14a86004850c17337b5e2ff16eb"
PRECISIONS_COMMIT = "b04c93678aca559d8ee56280cbbd1537ad0ff0eb"
PRECISIONS_SHA256 = "8202e896009689e941cc68abf8dbfcac6a278246d69a5677cf05867baec7738c"
REGISTRE = DOSSIER / "registre.csv"
JOURNAL = DOSSIER / "journal.csv"
SORTIES = DOSSIER / "sorties.csv"
TRACES = DOSSIER / "rituels"
MOTIF_FICHIER = re.compile(r"fiche_(\d{4}-\d{2}-\d{2})_(\d{2})\.md")
MOTIF_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def empreinte(chemin):
    """SHA-256 du fichier, fins de ligne normalisées (la conversion CRLF de git ne compte pas)."""
    return hashlib.sha256(Path(chemin).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def lire_csv(chemin):
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8-sig", newline="") as entree:
        return list(csv.DictReader(entree, delimiter=";"))


def ajouter_ligne(chemin, valeurs):
    with chemin.open("a", encoding="utf-8", newline="") as sortie:
        csv.writer(sortie, delimiter=";").writerow(valeurs)


def semaine_de(jour):
    return (jour - DEBUT).days // 7 + 1


def bornes_semaine(n):
    debut = DEBUT + timedelta(days=7 * (n - 1))
    return debut, debut + timedelta(days=6)


def verifier_protocole():
    """Protocole et précisions d'implémentation doivent être intacts depuis leur commit."""
    for fichier, attendu, commit in (("protocole.md", PROTOCOLE_SHA256, PROTOCOLE_COMMIT),
                                     ("precisions.md", PRECISIONS_SHA256, PRECISIONS_COMMIT)):
        if empreinte(DOSSIER / fichier) != attendu:
            sys.exit(f"REFUS : forward/{fichier} a changé depuis son commit {commit[:7]}. "
                     f"Il est figé.")


def trace(n):
    return TRACES / f"semaine_{n:02d}.log"


def dates_commit(chemin):
    """Dates de commit (AAAA-MM-JJ) d'un fichier ; [] si git est indisponible."""
    try:
        sortie = subprocess.run(["git", "log", "--format=%cs", "--", str(chemin)], cwd=RACINE,
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print("  attention : git indisponible, traces de rituel non vérifiables")
        return []
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def trace_commitee(n):
    """Vrai si la trace du rituel de la semaine n a été commitée pendant cette semaine."""
    debut, fin = bornes_semaine(n)
    return any(debut.isoformat() <= d <= fin.isoformat() for d in dates_commit(trace(n)))


def semaines_manquees(aujourd_hui):
    """Semaines terminées sans trace de rituel commitée pendant la semaine (journal ou non)."""
    terminees = [n for n in range(1, SEMAINES + 1) if bornes_semaine(n)[1] < aujourd_hui]
    return [n for n in terminees if not trace_commitee(n)]


def verifier_registre():
    """Arrêt si une fiche enregistrée manque ou a changé de hash."""
    problemes = []
    for ligne in lire_csv(REGISTRE):
        chemin = DOSSIER / ligne["fichier"]
        if not chemin.exists():
            problemes.append(f"{ligne['id']} : fichier {ligne['fichier']} absent")
        elif empreinte(chemin) != ligne["sha256"]:
            problemes.append(f"{ligne['id']} : hash modifié depuis l'enregistrement du {ligne['date']}")
    if problemes:
        sys.exit("REFUS : registre incohérent, fiches figées modifiées ou absentes :\n  "
                 + "\n  ".join(problemes))


def lire_fiche(chemin):
    texte = Path(chemin).read_text(encoding="utf-8")
    bloc = re.match(r"﻿?---\s*\n(.*?)\n---", texte, re.S)
    if not bloc:
        raise ValueError("bloc YAML d'en-tête (entre deux lignes ---) introuvable")
    return yaml.safe_load(bloc.group(1)) or {}


def texte(valeur):
    return "" if valeur is None else str(valeur).strip()


def nombre(valeur):
    try:
        return float(str(valeur).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def est_position_q2(fiche):
    """Position papier du protocole : adéquation forte, conviction haute, token coté à J0."""
    return (texte(fiche.get("adequation")) == "forte" and texte(fiche.get("conviction")) == "haute"
            and texte((fiche.get("solution") or {}).get("stade")) == "token_cote")


def valider(fiche, chemin, ids_enregistres, aujourd_hui):
    """(erreurs, avertissements)."""
    erreurs, avertissements = [], []
    nom = MOTIF_FICHIER.fullmatch(Path(chemin).name)
    if not nom:
        return ["nom de fichier attendu : fiche_AAAA-MM-JJ_NN.md"], []
    jour_fichier, numero = nom.groups()
    if texte(fiche.get("id")) != f"{jour_fichier}_{numero}":
        erreurs.append(f"id doit valoir {jour_fichier}_{numero}")
    if texte(fiche.get("date")) != jour_fichier:
        erreurs.append("date différente de celle du nom de fichier")
    if jour_fichier != aujourd_hui.isoformat():
        erreurs.append(f"une fiche s'enregistre le jour de sa date (aujourd'hui : {aujourd_hui})")
    semaine = semaine_de(date.fromisoformat(jour_fichier))
    if not 1 <= semaine <= SEMAINES:
        erreurs.append(f"hors des semaines 1 à {SEMAINES} du test")
    if texte(fiche.get("semaine")) != str(semaine):
        erreurs.append(f"semaine doit valoir {semaine}")
    remplace = texte(fiche.get("remplace"))
    if remplace and remplace not in ids_enregistres:
        erreurs.append(f"remplace : {remplace} n'est pas une fiche enregistrée")

    p = fiche.get("probleme") or {}
    for champ in ("id", "enonce", "qui_le_subit", "methode_estimation"):
        if not texte(p.get(champ)):
            erreurs.append(f"probleme.{champ} vide")
    sources = [s for s in (p.get("sources") or []) if isinstance(s, dict)]
    valides = [s for s in sources if MOTIF_DATE.fullmatch(texte(s.get("date"))) and texte(s.get("url"))]
    if len({texte(s["url"]) for s in valides}) < 3:
        erreurs.append("probleme.sources : au moins 3 sources datées (AAAA-MM-JJ) et distinctes")
    if any(texte(s.get("date")) > jour_fichier for s in valides):
        erreurs.append("probleme.sources : source datée après J0")
    mention = p.get("premiere_mention") or {}
    if not (MOTIF_DATE.fullmatch(texte(mention.get("date"))) and texte(mention.get("url"))):
        erreurs.append("probleme.premiere_mention : date et url requises")
    if nombre(p.get("argent_en_jeu_usd")) is None:
        erreurs.append("probleme.argent_en_jeu_usd : nombre requis")

    s = fiche.get("solution") or {}
    for champ in ("nom", "lien"):
        if not texte(s.get(champ)):
            erreurs.append(f"solution.{champ} vide")
    stade = texte(s.get("stade"))
    if stade not in ("pre_token", "token_cote"):
        erreurs.append("solution.stade : pre_token ou token_cote")
    if not MOTIF_DATE.fullmatch(texte(s.get("date_lancement"))):
        erreurs.append("solution.date_lancement : AAAA-MM-JJ")
    if stade == "token_cote" and not texte(s.get("id_coingecko")):
        erreurs.append("solution.id_coingecko requis pour un token coté")

    m = fiche.get("metrique") or {}
    remplis = [texte(m.get(c)) for c in ("nature", "slug_defillama", "valeur_j0")]
    if not any(remplis):
        avertissements.append("aucune métrique d'adoption : la fiche ne comptera pas pour Q1")
    else:
        if texte(m.get("nature")) not in ("tvl", "volume_dex", "frais"):
            erreurs.append("metrique.nature : tvl, volume_dex ou frais")
        if not texte(m.get("slug_defillama")):
            erreurs.append("metrique.slug_defillama vide")
        if nombre(m.get("valeur_j0")) is None:
            erreurs.append("metrique.valeur_j0 : nombre requis")

    part = nombre(fiche.get("part_captee_pct"))
    if part is None or not 0 <= part <= 100:
        erreurs.append("part_captee_pct : nombre entre 0 et 100")
    if texte(fiche.get("adequation")) not in ("forte", "moyenne", "faible"):
        erreurs.append("adequation : forte, moyenne ou faible")
    justification = [texte(x) for x in (fiche.get("justification_adequation") or []) if texte(x)]
    if len(justification) < 3:
        erreurs.append("justification_adequation : 3 lignes")
    if texte(fiche.get("conviction")) not in ("haute", "basse"):
        erreurs.append("conviction : haute ou basse")

    position = fiche.get("position") or {}
    type_position = texte(position.get("type"))
    if est_position_q2(fiche):
        if type_position != "achat_papier":
            erreurs.append("adéquation forte + conviction haute + token coté : position.type = achat_papier")
        elif texte(position.get("token")) != texte(s.get("id_coingecko")):
            erreurs.append("position.token doit être solution.id_coingecko")
    elif stade == "pre_token":
        if type_position not in ("suivi_pre_token", "aucune"):
            erreurs.append("solution pré-token : position.type = suivi_pre_token ou aucune")
    elif type_position != "aucune":
        erreurs.append("hors critères du protocole : position.type = aucune")
    for champ in ("condition_invalidation", "changerait_avis"):
        if not texte(fiche.get(champ)):
            erreurs.append(f"{champ} vide")
    return erreurs, avertissements


def enregistrer(chemin):
    verifier_protocole()
    verifier_registre()
    chemin = Path(chemin).resolve()
    registre = lire_csv(REGISTRE)
    ids = {l["id"] for l in registre}
    relatif = chemin.relative_to(DOSSIER).as_posix()
    if relatif in {l["fichier"] for l in registre}:
        sys.exit(f"REFUS : {relatif} est déjà enregistrée (une fiche enregistrée est figée).")
    try:
        fiche = lire_fiche(chemin)
    except (ValueError, yaml.YAMLError) as erreur:
        sys.exit(f"REFUS : fiche illisible ({erreur}).")
    if texte(fiche.get("id")) in ids:
        sys.exit(f"REFUS : l'id {fiche.get('id')} est déjà au registre.")
    aujourd_hui = date.today()
    erreurs, avertissements = valider(fiche, chemin, ids, aujourd_hui)
    for a in avertissements:
        print(f"  attention : {a}")
    if erreurs:
        sys.exit("REFUS :\n  " + "\n  ".join(erreurs))
    ajouter_ligne(REGISTRE, [texte(fiche["id"]), aujourd_hui.isoformat(), relatif, empreinte(chemin)])
    q2 = " — position papier Q2" if est_position_q2(fiche) else ""
    print(f"Enregistrée : {fiche['id']} (semaine {fiche['semaine']}, adéquation "
          f"{fiche['adequation']}{q2}). Fiche désormais figée.")


def enregistrer_sortie(identifiant, motif):
    verifier_protocole()
    verifier_registre()
    ligne = next((l for l in lire_csv(REGISTRE) if l["id"] == identifiant), None)
    if not ligne:
        sys.exit(f"REFUS : {identifiant} n'est pas au registre.")
    fiche = lire_fiche(DOSSIER / ligne["fichier"])
    if not est_position_q2(fiche):
        sys.exit(f"REFUS : {identifiant} n'est pas une position papier.")
    if any(l["id_fiche"] == identifiant for l in lire_csv(SORTIES)):
        sys.exit(f"REFUS : {identifiant} est déjà sortie.")
    if not texte(motif):
        sys.exit("REFUS : constat requis (ce qui a déclenché la condition d'invalidation).")
    condition = " ".join(texte(fiche.get("condition_invalidation")).split())
    ajouter_ligne(SORTIES, [identifiant, date.today().isoformat(), condition, texte(motif)])
    print(f"Sortie enregistrée : {identifiant}, clôture CoinGecko du {date.today().isoformat()}.\n"
          f"  condition de la fiche : {condition}")


def main():
    arguments = sys.argv[1:]
    if arguments[:1] == ["--verifier"]:
        verifier_protocole()
        verifier_registre()
        print(f"Protocole et précisions intacts, {len(lire_csv(REGISTRE))} fiche(s) au registre, toutes intactes.")
    elif arguments[:1] == ["--sortie"] and len(arguments) == 3:
        enregistrer_sortie(arguments[1], arguments[2])
    elif len(arguments) == 1 and not arguments[0].startswith("--"):
        enregistrer(arguments[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
