"""Dashboard statique — synthèse des couches 1 à 3.

Assemble le dernier thermomètre, la dernière veille et la dernière carte des
problèmes en une page HTML autonome (aucune dépendance externe, lisible hors ligne).

Usage  : python dashboard/generer.py
Sortie : data/dashboard.html
"""

import csv
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).resolve().parents[1]

NOMS_INDICATEURS = {
    "rang_coinbase_appstore": "Coinbase App Store",
    "funding_btc_eth": "Funding BTC+ETH",
    "stablecoins_30j": "Stablecoins 30 j",
    "google_trends_bitcoin": "Google Trends « bitcoin »",
}

STYLE = """
  .viz-root { color-scheme: light;
    --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
    --grille:#e1e0d9; --axe:#c3c2b7; --bord:rgba(11,11,11,0.10);
    --accent:#2a78d6; --accent-clair:#cde2fb; --warning:#fab219; --critical:#d03b3b; }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root { color-scheme: dark;
      --surface:#1a1a19; --page:#0d0d0d; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
      --grille:#2c2c2a; --axe:#383835; --bord:rgba(255,255,255,0.10);
      --accent:#3987e5; --accent-clair:#184f95; } }
  :root[data-theme="dark"] .viz-root { color-scheme: dark;
    --surface:#1a1a19; --page:#0d0d0d; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --grille:#2c2c2a; --axe:#383835; --bord:rgba(255,255,255,0.10);
    --accent:#3987e5; --accent-clair:#184f95; }

  body { margin:0; background:var(--page); color:var(--ink);
         font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width:1080px; margin:0 auto; padding:24px 16px 48px; }
  h1 { font-size:22px; margin:0 0 2px; }
  h2 { font-size:16px; margin:0 0 12px; }
  .sous-titre { color:var(--muted); font-size:13px; margin-bottom:20px; }
  .carte { background:var(--surface); border:1px solid var(--bord); border-radius:10px;
           padding:20px; margin-bottom:16px; }
  .hero { font-size:52px; font-weight:600; line-height:1.1; }
  .hero-ligne { display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; }
  .lecture { color:var(--ink2); font-size:15px; }
  .pastille { display:inline-block; width:10px; height:10px; border-radius:50%;
              margin-right:6px; vertical-align:baseline; }
  .jauge { height:12px; border-radius:6px; background:var(--accent-clair); margin:14px 0 4px; }
  .jauge > div { height:100%; border-radius:6px 4px 4px 6px; }
  .echelle { display:flex; justify-content:space-between; color:var(--muted); font-size:11px; }
  .tuiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(215px, 1fr));
            gap:12px; margin-top:18px; }
  .tuile { border:1px solid var(--bord); border-radius:8px; padding:12px 14px; }
  .etiquette { color:var(--ink2); font-size:13px; }
  .valeur { font-size:26px; font-weight:600; margin:2px 0; }
  .unite { color:var(--muted); font-size:12px; }
  .score { font-size:13px; color:var(--ink2); margin-top:4px; }
  .ligne-probleme { margin-bottom:12px; }
  .titre-probleme { font-size:14px; margin-bottom:3px; }
  .meta { color:var(--muted); font-size:12px; }
  .piste { border-left:1px solid var(--axe); padding:1px 0; }
  .barre { display:inline-block; height:14px; background:var(--accent);
           border-radius:0 4px 4px 0; vertical-align:middle; }
  .val { font-size:13px; color:var(--ink); margin-left:8px; vertical-align:middle; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th { text-align:left; font-size:12px; color:var(--muted); font-weight:600;
       border-bottom:1px solid var(--axe); padding:6px 8px; }
  td { padding:6px 8px; border-bottom:1px solid var(--grille); }
  td.num { text-align:right; font-variant-numeric:tabular-nums; }
  .note { color:var(--muted); font-size:12px; margin-top:10px; }
  .vide { color:var(--muted); }
"""


def echapper(texte):
    return html.escape(str(texte if texte is not None else ""))


def dernier_fichier(dossier, motif):
    fichiers = sorted((RACINE / "data" / dossier).glob(motif))
    return fichiers[-1] if fichiers else None


def compact_usd(brut):
    montant = float(brut)
    for seuil, suffixe in ((1e9, " Md$"), (1e6, " M$"), (1e3, " k$")):
        if abs(montant) >= seuil:
            valeur = montant / seuil
            texte = f"{valeur:.1f}" if valeur < 100 else f"{valeur:.0f}"
            return texte.replace(".", ",") + suffixe
    return f"{montant:.0f} $"


def couleur_chaleur(score):
    # jauge de sévérité : calme -> accent, chaud -> warning, euphorie -> critique
    if score is None:
        return "var(--muted)"
    if score < 50:
        return "var(--accent)"
    if score < 75:
        return "var(--warning)"
    return "var(--critical)"


