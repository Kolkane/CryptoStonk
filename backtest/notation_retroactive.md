# Notation rétroactive — grille couche 4 au TGE (backtest v0)

Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de plaintes
à J-90), donc ce backtest valide uniquement la grille d'audit couche 4, pas la
détection de problèmes.

Chaque token de `echantillon.csv` se note sur les critères couche 4 **tels qu'ils
étaient au moment du TGE** — jamais avec l'information d'aujourd'hui (le biais de
rétrospective ruinerait le backtest). Sources d'époque uniquement : annonces X du
projet, articles de listing, docs versionnées, TVL DefiLlama à la date, levées
annoncées avant TGE.

## Les 5 critères (état au TGE)

| Critère | Valeurs | Comment juger au TGE |
|---|---|---|
| `produit_live` | oui / testnet / non | Le produit était-il utilisable en mainnet avant le token ? |
| `traction_tge` | forte / moyenne / faible / nulle | TVL, volume, utilisateurs AVANT le TGE. Farming de points sans usage réel = faible. |
| `float_initial_pct` | nombre | % du supply en circulation au listing. |
| `fees_vers_token` | oui / partiel / non | Capture de valeur (frais, burn, droits) active — ou annoncée de façon engageante — au TGE. |
| `backers` | tier1 / tier2 / aucun | Investisseurs annoncés avant TGE. tier1 = fonds majeurs, exchange, écosystème puissant. |

Plus une colonne `confiance` (haute / basse) : basse dès que les sources d'époque
sont introuvables ou contradictoires — mieux vaut une case honnêtement incertaine
qu'un chiffre inventé.

## Protocole de session — prompts générés, jamais copiés à la main

Les prompts de session sont générés par `python backtest/preparer_sessions.py`
(`backtest/sessions/session_NN.txt`, lots de 10 en ordre aléatoire à graine fixe).
**Ne collez pas des lignes d'`echantillon.csv` dans Claude.ai** : ce fichier contient
la FDV, et les sessions générées ne contiennent aucune donnée de marché — uniquement
id_coingecko, ticker, nom, date de TGE et catégorie. Les performances restent dans
`performances.csv` et n'entrent jamais dans une session.

Variante premier passage : `--stratifie` sélectionne 40 tokens (10 meilleurs J+90
vs BTC, 10 pires — morts imputés compris —, 20 au sort), remélangés, en 4 sessions
`strat_NN.txt`. **La stratification interdit toute lecture en taux de réussite
absolu : elle mesure uniquement la capacité de la grille à discriminer.**

Déroulé :

1. Coller le contenu de `backtest/sessions/<session>.txt` dans Claude.ai.
2. Relire la réponse : tout fait d'époque douteux → `confiance=basse` ; corriger à la
   main ce que vous savez de première main.
3. Coller le CSV validé dans `backtest/notes/<même nom>.csv` (en-tête compris) :

```
id_coingecko;ticker;produit_live;traction_tge;float_initial_pct;fees_vers_token;backers;confiance;sources
```

L'`id_coingecko` est indispensable : deux tokens de l'échantillon partagent un même
ticker, la jointure avec les performances se fait par id.

## Exploitation (au fil des sessions rendues)

`python backtest/analyser_notation.py` joint `backtest/notes/*.csv` aux performances :
par critère puis sur un score composite v0, perf médiane J+90 relative à BTC des
tokens favorablement vs défavorablement notés. Question posée à chaque critère :
sépare-t-il réellement les gagnants des perdants ? C'est ce résultat, et lui seul,
qui recalibrera les poids de `audit/scoring.py` (posés à la main, non validés).
