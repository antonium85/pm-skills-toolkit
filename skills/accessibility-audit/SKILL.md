---
name: accessibility-audit
description: Audite l'accessibilité (a11y) d'une page web, d'un composant HTML/React, ou d'une maquette avant mise en production. Utiliser ce skill dès que l'utilisateur demande un audit d'accessibilité, veut vérifier la conformité WCAG/RGAA, mentionne "a11y", "accessibilité", "lecteur d'écran", "navigation clavier", "contraste", ou demande de vérifier qu'une page/un composant est accessible ou utilisable par des personnes en situation de handicap — même formulé de façon informelle ("est-ce que cette page est accessible ?", "vérifie l'a11y de ce composant", "peux-tu checker le contraste de ce design ?"). Se déclenche aussi proactivement si l'utilisateur partage du code HTML/JSX/CSS et demande une revue de qualité générale, car l'accessibilité doit être vérifiée systématiquement dans ce cas. Produit un rapport structuré avec constats, niveau de sévérité, et corrections suggérées.
---

# Accessibility Audit

Ce skill permet de réaliser un audit d'accessibilité (a11y) rigoureux sur du code HTML, JSX/React, ou une page web en ligne, en suivant un mini-process en 5 étapes. L'objectif est de repérer les obstacles réels pour les utilisateurs (lecteurs d'écran, navigation clavier, malvoyance, daltonisme) et de proposer des corrections concrètes, pas juste de citer des règles WCAG abstraites. La dernière étape produit un résumé exécutif destiné à un public non technique (produit, management) pour faciliter la priorisation et la décision.

## Quand utiliser ce skill

- L'utilisateur fournit du code (HTML, JSX, composant React/Vue) et demande un audit, une revue, ou "est-ce accessible ?"
- L'utilisateur fournit une URL et veut un audit de la page en ligne (utiliser un outil de navigation/browser si disponible pour inspecter le DOM réel)
- L'utilisateur demande une vérification de conformité WCAG 2.1/2.2 (AA) ou RGAA
- L'utilisateur veut un rapport avant mise en production ou avant une revue de code

## Ce dont tu as besoin avant de commencer

Si l'utilisateur n'a pas fourni le code ou l'URL, demande-le. Si c'est une URL, vérifie si un outil de navigation (ex: claude-in-chrome, ou équivalent) est disponible pour inspecter le DOM réel plutôt que de deviner à partir d'une capture d'écran. Sans accès au DOM ni au CSS calculé, précise dans le rapport que l'analyse est faite sur le code source fourni et non sur le rendu final (certains problèmes de contraste ou de focus ne sont visibles qu'à l'exécution).

## Le mini-process (5 étapes)

Applique les 5 étapes dans l'ordre. Pour chaque étape, produis une liste de constats classés par sévérité : **Bloquant** (empêche l'usage), **Majeur** (gêne sérieuse), **Mineur** (amélioration).

### 1. Structure sémantique

Vérifie :
- La hiérarchie des titres (`h1` → `h2` → `h3`...) est-elle continue, sans saut de niveau, et reflète-t-elle l'ordre logique de lecture ? Y a-t-il un seul `h1` par page ?
- Les landmarks HTML5 sont-ils présents et corrects (`<header>`, `<nav>`, `<main>`, `<footer>`, `<aside>`) plutôt que des `<div>` génériques partout ?
- Les liens ont-ils un intitulé explicite hors contexte (pas de "cliquez ici" ou "en savoir plus" sans contexte accessible via `aria-label` ou texte visible) ?
- Les listes (`<ul>`, `<ol>`), tableaux (`<table>` avec `<th>`/`scope`), et formulaires (`<label for="">` associés) utilisent-ils les bons éléments sémantiques plutôt que des `<div>` stylées ?
- Le DOM order correspond-il à l'ordre visuel (pas de réordonnancement CSS qui casse la lecture logique/lecteur d'écran) ?

### 2. Navigation clavier

Vérifie :
- Tous les éléments interactifs (liens, boutons, champs, éléments custom comme les dropdowns/modales) sont-ils atteignables via `Tab` ? Pas de piège clavier (focus trap non intentionnel) ?
- L'ordre de tabulation suit-il l'ordre visuel/logique ? Éviter les `tabindex` positifs (>0) qui cassent l'ordre naturel.
- Le focus est-il visible en permanence (pas de `outline: none` sans remplacement visuel clair) ? Le contraste de l'indicateur de focus est-il suffisant (3:1 minimum face au fond adjacent) ?
- Les composants custom (menus, modales, accordéons, carrousels) répondent-ils aux touches attendues (Entrée/Espace pour activer, Échap pour fermer une modale, flèches pour naviguer dans un menu) ?
- Existe-t-il un lien d'évitement ("Aller au contenu principal") en tout début de page ?

### 3. Contraste et lisibilité

