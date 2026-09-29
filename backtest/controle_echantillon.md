# Contrôle qualité de l'échantillon — backtest v0

_Généré le 2026-09-29 par backtest/controler_echantillon.py — à relancer après toute extension de l'échantillon._

Rappel du cadrage : la couche 2 n'est pas reconstructible (pas d'historique de plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4, pas la détection de problèmes.

## 1. Complétude des fenêtres

- Tokens ciblés : **104** (TGE de 2025-10-03 à 2026-06-26, fenêtre effective 2025-10-02 -> 2026-06-30).
- Données complètes J+30/J+90/J+180 : **66**.

| Fenêtre | ok | pas encore écoulée | série arrêtée | trou de données | non mesurable |
|---|---|---|---|---|---|
| J+30 | 99 | 0 | 0 | 0 | 5 |
| J+90 | 95 | 0 | 0 | 4 | 5 |
| J+180 | 67 | 26 | 2 | 4 | 5 |

Tokens incomplets et diagnostic :

| Ticker | Verticale | TGE | Dernière cotation | Diagnostic |
|---|---|---|---|---|
| GENIUS | perps | 2026-04-13 | 2026-09-27 | J+180 : pas encore écoulée |
| O | dex | 2026-06-17 | 2026-09-27 | J+180 : pas encore écoulée |
| CAP | lending | 2026-06-26 | 2026-09-27 | J+180 : pas encore écoulée |
| RE | rwa | 2026-06-18 | 2026-09-27 | J+180 : pas encore écoulée |
| B | dex | 2026-05-08 | 2026-09-27 | J+180 : pas encore écoulée |
| ASSET | rwa | 2026-04-30 | 2026-09-27 | J+180 : pas encore écoulée |
| ZEST | lending | 2026-05-19 | 2026-09-27 | J+180 : pas encore écoulée |
| SLX | rendement | 2026-05-25 | 2026-09-27 | J+180 : pas encore écoulée |
| SODA | dex | 2025-12-01 | 2026-09-27 | J+180 : trou de données |
| SHARE | rwa | 2026-05-08 | 2026-09-27 | J+180 : pas encore écoulée |
| KAIO | rwa | 2026-05-06 | 2026-09-27 | J+180 : pas encore écoulée |
| NVPRIME | rwa | 2026-05-15 | 2026-09-27 | J+180 : pas encore écoulée |
| LV | perps | 2025-12-18 | 2026-09-28 | J+30 : non mesurable (TGE réel avant l'historique CG); J+90 : non mesurable (TGE réel avant l'historique CG); J+180 : non mesurable (TGE réel avant l'historique CG) |
| NEST | dex | 2026-04-13 | 2026-09-27 | J+180 : pas encore écoulée |
| RAM | dex | 2023-03-30 | 2026-09-28 | J+30 : non mesurable (TGE réel avant l'historique CG); J+90 : non mesurable (TGE réel avant l'historique CG); J+180 : non mesurable (TGE réel avant l'historique CG) |
| KSKD | lending | 2026-06-08 | 2026-09-27 | J+180 : pas encore écoulée |
| MEZO | lending | 2026-04-01 | 2026-09-27 | J+180 : trou de données |
| PEN | dex | 2023-03-13 | 2026-09-28 | J+30 : non mesurable (TGE réel avant l'historique CG); J+90 : non mesurable (TGE réel avant l'historique CG); J+180 : non mesurable (TGE réel avant l'historique CG) |
| NEST | lending | 2026-06-20 | 2026-09-27 | J+180 : pas encore écoulée |
| ALT | perps | 2026-05-17 | 2026-09-27 | J+180 : pas encore écoulée |
| LO0P | lending | 2026-05-10 | 2026-09-27 | J+180 : pas encore écoulée |
| TOPAZ | dex | 2026-06-15 | 2026-09-27 | J+180 : pas encore écoulée |
| HYBR | dex | 2026-06-22 | 2026-09-27 | J+180 : pas encore écoulée |
| ORBIT | dex | 2026-05-02 | 2026-09-27 | J+180 : pas encore écoulée |
| MAGPIE | lending | 2026-06-03 | 2026-09-27 | J+180 : pas encore écoulée |
| LABS | options | 2024-07-01 | 2026-09-28 | J+30 : non mesurable (TGE réel avant l'historique CG); J+90 : non mesurable (TGE réel avant l'historique CG); J+180 : non mesurable (TGE réel avant l'historique CG) |
| VICTORY | dex | 2026-04-18 | 2026-09-27 | J+180 : pas encore écoulée |
| PARQ | perps | 2026-06-07 | 2026-09-27 | J+180 : pas encore écoulée |
| REWARD | rendement | 2026-02-21 | 2026-09-27 | J+90 : trou de données; J+180 : trou de données |
| FFX | perps | 2026-04-01 | 2026-09-26 | J+180 : trou de données |
| NEXUS | perps | 2026-06-10 | 2026-09-25 | J+180 : pas encore écoulée |
| PUMPPERPS | perps | 2026-03-30 | 2026-09-23 | J+90 : trou de données |
| CRACKROCK | perps | 2026-04-29 | 2026-09-22 | J+90 : trou de données; J+180 : pas encore écoulée |
| TROVE | perps | 2026-01-20 | 2026-06-03 | J+90 : trou de données; J+180 : série arrêtée — **mort probable, fenêtres post-mortem imputées -100 %** |
| DAKS | rwa | 2026-04-15 | 2026-09-23 | J+180 : pas encore écoulée |
| OOOO | bridges | 2025-12-30 | 2026-06-10 | J+180 : série arrêtée — **mort probable, fenêtres post-mortem imputées -100 %** |
| STEAK | lsd_restaking | 2026-06-15 | 2026-09-13 | J+180 : pas encore écoulée — **mort probable, fenêtres post-mortem imputées -100 %** |
| SEAS | rendement | 2025-12-09 | 2026-09-28 | J+30 : non mesurable (TGE réel avant l'historique CG); J+90 : non mesurable (TGE réel avant l'historique CG); J+180 : non mesurable (TGE réel avant l'historique CG) |

## 2. Biais du survivant

CoinGecko déliste ou cesse de suivre les tokens morts : ils ne peuvent pas entrer dans l'échantillon (le pré-filtre parcourt les pièces encore cotées). L'échantillon sur-représente donc structurellement les survivants, et les moyennes brutes mentent.

- Morts identifiés **dans** l'échantillon (aucune cotation depuis 14 j) : **6** — IZKY, OOOO, RNGR, STEAK, TEA, TROVE. Leurs fenêtres postérieures à la mort sont **imputées à -100 %**, pas exclues ; leurs fenêtres vécues gardent la mesure.

- Univers estimé (DefiLlama /protocols) : **36** lancements de token sur la fenêtre, nos verticales — après exclusion de 46 fiches dont le token préexiste à la fenêtre (nouveaux produits de protocoles établis, pas des TGE), de 2 instruments, et dédoublonnage par symbole.
- Retrouvés dans l'échantillon : **8** (couverture 22 %). Absents : **28**, dont **17** avec TVL < 10 k$ aujourd'hui (morts/abandonnés probables : la masse invisible du biais).

Principaux absents (TVL actuelle) :

| Protocole | Symbole | Verticale | TVL |
|---|---|---|---|
| Sierra Protocol | SIERRA | rendement | 44 908 014 $ |
| Piku Finance | PIKU | rendement | 19 342 983 $ |
| Stobox | STBU | rwa | 13 952 059 $ |
| Ledgity Yield | LDY | rendement | 2 467 968 $ |
| Omnipair | OMFG | lending | 663 845 $ |
| DIEM Relay | DIEM | lsd_restaking | 609 080 $ |
| Pondo Protocol | PNDO | lsd_restaking | 566 899 $ |
| Everything | EV | lending | 370 022 $ |
| Pepu Bridge | PEPU | bridges | 300 270 $ |
| Ripe Protocol | RIPE | lending | 163 417 $ |
| Alvara | ALVA | rendement | 13 455 $ |
| Juris Protocol | JURIS | lending | 6 358 $ |
| PrimeFi | PRFI | lending | 4 319 $ |
| Defimarketplus | DMTP | rendement | 1 388 $ |
| Edel | EDEL | lending | 865 $ |

Limites de l'estimation : listedAt DefiLlama = date d'ajout au site, pas le TGE ; rapprochement par symbole/nom approximatif ; DefiLlama a son propre biais de survie (plus faible : les fiches mortes restent) ; /emissions (vraies dates de TGE) est passée en offre payante.

## 3. Distribution — perf relative à BTC à J+90

| Série | n | min | médiane | max | % > 0 |
|---|---|---|---|---|---|
| Survivants (mesuré) | 95 | -99.8 % | -56.7 % | +2702.1 % | 19 % |
| Avec morts imputés -100 % | 95 | -99.8 % | -56.7 % | +2702.1 % | 19 % |

Imputations à J+90 : (aucun ajout : les morts de l'échantillon ont vécu jusqu'à leur J+90 — leur -100 % mesuré y figure déjà le cas échéant)

Complément J+30 : médiane -34.1 %, 25 % positifs (99 mesurés).
Complément J+180 : médiane -64.4 %, 15 % positifs (67 mesurés) ; avec 3 mort(s) imputé(s) : médiane -66.6 %, 14 % positifs (70).

Médiane négative vs BTC : cohérent avec un marché de lancements difficile ; le biais du survivant rend la réalité encore un peu pire que ces chiffres.

## Verdict avant notation

- Noter en priorité les tokens avec J+90 disponible ou imputé (95 sur 104).
- Garder les 6 morts et leurs -100 % dans toutes les moyennes : les retirer regonflerait le biais.
- L'échantillon ne couvre qu'une partie de l'univers réel : toute conclusion du backtest est un ordre de grandeur, pas une preuve.
- Relancer ce contrôle après extension de l'échantillon ou nouvelle mesure.