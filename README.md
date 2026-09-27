# CryptoStonk

Moteur de détection précoce de cryptos à fort potentiel. Outil interne pour notre propre capital : il structure la décision et réduit le hasard, il ne supprime pas le risque. Rien ici n'est une boule de cristal ni un conseil d'investissement — chaque position reste un pari dimensionné en conséquence.

## Le pari

Sur chaque cycle, les plus grosses performances viennent de projets qui résolvent un problème concret laissé ouvert par les leaders du moment (Aster reprenant Hyperliquid en cachant les ordres pour empêcher la chasse aux stops, DRV ouvrant les options onchain aux institutionnels). Ces problèmes s'expriment publiquement — X, Reddit, Discord, forums de gouvernance — bien avant que la solution ne soit valorisée par le marché. On cherche donc le problème d'abord, la solution ensuite.

## Les 4 couches

| Couche | Rôle | Où |
|---|---|---|
| 1. Thermomètre de cycle | Niveau d'euphorie du marché (rang App Store de Coinbase, funding, stablecoins, Google Trends) → dimensionner le risque | `cycle/` |
| 2. Détection de problèmes | Plaintes récurrentes par verticale, collecte forums automatique + captures X manuelles, clustering hebdo via Claude.ai (API en option) → carte vivante des problèmes | `problemes/` |
| 3. Mapping des solutions | Veille des nouveaux protocoles (DefiLlama en v0), croisée avec la carte des problèmes (croisement local v0 + affinage hebdo Claude.ai) | `veille/` |
| 4. Audit et timing | Checklist structurée + scoring par candidat : produit, traction, tokenomics, valorisation, distribution, catalyseurs | `audit/` |

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

1. Copier `audit/candidats/_gabarit.yaml` → `audit/candidats/<slug>.yaml` et le remplir (checklist détaillée : [audit/gabarit_audit.md](audit/gabarit_audit.md)).
2. `python audit/scoring.py audit/candidats/<slug>.yaml`

Le scoring v0 est une grille de lecture, pas une vérité : il doit être backtesté sur les ~50 derniers lancements avant d'avoir voix au chapitre. Le meilleur point d'entrée est souvent avant le token (farming de points) — le champ `points_farming` du gabarit est là pour ça.

## Backtest (couche 4 uniquement)

**Cadrage honnête : la couche 2 n'est pas reconstructible (pas d'historique de plaintes à J-90), donc ce backtest valide uniquement la grille d'audit couche 4, pas la détection de problèmes.**

1. `python backtest/constituer_echantillon.py` — tokens listés entre septembre 2025 et juin 2026 sur nos verticales, via l'API CoinGecko gratuite (throttle intégré, comptez 30-60 min ; le script reprend où il s'était arrêté si ça casse). Proxys assumés, étiquetés dans le CSV : date de TGE = première cotation CoinGecko ; FDV initiale approchée ; instruments (parts de fonds, LST, wrappés) écartés par marqueurs. Limite de l'offre gratuite : historique plafonné à 365 j, donc la fenêtre effective démarre au plus tôt ~12 mois en arrière (affichée au lancement). Sortie : `backtest/echantillon.csv` (cible ≥ 50 tokens).
2. `python backtest/mesurer_performance.py` — performance à J+30 / J+90 / J+180, absolue et relative à BTC sur la même fenêtre. Sortie : `backtest/performances.csv`.
3. Notation rétroactive **à la main**, par sessions de 10 tokens via Claude.ai : grille, garde-fous anti-rétrospective et prompt dans [backtest/notation_retroactive.md](backtest/notation_retroactive.md) ; résultats cumulés dans `backtest/notation.csv`.
4. Exploitation : corrélation notation × performance relative BTC (J+90 en tête) pour recalibrer les poids de `audit/scoring.py`.

Clé CoinGecko optionnelle : `COINGECKO_API_KEY` (offre démo) si le sans-clé rate-limite trop.

## Garde-fous

Résoudre un problème ne suffit pas : beaucoup de projets utiles vont à zéro. Le modèle intègre la distribution (écosystème, backers), les tokenomics et les catalyseurs, pas seulement le product-market fit. Et on n'achète pas au sommet de l'euphorie : le thermomètre dimensionne le risque, la carte des problèmes désigne les cibles, l'audit tranche.

## Feuille de route

- **Semaine 2+** : levées VC (RootData), calendrier des TGE, exploitation du backtest couche 4 (corrélation notation × performances → recalibrer `audit/scoring.py`), backtest du croisement (l'heuristique v0 n'est pas validée).
- Les seuils du thermomètre sont des heuristiques v0, à recalibrer sur données historiques.