Vérifie :
- Le ratio de contraste texte/fond atteint-il **4.5:1** pour le texte normal et **3:1** pour le texte large (≥18px gras ou ≥24px normal), conforme WCAG AA.
- La taille de police du texte courant est-elle ≥16px (ou équivalent `1rem`), avec un interlignage suffisant (≥1.5) et un espacement de paragraphe correct ?
- L'information n'est-elle jamais portée uniquement par la couleur (ex: erreurs de formulaire en rouge sans icône/texte, liens différenciés uniquement par couleur) ?
- Le texte redimensionne-t-il correctement jusqu'à 200% sans perte de contenu ni de fonctionnalité (pas d'unités figées en `px` bloquant le zoom) ?

Si tu ne peux pas calculer un ratio exact (pas d'accès au rendu réel), donne une estimation basée sur les codes couleur du CSS/design token fournis, et signale la limite.

### 4. Description des images et médias

Vérifie :
- Chaque `<img>` porteuse de sens a un `alt` descriptif et pertinent (pas de "image" ou nom de fichier) ; les images purement décoratives ont `alt=""` (pas absente d'attribut).
- Les vidéos ont des sous-titres ou une transcription ; les contenus audio ont une transcription texte.
- Les icônes utilisées seules comme bouton (sans texte visible) ont un `aria-label` ou `aria-labelledby` explicite.
- Les graphiques/infographies complexes (charts, diagrammes) ont une alternative textuelle qui transmet l'information, pas juste "graphique montrant les ventes".
- Les SVG inline interactifs ont les attributs ARIA appropriés (`role="img"` + `aria-label`, ou `aria-hidden="true"` si décoratifs).

### 5. Résumé exécutif

Cette étape se fait en dernier, une fois les 4 audits techniques terminés. L'objectif est de traduire les constats en langage accessible à un public non technique (product manager, management, client) qui doit décider de la priorisation sans lire le détail technique.

Produis un résumé qui :
- Donne un verdict global en une phrase (ex: "La page est utilisable mais présente 2 blocages critiques pour les utilisateurs de lecteur d'écran et de clavier, à corriger avant mise en production").
- Indique le nombre total de constats par sévérité (Bloquant / Majeur / Mineur), toutes catégories confondues.
- Reformule les 2-3 problèmes les plus critiques en termes d'impact business/utilisateur, pas de jargon technique (ex: "les utilisateurs malvoyants ne peuvent pas lire le prix des produits" plutôt que "contraste 2.1:1 sur `.price-tag`").
- Donne une estimation qualitative de l'effort global de mise en conformité (Faible/Moyen/Élevé) et un risque associé si rien n'est corrigé (ex: risque légal RGAA pour le secteur public, risque d'exclusion d'utilisateurs, image de marque).
- Ne dépasse pas 6-8 lignes : c'est un résumé pour décider, pas un rapport bis.

## Format du rapport

Structure toujours le rapport ainsi :

```
# Audit d'accessibilité — [nom du composant/page]

## Résumé exécutif
[Verdict global en une phrase, nombre de constats par sévérité, top 2-3 problèmes en langage non technique, effort global et risque — 6-8 lignes max, produit en dernier mais affiché en premier]

## 1. Structure sémantique
- [Bloquant/Majeur/Mineur] Constat — Localisation (ex: ligne, sélecteur) — Correction suggérée (avec extrait de code corrigé)

## 2. Navigation clavier
[même format]

## 3. Contraste et lisibilité
[même format]

## 4. Images et médias
[même format]

## Priorités recommandées

| Priorité | Constat | Impact utilisateur | Sévérité | Effort estimé |
|----------|---------|---------------------|----------|----------------|
| 1 | [constat] | [qui est impacté et comment] | Bloquant | Faible/Moyen/Élevé |
| 2 | ... | ... | ... | ... |
```

Le tableau des priorités recommandées liste les 3 à 5 corrections à traiter en premier, triées par impact décroissant (un problème Bloquant à faible effort passe avant un Mineur à effort élevé). La colonne "Effort estimé" reste qualitative (Faible/Moyen/Élevé) car elle dépend du code réel, pas d'une mesure précise. La colonne "Impact utilisateur" doit nommer concrètement qui est bloqué (ex: "utilisateurs lecteur d'écran ne peuvent pas fermer la modale", pas "problème d'accessibilité").

Chaque constat doit inclure un extrait de code "avant/après" quand c'est pertinent, pas juste une description théorique — l'utilisateur doit pouvoir copier-coller la correction.

## Notes

- Reste concret et actionnable : évite de simplement citer un critère WCAG (ex: "1.4.3 Contraste") sans expliquer le problème réel et la correction.
- Si le code fourni est trop long, découpe l'audit par composant/section plutôt que de tout traiter d'un bloc.
- Si l'utilisateur veut aussi tester avec un vrai lecteur d'écran ou un outil automatisé (axe-core, Lighthouse), tu peux le proposer en complément, mais l'audit manuel en 4 étapes techniques + résumé exécutif reste la base du rapport.
- Le résumé exécutif se rédige en dernier (il synthétise les 4 audits), mais il s'affiche en tête du rapport final puisque c'est souvent la seule partie lue par un décideur pressé.
