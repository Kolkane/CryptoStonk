# Test d'entrée différée — achat à J+90 plutôt qu'au TGE

_Généré le 2026-09-30 par backtest/entree_differee.py._

## Règle de décision (posée avant les résultats)

> Médiane hors plancher >= 0 : entrée différée à creuser ; < 0 : pas d'achat post-TGE dans ce régime.

## Mesure

Population : tokens notés avec un prix à J+90 et à J+180 (morts entre J+90 et J+180 imputés à -100 % : 2). Perf J+90 -> J+180 vs BTC = (P180/P90) / (BTC180/BTC90) - 1.

| Groupe | n | Médiane | Part positive |
|---|---|---|---|
| tous | 64 | -26.2 % | 30 % (19) |
| hors plancher | 45 | -19.0 % | 33 % (15) |
| plancher | 19 | -39.2 % | 21 % (4) |

## Application de la règle

médiane hors plancher -19.0 % < 0 : **pas d'achat post-TGE dans ce régime**

Une seule fenêtre de marché (TGE d'octobre 2025 à juin 2026) : le verdict vaut pour ce régime.
