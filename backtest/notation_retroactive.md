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

## Sortie attendue : `backtest/notation.csv`

Une ligne par token, point-virgule :

```
ticker;produit_live;traction_tge;float_initial_pct;fees_vers_token;backers;confiance;sources
```

## Protocole de session Claude.ai — 10 tokens par session

1. Copier le prompt ci-dessous, puis 10 lignes de `echantillon.csv` à la suite.
2. Relire la réponse : tout fait d'époque douteux → `confiance=basse` ; corriger à la main
   ce que vous savez de première main.
3. Coller les lignes validées à la suite de `backtest/notation.csv`.

Prompt à coller :

```
Tu notes des tokens crypto À LA DATE DE LEUR TGE, pour un backtest. Pour chaque token
ci-dessous, remplis la grille telle qu'elle était AU MOMENT DU LISTING, jamais avec
l'information d'aujourd'hui. Cherche des sources d'époque (annonces, articles de
listing, docs, TVL DefiLlama à la date). Si un fait d'époque reste incertain,
écris confiance=basse et explique en deux mots dans sources.

Réponds UNIQUEMENT en CSV point-virgule, en-tête compris, une ligne par token :
ticker;produit_live;traction_tge;float_initial_pct;fees_vers_token;backers;confiance;sources

Valeurs permises : produit_live oui|testnet|non ; traction_tge forte|moyenne|faible|nulle ;
fees_vers_token oui|partiel|non ; backers tier1|tier2|aucun ; confiance haute|basse.

Tokens à noter (ticker;nom;id_coingecko;verticale;categorie_cg;date_tge;…) :
<coller ici 10 lignes de backtest/echantillon.csv>
```

## Exploitation (une fois notation.csv rempli)

Croiser `notation.csv` × `performances.csv` — la performance relative à BTC à J+90
en tête. Question posée à chaque critère : sépare-t-il réellement les gagnants des
perdants de l'échantillon ? C'est ce résultat, et lui seul, qui recalibrera les
poids de `audit/scoring.py` (aujourd'hui posés à la main, non validés).