def section_cycle():
    fichier = dernier_fichier("cycle", "*.json")
    if not fichier:
        return ("<section class='carte'><h2>Thermomètre de cycle</h2>"
                "<p class='vide'>Aucune mesure — lancez <code>python cycle/thermometre.py</code>.</p></section>")
    mesure = json.loads(fichier.read_text(encoding="utf-8"))
    composite = mesure.get("score_composite")
    teinte = couleur_chaleur(composite)
    largeur = 0 if composite is None else round(composite)

    tuiles = []
    for cle, indicateur in mesure.get("indicateurs", {}).items():
        nom = echapper(NOMS_INDICATEURS.get(cle, cle))
        if indicateur.get("score") is None:
            corps = (f"<div class='valeur vide'>—</div>"
                     f"<div class='unite'>{echapper(indicateur.get('note', 'indisponible'))}</div>")
        else:
            corps = (f"<div class='valeur'>{echapper(indicateur.get('valeur'))}</div>"
                     f"<div class='unite'>{echapper(indicateur.get('unite', ''))}</div>"
                     f"<div class='score'><span class='pastille' style='background:"
                     f"{couleur_chaleur(indicateur['score'])}'></span>score {indicateur['score']}</div>")
        tuiles.append(f"<div class='tuile'><div class='etiquette'>{nom}</div>{corps}</div>")

    hero = "—" if composite is None else echapper(composite)
    return f"""<section class='carte'>
  <h2>Thermomètre de cycle — {echapper(mesure.get('date', ''))}</h2>
  <div class='hero-ligne'>
    <div class='hero'>{hero}</div>
    <div class='lecture'><span class='pastille' style='background:{teinte}'></span>{echapper(mesure.get('lecture', ''))}</div>
  </div>
  <div class='jauge'><div style='width:{largeur}%; background:{teinte}'></div></div>
  <div class='echelle'><span>0 froid</span><span>25</span><span>50</span><span>75</span><span>100 euphorie</span></div>
  <div class='tuiles'>{''.join(tuiles)}</div>
</section>"""


def section_problemes():
    # source unique : problemes/carte_problemes.md, alimentée par le clustering
    # hebdo manuel (Claude.ai) comme par le mode API
    fichier = RACINE / "problemes" / "carte_problemes.md"
    if not fichier.exists():
        return ("<section class='carte'><h2>Problèmes non résolus</h2>"
                "<p class='vide'>Aucune carte — <code>python problemes/clustering.py --export-prompt</code>, "
                "prompt dans Claude.ai, réponse dans problemes/carte_problemes.md.</p></section>")
    texte = fichier.read_text(encoding="utf-8")
    entete = re.search(r"^_(Générée le .+?)_$", texte, re.MULTILINE)

    clusters, verticale = [], "?"
    for ligne in texte.splitlines():
        if ligne.startswith("### "):
            c = re.match(r"###\s+(.+?)\s+[—-]\s+poids\s+(\d+)\s*\(fréquence\s+(\d+)\s*[×x]\s*intensité\s+(\d+)\)",
                         ligne)
            if c:
                clusters.append({"titre": c.group(1), "poids": int(c.group(2)),
                                 "frequence": int(c.group(3)), "intensite": int(c.group(4)),
                                 "verticale": verticale})
        elif ligne.startswith("## "):
            verticale = ligne[3:].strip()

    if not clusters:
        return ("<section class='carte'><h2>Problèmes non résolus</h2>"
                "<p class='vide'>Carte présente mais aucun problème lisible — vérifier le format "
                "« ### titre — poids … » dans problemes/carte_problemes.md.</p></section>")

    clusters.sort(key=lambda c: -c["poids"])
    clusters = clusters[:10]
    poids_max = max(c["poids"] for c in clusters) or 1

    lignes = []
    for c in clusters:
        # plafond 92 % : garde la valeur au bout de la barre, sans retour à la ligne
        pct = max(2, round(c["poids"] / poids_max * 92))
        lignes.append(f"""<div class='ligne-probleme'>
  <div class='titre-probleme'>{echapper(c['titre'])}
    <span class='meta'>({echapper(c['verticale'])} — fréquence {c['frequence']} × intensité {c['intensite']})</span></div>
  <div class='piste'><span class='barre' style='width:{pct}%'></span><span class='val'>{c['poids']}</span></div>
</div>""")
    note_entete = f"<p class='note'>{echapper(entete.group(1))}</p>" if entete else ""
    return f"""<section class='carte'>
  <h2>Problèmes non résolus — poids (fréquence × intensité)</h2>
  {note_entete}
  {''.join(lignes)}
  <p class='note'>Détail et citations : problemes/carte_problemes.md</p>
</section>"""


