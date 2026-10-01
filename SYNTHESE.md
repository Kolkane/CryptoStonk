# Synthèse de la phase backtest

_Close le 2026-09-30. Échantillon : TGE d'octobre 2025 à juin 2026 sur nos verticales, performances mesurées contre BTC._

**Phase backtest close : plus de nouveau test sur cet échantillon (risque de faux positif par tests répétés).**

## Quatre verdicts

Portée : cette phase a testé une grille générique appliquée au TGE (produit, traction, float, capture de valeur, backers), puis la rétention de TVL après le TGE comme proxy d'adéquation (verdict 4, sans signal). Elle n'a pas testé le cœur de la thèse : la découverte des problèmes remontés par le marché, et la confrontation entre la taille d'un problème et la part qu'une solution en capte. Ce cœur est non testé, pas réfuté.

**1. La grille d'audit écarte les quasi-zéros, elle ne désigne pas les gagnants.** ([bilan](backtest/bilan_passage_complet.md))
99 tokens notés, 87 mesurés à J+90. En niveau : médiane −59,9 % contre BTC à J+90, 18 % seulement battent BTC. Le score composite sépare les tokens de +15,5 points sur l'ensemble, mais de +1,5 point une fois les profils fantômes retirés (−1,7 à J+180). Le profil fantôme (ni produit, ni traction, ni backers) compte 44 % de quasi-zéros (−90 % ou pire) contre 8 % au-dessus, et regroupe 69 % des quasi-zéros.

**2. Acheter après le TGE ne rattrape pas la baisse.** ([bilan](backtest/entree_differee.md))
Entre J+90 et J+180, la médiane hors plancher est de −19,0 % contre BTC (45 tokens, 33 % positifs). La règle posée avant les résultats s'applique : pas d'achat post-TGE dans ce régime.

**3. Le rendement du farming n'est pas mesurable sur données publiques.** ([bilan](backtest/farming/bilan_farming.md))
Sur 24 programmes pré-TGE, 5 seulement publient ensemble la date de début, la part des farmers et le déblocage. Il en sort 2 lectures TVL pour un seuil de 8 : la question reste ouverte, ni validée ni rejetée.

**4. La rétention de TVL après le TGE ne distingue pas les tokens.** ([protocole et résultats](backtest/retention/))
Sur 23 tokens mesurables de J+30 à J+180, les tokens à forte rétention (TVL de J+23 à J+30 rapportée à celle de J-30 à J-1) font −37,5 % contre BTC, ceux à faible rétention −33,6 % : écart de −3,9 points. Selon la règle figée avant calcul (protocole commit `acc6845`, résultats commit `44dc2d0`), pas de signal.

**Lecture d'ensemble** : dans cette fenêtre, aucun proxy de qualité testé (grille, entrée différée, farming, rétention) ne distingue les tokens au-dessus des fantômes ; le signal le plus net est le float bas, un signal d'offre.

## Usage validé de la grille v1

- **À utiliser comme filtre** : exclure un candidat si `produit_live=non` ET `traction_tge=nulle` ET `backers=aucun`. C'est la seule partie validée par le backtest (`python audit/scoring.py --controle-backtest`).
- **Pas comme classeur** : les indices float (malus au-dessus de 20 %, plus fort au-dessus de 50 %) et traction orientent la lecture d'un dossier, ils ne trient pas les candidats entre eux. Capture de valeur et backers sont affichés sans poids : leur signal a été nul ou instable.

## Enseignements qualitatifs

- **Les points ne sont pas un contrat.** Sur 30 programmes, trois ont changé de nature avant le TGE : Cap a payé en stablecoin puis réduit la récompense de 65 %, Ranger a converti les points en simple droit d'achat, Katana a gardé les tokens farmés non transférables sans publier les montants.
- **Biais de publication.** Les programmes mesurables sont ceux qui publient leurs chiffres, c'est-à-dire surtout les gros dossiers (Lighter, Meteora, Kinetiq, Turtle, Genius). Un rendement calculé sur eux décrirait les meilleurs cas, pas le farming typique : même avec plus de lectures, l'échantillon resterait biaisé vers le haut.
- **Une seule fenêtre de marché, baissière pour les lancements.** Tous les écarts et verdicts sont relatifs à ce régime. Ils ne disent rien d'un cycle où les lancements montent.

## Décision en attente : forward cadré ou pause

**Forward cadré** : suivre en temps réel les prochains lancements avec le filtre v1, sous un protocole écrit avant de commencer (population, critères, durée, nombre minimal de cas, règle de décision). Il supprime deux limites du backtest : les notes sont prises au moment des faits, sans reconstitution, et les données de farming sont relevées par nous (date d'entrée, capital engagé, allocation reçue) au lieu de dépendre de ce que les projets publient. Il coûte une notation régulière et des mois avant le premier verdict.

**Pause** : garder la routine quotidienne (thermomètre, veille, croisement) et le filtre v1 pour l'hygiène des dossiers, sans nouvelle mesure. Reprendre quand le régime change (signal du thermomètre) ou quand une nouvelle question justifie l'effort.

Dans les deux cas, aucun résultat de cette phase ne justifie aujourd'hui une position.

## Forward cadré en cours

Décision prise le 2026-10-01 : forward cadré. Protocole [forward/protocole.md](forward/protocole.md), figé au commit `3456162` avant toute fiche ; 12 semaines de rituel (jusqu'au 2026-12-23), lecture Q1 au plus tôt le 2027-03-23, Q2 90 puis 180 jours après la dernière position.
