# Bilan du backtest farming

_Clos le 2026-09-30. Protocole figé avant mesure : [protocole.md](protocole.md). Résultats bruts : [resultats.md](resultats.md). Couverture : `python backtest/farming/calculer.py --couverture`._

## Verdict

**Non concluant sur données publiques.** Le protocole demandait au moins 8 lectures TVL pour conclure ; les notes n'en permettent que 2. Q1 est déclarée non concluante et Q2 n'est pas calculée. La question « le farming pré-TGE rémunère-t-il le capital immobilisé ? » reste ouverte : ni validée, ni rejetée.

## Couverture finale

30 candidats notés (tokens hors plancher joints à J+90 dont les notes évoquaient des points ou un airdrop), dont 24 avec un programme pré-TGE confirmé.

| Étape | Lignes |
|---|---|
| Éligibles à la lecture TVL principale (champs des notes) | 3 |
| … dont mesurées au calcul | **2** |
| Éligibles et mesurées à la lecture volume principale | **1** |
| Éligibles à la sensibilité mixte | 0 |
| Bloquées dès les notes | 26 |

TURTLE était éligible sur les champs mais tombe au calcul : la série TVL DefiLlama ne couvre que 29 % des jours de sa fenêtre (depuis mars 2024), sous le seuil de 90 %.

### Motifs de blocage (une ligne peut en cumuler plusieurs)

| Motif | Lignes |
|---|---|
| `debut_programme` manquant | 13 |
| `airdrop_unlock_tge_pct` manquant | 9 |
| volume cumulé manquant | 9 |
| `airdrop_pct_farmers` manquant | 8 |
| pas de programme pré-TGE | 6 |
| base « taches » (pas de capital engagé) | 5 |
| base manquante | 1 |

Sur les 24 programmes confirmés, la part des farmers est publiée pour 12, le déblocage au TGE pour 10, la date de début pour 7, et un volume cumulé daté pour 1 seul. **Seuls 5 publient ensemble la date, la part et le déblocage** : LIT, TURTLE, GENIUS, KNTQ et MET.

### Pourquoi ces champs manquent

- **Date de début** : les projets datent le TGE et les saisons nommées, rarement l'ouverture des points. Beaucoup de programmes démarrent en bêta privée ou avec le produit, sans annonce datée (Echelon « mi-2024 », HyperSwap « Q1 2025 », Momentum sans date pour les Bricks). Deux dates retenues sont conventionnelles (le 15 du mois, pour LIT et TURTLE).
- **Part des farmers et déblocage** : l'enveloppe « communauté » publiée mélange airdrop, ventes publiques, incentives futurs et liquidité (VOOI 10,53 % incluant une vente, Mezo 40 %, Momentum 20,41 % incluant la vente Buidlpad), et le déblocage de cette seule part est rarement détaillé (HyperLend : genesis de 25 % sans calendrier).
- **Volume cumulé** : aucun projet ne publie un cumul daté depuis le début du programme. On trouve des volumes mensuels (Lighter : 272,5 Md$ en octobre 2025), des cumuls non datés (VOOI, ~5 Md$) ou des moyennes de saison (Paradex). Les séries de volume perps de DefiLlama sont payantes.
- **Pas de programme, tâches, base inconnue** : ce ne sont pas des trous de données mais la structure des lancements. Six tokens n'ont pas distribué d'allocation gratuite liée à l'usage, cinq programmes rémunéraient des quêtes ou un testnet sans capital, et un ne documente pas sa mécanique (Fanable).

## Statut des questions

- **Q1** (rendement annualisé TVL contre 5 %/an) : **non concluante**, 2 lectures pour un seuil de 8.
- **Q2** (traction forte et backers tier1 contre le reste) : **non calculée**, aucun groupe n'atteint 3 lectures.
- **Sensibilité base mixte** : aucune lecture mesurable.

## Cas isolés — non généralisables

Rapportés un par un, conformément au protocole : ni médiane, ni comparaison au seuil de Q1.

- **KNTQ (Kinetiq)** : 6,1 %/an. Valeur de sortie 35,7 M$ pour une TVL moyenne de 1,58 Md$ sur 135 jours (kPoints du 15/07/2025 au TGE du 27/11/2025).
- **MET (Meteora)** : 8,3 %/an. Valeur de sortie 79,8 M$ pour une TVL moyenne de 528 M$ sur 661 jours (LP Stimulus depuis le 01/01/2024, date annoncée). La TVL est celle du parent DefiLlama, tous produits Meteora confondus.
- **GENIUS (Genius Terminal)** : ~25 bps du volume, ordre de grandeur. Valeur de sortie 45,4 M$ pour 18 Md$ de volume déclaré par le projet.

## Trois programmes dont la récompense a changé de nature avant le TGE

- **Cap** : le programme Frontier a été récompensé en stablecoin et non en CAP. Le Stabledrop annoncé à 12 M cUSD le 04/02/2026 a été réduit à 4,2 M (−65 %) et réservé aux détenteurs de YT Pendle.
- **Ranger** : les points ont été convertis en droit d'achat garanti à l'ICO MetaDAO (06-10/01/2026), pas en allocation gratuite.
- **Katana** : les KAT farmés sont restés non transférables jusqu'au TGE du 18/03/2026, sans publication du montant cumulé.

Sur 30 programmes, trois ont donc changé la nature, le montant ou la liquidité de la récompense avant le TGE : **les points ne sont pas un contrat**. L'émetteur garde la main jusqu'au dernier jour.

## Limites

- Notes en un seul passage, sans double notation ; 27 sur 30 en confiance basse.
- Valeur de sortie au prix médian de J+1 à J+7, sur la part débloquée au TGE seulement : c'est la valeur réalisable par un farmer qui vend la première semaine, pas celle d'un farmer qui garde.
- Une seule fenêtre de marché (TGE d'octobre 2025 à juin 2026).
