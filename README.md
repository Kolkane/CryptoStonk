# CryptoStonk

> **Phase backtest close : lire d'abord la [synthèse](SYNTHESE.md).**

Moteur de détection précoce de cryptos à fort potentiel. Outil interne pour notre propre capital : il structure la décision et réduit le hasard, il ne supprime pas le risque. Rien ici n'est une boule de cristal ni un conseil d'investissement — chaque position reste un pari dimensionné en conséquence.

## Le pari

Sur chaque cycle, les plus grosses performances viennent de projets qui résolvent un problème concret laissé ouvert par les leaders du moment (Aster reprenant Hyperliquid en cachant les ordres pour empêcher la chasse aux stops, DRV ouvrant les options onchain aux institutionnels). Ces problèmes s'expriment publiquement — X, Reddit, Discord, forums de gouvernance — bien avant que la solution ne soit valorisée par le marché. On cherche donc le problème d'abord, la solution ensuite.

## Les 4 couches

| Couche | Rôle | Où |
|---|---|---|
| 1. Thermomètre de cycle | Niveau d'euphorie du marché (rang App Store de Coinbase, funding, stablecoins, Google Trends) → dimensionner le risque | `cycle/` |
| 2. Détection de problèmes | Plaintes récurrentes par verticale, collecte forums automatique + captures X manuelles, clustering hebdo via Claude.ai (API en option) → carte vivante des problèmes | `problemes/` |
| 3. Mapping des solutions | Veille des nouveaux protocoles (DefiLlama en v0), croisée avec la carte des problèmes (croisement local v0 + affinage hebdo Claude.ai) | `veille/` |
| 4. Audit et timing | Checklist structurée + scoring v1 : filtre d'exclusion validé sur backtest, indices float/traction non validés comme classeur | `audit/` |

Les sorties générées (JSON, CSV, dashboard) vont dans `data/`, hors dépôt. L'inbox des plaintes et la carte des problèmes sont versionnées : c'est la mémoire de travail commune.

## Installation

Python 3.10+.

```
pip install -r requirements.txt
# Optionnel (Google Trends, lib fragile) : pip install pytrends
```

Aucune clé API n'est requise en v0 : le clustering se fait à la main via Claude.ai (voir la routine hebdo). Le mode API du clustering est optionnel (modèle `claude-haiku-4-5-20251001`) ; pour l'utiliser : `setx ANTHROPIC_API_KEY "sk-ant-…"` puis rouvrir le terminal, ou un profil `ant auth login`.

## Routine

**Quotidien (~10 min + lecture)**

```
python cycle/thermometre.py          # où en est le cycle
python veille/nouveaux_projets.py    # quoi de neuf sur DefiLlama
python veille/croisement.py          # candidats : nouveaux protocoles × carte des problèmes
python problemes/collecte_forums.py  # sujets récents des forums de gouvernance
#  → coller vos captures X/Discord du jour dans problemes/inbox/AAAA-MM-JJ.md
python dashboard/generer.py          # data/dashboard.html
```

**Hebdo — clustering et affinage manuels via Claude.ai**

```
python problemes/clustering.py --export-prompt --jours 7
#  → coller problemes/prompt_clustering.txt dans Claude.ai
#  → coller la réponse telle quelle dans problemes/carte_problemes.md
python veille/croisement.py --export-prompt
#  → coller veille/prompt_croisement.txt dans Claude.ai
#  → coller la réponse dans veille/correspondances_affinees.csv
python dashboard/generer.py          # met à jour problèmes et candidats
```

## Couche 2 : alimenter l'inbox

**Automatique** — `collecte_forums.py` interroge l'API JSON publique des 5 forums Discourse listés dans [config/sources.yaml](config/sources.yaml) et verse les sujets récents dans l'inbox, dédoublonnés.

**Manuel (X, Discord, Reddit)** — coller les plaintes repérées dans `problemes/inbox/AAAA-MM-JJ.md`, un bloc par plainte :

```markdown
## @compte | perps | 2026-09-27
Texte de la plainte, verbatim de préférence.
```

La verticale et la date sont optionnelles. Les fichiers préfixés `_` sont ignorés (modèles). La liste des 30 comptes X de référence vit dans `config/sources.yaml` — les entrées fournies sont des exemples à remplacer par la vôtre. Pas de scraping X automatisé en v0 : API payante et CGU restrictives, la collecte reste semi-manuelle.

