# CryptoStonk

Moteur de détection précoce de cryptos à fort potentiel. Outil interne pour notre propre capital : il structure la décision et réduit le hasard, il ne supprime pas le risque. Rien ici n'est une boule de cristal ni un conseil d'investissement — chaque position reste un pari dimensionné en conséquence.

## Le pari

Sur chaque cycle, les plus grosses performances viennent de projets qui résolvent un problème concret laissé ouvert par les leaders du moment (Aster reprenant Hyperliquid en cachant les ordres pour empêcher la chasse aux stops, DRV ouvrant les options onchain aux institutionnels). Ces problèmes s'expriment publiquement — X, Reddit, Discord, forums de gouvernance — bien avant que la solution ne soit valorisée par le marché. On cherche donc le problème d'abord, la solution ensuite.

## Les 4 couches

| Couche | Rôle | Où |
|---|---|---|
| 1. Thermomètre de cycle | Niveau d'euphorie du marché (rang App Store de Coinbase, funding, stablecoins, Google Trends) → dimensionner le risque | `cycle/` |
| 2. Détection de problèmes | Plaintes récurrentes par verticale, collecte forums automatique + captures X manuelles, clustering IA quotidien → carte vivante des problèmes | `problemes/` |
| 3. Mapping des solutions | Veille des nouveaux protocoles (DefiLlama en v0), croisée avec la carte des problèmes | `veille/` |
| 4. Audit et timing | Checklist structurée + scoring par candidat : produit, traction, tokenomics, valorisation, distribution, catalyseurs | `audit/` |

Les sorties générées (JSON, CSV, dashboard) vont dans `data/`, hors dépôt. L'inbox des plaintes et la carte des problèmes sont versionnées : c'est la mémoire de travail commune.

## Installation

Python 3.10+.

```
pip install -r requirements.txt
# Optionnel (Google Trends, lib fragile) : pip install pytrends
```

Le clustering (couche 2) appelle l'API Claude (modèle `claude-haiku-4-5-20251001`). Identifiants, au choix :

- `setx ANTHROPIC_API_KEY "sk-ant-…"` puis rouvrir le terminal ;
- ou un profil `ant auth login`, détecté automatiquement par le SDK.

## Routine quotidienne (~15 min + lecture)

```
python cycle/thermometre.py          # où en est le cycle
python veille/nouveaux_projets.py    # quoi de neuf sur DefiLlama
python problemes/collecte_forums.py  # sujets récents des forums de gouvernance
#  → coller vos captures X/Discord du jour dans problemes/inbox/AAAA-MM-JJ.md
python problemes/clustering.py       # régénère la carte des problèmes
python dashboard/generer.py          # data/dashboard.html
```

## Couche 2 : alimenter l'inbox

**Automatique** — `collecte_forums.py` interroge l'API JSON publique des 5 forums Discourse listés dans [config/sources.yaml](config/sources.yaml) et verse les sujets récents dans l'inbox, dédoublonnés.

**Manuel (X, Discord, Reddit)** — coller les plaintes repérées dans `problemes/inbox/AAAA-MM-JJ.md`, un bloc par plainte :

```markdown
## @compte | perps | 2026-09-27
Texte de la plainte, verbatim de préférence.
```

La verticale et la date sont optionnelles. Les fichiers préfixés `_` sont ignorés (modèles). La liste des 30 comptes X de référence vit dans `config/sources.yaml` — les entrées fournies sont des exemples à remplacer par la vôtre. Pas de scraping X automatisé en v0 : API payante et CGU restrictives, la collecte reste semi-manuelle.

Premier essai sans rien écrire : `python problemes/clustering.py --dry-run` (3 plaintes, carte affichée en console).

## Couche 4 : auditer un candidat

1. Copier `audit/candidats/_gabarit.yaml` → `audit/candidats/<slug>.yaml` et le remplir (checklist détaillée : [audit/gabarit_audit.md](audit/gabarit_audit.md)).
2. `python audit/scoring.py audit/candidats/<slug>.yaml`

Le scoring v0 est une grille de lecture, pas une vérité : il doit être backtesté sur les ~50 derniers lancements avant d'avoir voix au chapitre. Le meilleur point d'entrée est souvent avant le token (farming de points) — le champ `points_farming` du gabarit est là pour ça.

## Garde-fous

Résoudre un problème ne suffit pas : beaucoup de projets utiles vont à zéro. Le modèle intègre la distribution (écosystème, backers), les tokenomics et les catalyseurs, pas seulement le product-market fit. Et on n'achète pas au sommet de l'euphorie : le thermomètre dimensionne le risque, la carte des problèmes désigne les cibles, l'audit tranche.

## Feuille de route

- **Semaine 2+** : levées VC (RootData), calendrier des TGE, croisement automatique carte des problèmes × nouveaux projets, backtest du scoring sur les 50 derniers lancements.
- Les seuils du thermomètre sont des heuristiques v0, à recalibrer sur données historiques.
