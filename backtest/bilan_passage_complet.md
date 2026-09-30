# Bilan du passage complet de notation — backtest v0

_Généré le 2026-09-30 par backtest/bilan_passage.py. Lecture seule : notes, échantillon et scoring inchangés._

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4, pas la détection de problèmes.

## a. État

- Échantillon final : **99** tokens (après purges tracées dans `exclusions.csv`).
- Notes : **116** ids notés, dont 17 purgés depuis (hors échantillon) ; tokens de l'échantillon sans note : **0**.
- Jointes à une perf J+90 : **87** (dont 48 en confiance basse) ; à J+180 : **66**.
- Non mesurables (vraie date de TGE avant l'historique CoinGecko) : **8** — B, LABS, LV, MANTRA, PEN, RAM, SEAS, SODA.
- Morts (aucune cotation depuis 14 j) : **6** — IZKY, OOOO, RNGR, STEAK, TEA, TROVE ; imputations à -100 % : 0 à J+90, 3 à J+180.

## b. Lecture absolue — perf J+90 vs BTC, toutes les jointes

Le passage complet couvre l'échantillon mesurable entier : la lecture en niveau est légitime, contrairement au seul passage stratifié.

- n = **87**
- Médiane : **-59.9 %**
- Part positive (bat BTC) : **18 %** (16)
- Part à -90 % ou pire : **18 %** (16)

## c. Contrastes J+90 vs BTC (médianes, favorable vs défavorable)

### Global (n = 87)

| Critère | Favorable | Défavorable | Écart |
|---|---|---|---|
| produit_live | -53.0 % (n=60) | -83.9 % (n=25) | +30.9 pts |
| traction_tge | -43.3 % (n=36) | -67.2 % (n=51) | +23.9 pts |
| fees_vers_token | -60.0 % (n=18) | -60.4 % (n=49) | +0.4 pts |
| backers | -55.6 % (n=22) | -68.3 % (n=46) | +12.7 pts |
| float_initial_pct | -63.4 % (n=41) | +4.8 % (n=9) | -68.2 pts |
| **composite** (split à +0.0) | -53.0 % (n=38) | -68.5 % (n=41) | +15.5 pts |

### Hors plancher (n = 62, 25 profils fantômes exclus : produit_live=non ET traction_tge=nulle ET backers=aucun ; split à la médiane du sous-ensemble)

| Critère | Favorable | Défavorable | Écart |
|---|---|---|---|
| produit_live | — | — | incalculable (un groupe vide) |
| traction_tge | -43.3 % (n=36) | -58.7 % (n=26) | +15.4 pts |
| fees_vers_token | -60.0 % (n=14) | -39.1 % (n=30) | -20.9 pts |
| backers | -55.6 % (n=22) | -63.4 % (n=21) | +7.8 pts |
| float_initial_pct | -55.8 % (n=26) | +4.8 % (n=9) | -60.6 pts |
| **composite** (split à +1.0) | -50.0 % (n=30) | -51.4 % (n=24) | +1.5 pts |

## d. Mêmes contrastes à J+180 (là où la mesure existe)

### Global (n = 66)

| Critère | Favorable | Défavorable | Écart |
|---|---|---|---|
| produit_live | -55.9 % (n=43) | -94.6 % (n=21) | +38.7 pts |
| traction_tge | -50.0 % (n=26) | -84.3 % (n=40) | +34.3 pts |
| fees_vers_token | -63.2 % (n=14) | -73.2 % (n=37) | +10.0 pts |
| backers | -55.9 % (n=17) | -90.8 % (n=35) | +34.9 pts |
| float_initial_pct | -75.5 % (n=31) | -9.9 % (n=7) | -65.6 pts |
| **composite** (split à -0.5) | -51.6 % (n=33) | -90.8 % (n=33) | +39.2 pts |

### Hors plancher (n = 45)

| Critère | Favorable | Défavorable | Écart |
|---|---|---|---|
| produit_live | — | — | incalculable (un groupe vide) |
| traction_tge | -50.0 % (n=26) | -60.5 % (n=19) | +10.5 pts |
| fees_vers_token | -34.6 % (n=10) | -55.9 % (n=21) | +21.2 pts |
| backers | -55.9 % (n=17) | -55.5 % (n=14) | -0.4 pts |
| float_initial_pct | -53.8 % (n=18) | -9.9 % (n=7) | -43.9 pts |
| **composite** (split à +1.0) | -55.9 % (n=21) | -54.2 % (n=19) | -1.7 pts |

## e. Float initial en tranches — perf J+90 vs BTC

Float inconnu : 37 token(s), hors tranches.

| Tranche | n | Médiane J+90 | Part positive |
|---|---|---|---|
| < 10 % | 3 | +11.3 % | 100 % |
| 10-20 % | 11 | -45.0 % | 18 % |
| 20-50 % | 14 | -53.0 % | 14 % |
| >= 50 % | 22 | -87.0 % | 5 % |

## f. Valeur du filtre plancher

| Groupe | n | Médiane J+90 | Part à -90 % ou pire |
|---|---|---|---|
| Plancher (fantômes) | 25 | -83.9 % | 44 % (11) |
| Hors plancher | 62 | -53.0 % | 8 % (5) |

Sur les 16 tokens à -90 % ou pire, 11 sont des fantômes (69 %) : c'est la part des quasi-zéros que le filtre aurait écartés.

## Lecture

- Le composite sépare les tokens de **+15.5 pts** sur l'ensemble, de **+1.5 pts** hors plancher. Au-dessus du plancher, la grille ne classe pas : son pouvoir discriminant vient de la séparation entre fantômes et projets réels.
- `produit_live` n'est pas testable hors plancher : toutes ses notes défavorables sont des fantômes. Son signal global vient entièrement du plancher.
- Seul(s) critère(s) positif(s) au-dessus du plancher sur les deux fenêtres : `traction_tge` (+15.4 pts à J+90, +10.5 à J+180). Signal modeste.
- `fees_vers_token` hors plancher : -20.9 pts à J+90 mais +21.2 à J+180. Le signe change d'une fenêtre à l'autre : pas de signal stable sur la capture de valeur.
- À J+180, le composite global donne +39.2 pts (n=66) contre +15.5 à J+90, et -1.7 pts hors plancher : le plancher pèse encore plus à six mois (les fantômes finissent de s'effondrer), mais au-dessus rien ne classe.
- Float en tranches : pas de cloche : la relation est monotone, plus le float initial est élevé, plus la perf J+90 est mauvaise. La tranche < 10 % ne compte que 3 token(s), mais la pente tient sur les trois autres tranches. Effectifs faibles, à lire comme une tendance.
- Filtre plancher : 44 % de quasi-zéros dans le plancher contre 8 % hors plancher. C'est ce que la grille sait faire.

## Limites

- Une seule fenêtre de marché (TGE d'octobre 2025 à juin 2026), baissière pour les lancements : les écarts sont relatifs à ce régime.
- Couverture de l'univers réel limitée (voir `controle_echantillon.md`), proxy de date de TGE corrigé seulement là où la notation a trouvé mieux (`overrides_tge.csv`, dont Baseline sur source secondaire).
- Notes rétroactives en un seul passage, sans double notation ; près de la moitié en confiance basse, concentrée sur les fantômes.
- Contrastes sur médianes de petits groupes : quelques extrêmes (ZSWAP, NEST, BTW) pèsent lourd.

Scoring inchangé : le TODO float d'`audit/scoring.py` et le poids de la capture de valeur restent à décider sur la base de ce bilan.