**Clustering hebdo (v0, manuel)** — `python problemes/clustering.py --export-prompt --jours 7` génère `problemes/prompt_clustering.txt` (règles d'analyse + format attendu + plaintes numérotées) : le coller dans Claude.ai, puis coller la réponse telle quelle dans `problemes/carte_problemes.md` — le dashboard lit ce fichier directement. Le fichier prompt est régénéré à chaque export (hors dépôt).

**Mode API (optionnel)** — `python problemes/clustering.py` fait la même analyse via l'API et écrit la carte tout seul ; premier essai sans rien écrire avec `--dry-run` (3 plaintes, carte en console). Nécessite des identifiants (voir Installation).

## Couche 3 : croiser veille et problèmes

`python veille/croisement.py` croise le dernier CSV de veille avec `problemes/carte_problemes.md` — en local, sans LLM : même verticale + mots-clés communs (minuscules, stopwords FR/EN). Force du match : **fort** (verticale + ≥ 2 mots-clés), **moyen** (+ 1), **faible** (verticale seule). Sortie versionnée : `veille/correspondances.csv`, colonne `methode` = « v0 heuristique non backtestée » — une présélection à trier, pas un verdict. Le dashboard en tire la section « Candidats » (matchs forts et moyens, pré-TGE d'abord).

**Affinage hebdo (Claude.ai)** — `python veille/croisement.py --export-prompt` génère `veille/prompt_croisement.txt` (hors dépôt) : Claude.ai confirme/infirme chaque correspondance forte ou moyenne, réponse à coller dans `veille/correspondances_affinees.csv` (hors dépôt).

## Couche 4 : auditer un candidat

1. Copier `audit/candidats/_gabarit.yaml` → `audit/candidats/<slug>.yaml` et le remplir (checklist détaillée : [audit/gabarit_audit.md](audit/gabarit_audit.md)). Les champs `produit_live`, `traction_tge`, `backers` et `float_initial_pct` reprennent le vocabulaire des notes du backtest.
2. `python audit/scoring.py audit/candidats/<slug>.yaml`

Scoring v1 (la v0 pondérée reste dans l'historique git) :

- **Étape 1, filtre d'exclusion — validé sur backtest (87 TGE d'octobre 2025 à juin 2026).** Exclu si `produit_live=non` ET `traction_tge=nulle` ET `backers=aucun`. Dans le backtest, ce profil compte 44 % de quasi-zéros (−90 % ou pire vs BTC à J+90) contre 8 % au-dessus, et regroupe 69 % des quasi-zéros.
- **Étape 2, indices — non validés comme classeur.** Float initial ≥ 50 % : malus ; 20-50 % : malus léger ; en dessous : neutre. Traction forte ou moyenne : bonus. Capture de valeur et backers : affichés, poids nul. Au-dessus du plancher, la grille ne sépare pas les gagnants (composite +1,5 pt) : les indices orientent la lecture, ils ne trient pas.
- Acheter à J+90 plutôt qu'au TGE ne rattrape pas la baisse dans ce régime : médiane hors plancher −19,0 % vs BTC entre J+90 et J+180.

Détails : [backtest/bilan_passage_complet.md](backtest/bilan_passage_complet.md) et [backtest/entree_differee.md](backtest/entree_differee.md). `python audit/scoring.py --controle-backtest` vérifie que le filtre exclut exactement les 25 profils plancher du bilan. L'entrée avant le token (farming de points) n'a pas pu être mesurée sur données publiques : [backtest/farming/bilan_farming.md](backtest/farming/bilan_farming.md).

## Backtest (couche 4 uniquement)

**Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4, pas la détection de problèmes.**

1. `python backtest/constituer_echantillon.py` — tokens listés entre septembre 2025 et juin 2026 sur nos verticales, via l'API CoinGecko gratuite (throttle intégré, comptez 30-60 min ; le script reprend où il s'était arrêté si ça casse). Proxys assumés, étiquetés dans le CSV : date de TGE = première cotation CoinGecko ; FDV initiale approchée ; instruments (parts de fonds, LST, wrappés) écartés par marqueurs. Limite de l'offre gratuite : historique plafonné à 365 j, donc la fenêtre effective démarre au plus tôt ~12 mois en arrière (affichée au lancement). Sortie : `backtest/echantillon.csv` (cible ≥ 50 tokens).
2. `python backtest/mesurer_performance.py` — performance à J+30 / J+90 / J+180, absolue et relative à BTC sur la même fenêtre. Sortie : `backtest/performances.csv`. Les vraies dates de TGE trouvées en notation se déclarent dans `backtest/overrides_tge.csv` (`id_coingecko;date_tge_reelle;source`) et priment sur le proxy « première cotation CoinGecko » ; `--ids <id1,id2>` re-mesure les seuls tokens corrigés et fusionne. Si la vraie date précède l'historique CoinGecko du token (plafond 365 j), ses fenêtres passent « non mesurable » plutôt que d'être mesurées depuis la première cotation.
3. `python backtest/preparer_sessions.py` — génère les prompts de session (`backtest/sessions/session_NN.txt`, lots de 10 en ordre aléatoire à graine fixe), **sans aucune performance dedans** : uniquement id, ticker, nom, date de TGE, catégorie, avec la consigne de noter l'état au TGE et de ne jamais chercher le prix. Variante `--stratifie` : 40 tokens (10 meilleurs J+90 vs BTC, 10 pires — morts imputés compris —, 20 au sort), remélangés, en 4 sessions `strat_NN.txt` pour un premier passage. **La stratification interdit toute lecture en taux de réussite absolu : elle mesure uniquement la capacité de la grille à discriminer.** Coller chaque prompt dans Claude.ai, la réponse CSV dans `backtest/notes/<même nom>.csv` (grille et garde-fous : [backtest/notation_retroactive.md](backtest/notation_retroactive.md)).
4. `python backtest/analyser_notation.py` — joint les notes aux performances : par critère puis sur un score composite, perf médiane J+90 vs BTC des tokens favorablement vs défavorablement notés, avec deux contrôles de robustesse (haute confiance, hors plancher). Passage complet terminé : 99 tokens notés, 87 joints à J+90. Les purges unitaires (instruments, ids recyclés) sont tracées dans `backtest/exclusions.csv`.
5. `python backtest/bilan_passage.py` → [backtest/bilan_passage_complet.md](backtest/bilan_passage_complet.md) : lecture absolue (médiane −59,9 % vs BTC à J+90, 18 % de tokens positifs), contrastes J+90 et J+180 global et hors plancher, float en tranches, valeur du filtre. Verdict : la grille écarte les quasi-zéros, elle ne désigne pas les gagnants. **Recalibrage fait : scoring v1** (voir Couche 4).
6. `python backtest/entree_differee.py` → [backtest/entree_differee.md](backtest/entree_differee.md) : acheter à J+90 plutôt qu'au TGE ne rattrape pas la baisse (médiane hors plancher −19,0 % vs BTC entre J+90 et J+180). Règle posée avant les résultats : pas d'achat post-TGE dans ce régime.
7. **Backtest farming, clos — non concluant sur données publiques** ([bilan](backtest/farming/bilan_farming.md)) : le capital immobilisé avant le TGE est-il rémunéré ? Protocole figé avant toute mesure dans [backtest/farming/protocole.md](backtest/farming/protocole.md). `python backtest/farming/preparer.py` liste les candidats, vérifie la couverture DefiLlama et génère les sessions `farm_NN.txt` (`--sessions-seules` pour les régénérer sans réseau) ; réponses dans `backtest/farming/notes/farm_NN.csv`, puis `python backtest/farming/calculer.py`.

Clé CoinGecko optionnelle : `COINGECKO_API_KEY` (offre démo) si le sans-clé rate-limite trop.

## Garde-fous

Résoudre un problème ne suffit pas : beaucoup de projets utiles vont à zéro. Le modèle intègre la distribution (écosystème, backers), les tokenomics et les catalyseurs, pas seulement le product-market fit. Et on n'achète pas au sommet de l'euphorie : le thermomètre dimensionne le risque, la carte des problèmes désigne les cibles, l'audit tranche.

## Feuille de route

- **Fait** : backtest couche 4 (passage complet, bilan, entrée différée négative) et recalibrage en scoring v1.
- **Clos** : backtest farming, non concluant sur données publiques (2 lectures TVL mesurables pour un seuil de 8) : [backtest/farming/bilan_farming.md](backtest/farming/bilan_farming.md).
- **Ensuite** : levées VC (RootData), calendrier des TGE, backtest du croisement (l'heuristique v0 n'est pas validée).
- Les seuils du thermomètre sont des heuristiques v0, à recalibrer sur données historiques.
