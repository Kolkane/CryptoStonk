# Test de rétention — protocole

_Figé le 2026-09-30, committé seul avant l'écriture du calcul._

Question : la solution garde-t-elle ses utilisateurs quand les incitations s'arrêtent ? La TVL qui reste un mois après le TGE sert de proxy de l'adéquation entre le problème et la solution, la thèse centrale non testée par la phase backtest (`../../SYNTHESE.md`).

## Population

Tokens hors plancher joints à J+90 dans le bilan du passage complet, avec une série TVL DefiLlama couvrant au moins 90 % des jours de J-30 à J+30 autour du TGE. Correspondance DefiLlama : `../farming/correspondances.csv` (vérifiées à la main), sinon `gecko_id` d'un protocole, d'un protocole parent ou d'une chaîne.

## Mesures

- **Rétention** : TVL moyenne de J+23 à J+30, divisée par la TVL moyenne de J-30 à J-1.
- **Issue principale** : perf vs BTC de J+30 à J+180.
- **Issue secondaire** : perf vs BTC de J+30 à J+90.

## Contraste

Split à la médiane de rétention ; médiane de l'issue de chaque côté ; n affichés.

## Règle de décision

- Moins de 20 tokens mesurables sur l'issue principale : **non concluant**.
- Écart d'au moins +20 points en faveur de la forte rétention sur l'issue principale : **signal à creuser**.
- Sinon : **pas de signal**.

L'issue secondaire est rapportée mais ne décide pas.

## Précisions d'implémentation (figées avec le protocole)

- **Date du TGE** : `date_tge` de `../performances.csv`, overrides compris.
- **Fenêtre de couverture** : de J-30 à J+30 inclus, soit 61 jours ; un jour est couvert s'il porte un point de la série TVL.
- **TVL pré-TGE nulle** (moyenne J-30 à J-1 égale à 0) : rétention indéfinie, token non mesurable.
- **Perf de J+30 à J+N vs BTC** : (1 + rel_N) / (1 + rel_30) − 1, à partir des perfs relatives de `../performances.csv` ; J+30 doit être mesuré. Un token mort avant J+N est imputé à −100 % (convention du backtest).
- **Split** : médiane de rétention calculée sur les tokens mesurables pour l'issue considérée ; les tokens exactement à la médiane sont écartés.
- **Écart** : médiane de l'issue côté forte rétention moins médiane côté faible rétention.