def section_candidats():
    fichier = RACINE / "veille" / "correspondances.csv"
    if not fichier.exists():
        return ("<section class='carte'><h2>Candidats — protocoles × problèmes</h2>"
                "<p class='vide'>Aucun croisement — <code>python veille/croisement.py</code> "
                "(nécessite une carte des problèmes).</p></section>")
    with fichier.open(encoding="utf-8-sig", newline="") as entree:
        lignes = [l for l in csv.DictReader(entree, delimiter=";")
                  if l.get("force") in ("fort", "moyen")]
    if not lignes:
        return ("<section class='carte'><h2>Candidats — protocoles × problèmes</h2>"
                "<p class='vide'>Aucune correspondance forte ou moyenne pour l'instant.</p></section>")

    rang_force = {"fort": 0, "moyen": 1}
    lignes.sort(key=lambda l: (rang_force[l["force"]], l.get("pre_tge") != "oui",
                               -int(l.get("poids_probleme") or 0)))
    rangs = []
    for l in lignes[:15]:
        force = "<strong>fort</strong>" if l["force"] == "fort" else "moyen"
        rangs.append(f"<tr><td>{echapper(l['protocole'])}</td><td>{echapper(l['verticale'])}</td>"
                     f"<td>{echapper(l['probleme_adresse'])}</td>"
                     f"<td class='num'>{echapper(l.get('poids_probleme', ''))}</td>"
                     f"<td>{force}</td><td>{echapper(l.get('pre_tge', ''))}</td>"
                     f"<td class='num'>{echapper(compact_usd(l.get('tvl_usd') or 0))}</td></tr>")
    reste = f"<p class='note'>{len(lignes)} correspondances fortes/moyennes au total dans " \
            f"veille/correspondances.csv</p>" if len(lignes) > 15 else ""
    return f"""<section class='carte'>
  <h2>Candidats — protocoles × problèmes</h2>
  <table>
    <thead><tr><th>Protocole</th><th>Verticale</th><th>Problème adressé</th><th>Poids</th>
    <th>Force</th><th>Pré-TGE</th><th>TVL</th></tr></thead>
    <tbody>{''.join(rangs)}</tbody>
  </table>
  {reste}
  <p class='note'>Matching v0 — heuristique non backtestée. Affinage hebdo : veille/correspondances_affinees.csv.</p>
</section>"""


def section_audit():
    sys.path.insert(0, str(RACINE / "audit"))
    import yaml
    from scoring import ETIQUETTE_V1, evaluer

    fichiers = sorted(f for f in (RACINE / "audit" / "candidats").glob("*.yaml")
                      if not f.name.startswith("_"))
    note = f"<p class='note'>{echapper(ETIQUETTE_V1)}</p>"
    if not fichiers:
        return ("<section class='carte'><h2>Audit couche 4 — scoring v1</h2>"
                "<p class='vide'>Aucun candidat audité — copier "
                "<code>audit/candidats/_gabarit.yaml</code> vers <code>&lt;slug&gt;.yaml</code>.</p>"
                f"{note}</section>")
    rangs = []
    for fichier in fichiers:
        candidat = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        r = evaluer(candidat)
        filtre = "<strong>exclu</strong>" if r["filtre"] == "exclu" else echapper(r["filtre"])
        indices = " ; ".join(f"{echapper(l)} : {echapper(s)}" for l, s in r["indices"])
        rangs.append(f"<tr><td>{echapper(candidat.get('nom') or fichier.stem)}</td>"
                     f"<td>{echapper(candidat.get('verticale') or '')}</td>"
                     f"<td>{filtre}</td><td>{indices}</td></tr>")
    return f"""<section class='carte'>
  <h2>Audit couche 4 — scoring v1</h2>
  <table>
    <thead><tr><th>Candidat</th><th>Verticale</th><th>Filtre</th><th>Indices (pas un classement)</th></tr></thead>
    <tbody>{''.join(rangs)}</tbody>
  </table>
  {note}
</section>"""


def section_veille():
    fichier = dernier_fichier("veille", "nouveaux_*.csv")
    if not fichier:
        return ("<section class='carte'><h2>Nouveaux protocoles</h2>"
                "<p class='vide'>Aucune veille — lancez <code>python veille/nouveaux_projets.py</code>.</p></section>")
    with fichier.open(encoding="utf-8-sig", newline="") as entree:
        lignes = list(csv.DictReader(entree, delimiter=";"))

    rangs = []
    for l in lignes[:12]:
        rangs.append(f"<tr><td>{echapper(l['nom'])}</td><td>{echapper(l['verticale'])}</td>"
                     f"<td class='num'>{echapper(compact_usd(l['tvl_usd']))}</td>"
                     f"<td>{echapper(l['token'])}</td><td>{echapper(l['liste_le'])}</td></tr>")
    reste = f"<p class='note'>{len(lignes)} protocoles au total dans {echapper(fichier.name)}</p>" \
        if len(lignes) > 12 else ""
    return f"""<section class='carte'>
  <h2>Nouveaux protocoles (DefiLlama)</h2>
  <table>
    <thead><tr><th>Nom</th><th>Verticale</th><th>TVL</th><th>Token</th><th>Listé le</th></tr></thead>
    <tbody>{''.join(rangs)}</tbody>
  </table>
  {reste}
</section>"""


def main():
    corps = (section_cycle() + section_problemes() + section_candidats() + section_audit()
             + section_veille())
    page = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CryptoStonk</title>
<style>{STYLE}</style>
</head>
<body class="viz-root">
<main>
  <h1>CryptoStonk</h1>
  <div class="sous-titre">Généré le {date.today().isoformat()} — outil interne, pas un conseil d'investissement.</div>
  {corps}
</main>
</body>
</html>"""
    sortie = RACINE / "data" / "dashboard.html"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(page, encoding="utf-8")
    print(f"Écrit : {sortie.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
