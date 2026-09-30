# Backtest farming — protocole

_Figé le 2026-09-30, avant toute mesure ; arbitrages d'implémentation du même jour intégrés avant la première session. Toute modification après le premier calcul se note ici, datée, avec sa raison._

Cadrage : le passage complet a montré qu'acheter au TGE ou à J+90 perd contre BTC dans ce régime (`../bilan_passage_complet.md`, `../entree_differee.md`). La question devient : le farming pré-TGE rémunère-t-il le capital immobilisé ?

## Population

Tokens **hors plancher** joints à J+90 dans le bilan, ayant eu un **programme de points ou d'airdrop pré-TGE** (`programme_pretge=oui` dans les notes farming). Candidats présélectionnés par mots-clés dans les sources des notes (`candidats.csv`), confirmés ou infirmés par la notation farming.

## Valeur de sortie

`airdrop_pct_farmers × airdrop_unlock_tge_pct × supply totale × médiane des clôtures CoinGecko de J+1 à J+7`

La part vestée n'est pas comptée : c'est la valeur réalisable par un farmer qui vend dans la première semaine.

## Deux lectures séparées

- **Programmes TVL** : rendement annualisé = valeur de sortie / (TVL moyenne DefiLlama entre `debut_programme` et le TGE × durée en années).
- **Programmes volume** : valeur de sortie / volume cumulé pré-TGE (`volume_cumule_pretge_usd` des notes farming, source d'époque), en points de base. Lecture étiquetée **ordre de grandeur**.

## Questions

- **Q1** : médiane du rendement annualisé TVL, comparée à 5 %/an.
- **Q2** : `traction_tge` forte contre le reste, `backers` tier1 contre le reste (valeurs des notes existantes du backtest), pour chacune des deux lectures.

Q1 et Q2 portent sur les bases `tvl` et `volume` seulement. La base `mixte` est rapportée à part, en ligne de sensibilité TVL et volume. Aucun autre découpage.

## Précisions d'implémentation (figées avec le protocole)

- **Date du TGE** : `date_tge` de `../performances.csv`, overrides compris.
- **Supply** : `max_supply` CoinGecko si elle est définie ; sinon `total_supply` actuelle, signalée `supply_proxy` dans la sortie.
- **Clôtures J+1 à J+7** : dernier prix de chaque jour UTC de la série CoinGecko ; au moins 5 des 7 jours, sinon valeur de sortie non mesurable.
- **Base d'éligibilité** : `tvl` → lecture TVL ; `volume` → lecture volume ; `mixte` → les deux lectures, hors Q1 et Q2, en ligne de sensibilité ; `taches` → aucune lecture (pas de capital engagé).
- **Fenêtre** : de `debut_programme` inclus à la veille du TGE. Sans `debut_programme`, aucune lecture.
- **Couverture (lecture TVL)** : calculée seulement si la série DefiLlama couvre au moins 90 % des jours de la fenêtre.
- **Série TVL** : DefiLlama, protocole (parent agrégé le cas échéant) ou chaîne.
- **Volume** : `volume_cumule_pretge_usd` des notes farming, publié dans une source datée à 30 jours près du TGE et compté depuis une date à 30 jours près de `debut_programme`, sinon vide et pas de lecture. Pas d'API payante ; les séries de volume DefiLlama ne sont pas utilisées, et la série spot gratuite reste écartée pour les perps.
- **Correspondances DefiLlama** : `correspondances.csv` (vérifiées à la main), sinon `gecko_id` ; pas de repli par nom ou symbole.
