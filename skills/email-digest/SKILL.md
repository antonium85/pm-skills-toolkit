---
name: email-digest
description: Synthétise et trie les emails Gmail des 7 derniers jours pour permettre à l'utilisateur de comprendre rapidement ce qui mérite son attention sans lire chaque email. Utilise le contexte personnel (métier, projets, centres d'intérêt, famille) uniquement pour prioriser et personnaliser les résumés, jamais pour inventer du contenu. Déclencher ce skill chaque fois que l'utilisateur demande un résumé, une synthèse, un tri, un récap ou un point sur ses emails/sa boîte Gmail/sa boîte de réception, même formulé de façon informelle ("qu'est-ce que j'ai reçu cette semaine ?", "fais le point sur mes mails", "y'a-t-il des trucs urgents dans ma boîte ?").
---
 
# Email Digest — Synthèse hebdomadaire Gmail
 
## Objectif
 
Lire les emails Gmail des 7 derniers jours et produire une synthèse triée par
niveau d'importance, pour que l'utilisateur sache en 2 minutes ce qui mérite
son attention — sans avoir à ouvrir sa boîte de réception.
 
## Règle d'or : contexte = lentille, jamais source
 
Le contexte personnel de l'utilisateur (métier de chef de produit e-commerce,
intérêt pour la tech/trading/crypto, famille, loisirs, etc.) sert **uniquement** à :
 
1. mieux évaluer l'importance réelle d'un email (ex: un email d'un outil
   e-commerce que l'utilisateur utilise est probablement plus pertinent
   qu'une newsletter générique) ;
2. relier un email à un projet, une activité ou un centre d'intérêt déjà
   connu, pour donner du contexte au résumé ;
3. repérer les éléments qui nécessitent une action ;
4. adapter le ton et le niveau de détail du résumé.
**Le contexte ne doit jamais servir à :**
- supposer le contenu d'un email non lu ou non ouvert ;
- attribuer une intention, une urgence ou un sujet à un email sur la seule
  base du nom de l'expéditeur ou de l'objet, sans avoir vérifié le corps ;
- inventer un lien entre un email et la vie personnelle de l'utilisateur si ce
  lien n'est pas explicite dans le texte de l'email.
Concrètement : si un email vient d'une école et que l'utilisateur est connu
comme parent, ne pas écrire "email concernant Lan My" sauf si le prénom ou
un élément identifiable apparaît réellement dans l'email. Écrire plutôt
"email de l'école [nom de l'école] — à vérifier qui est concerné" si le
contenu ne le précise pas.
 
Avant d'écrire une phrase de résumé, se demander : *"Est-ce que je tiens ça du
texte de l'email, ou est-ce que je le déduis du contexte perso ?"* Si c'est la
deuxième option, soit reformuler en restant neutre, soit l'omettre.
 
## Étapes
 
### 1. Récupérer les emails des 7 derniers jours
 
Utiliser `Gmail:search_threads` avec la requête `newer_than:7d` (ajuster en
`newer_than:Xd` si l'utilisateur précise une autre période). Exclure spam et
trash par défaut (comportement natif de l'outil).
 
- Utiliser `pageSize: 50` (max) et paginer avec `pageToken` si besoin pour
  couvrir toute la période.
- `view: THREAD_VIEW_MINIMAL` suffit pour un premier passage (objet + extrait).
### 2. Ignorer le bruit avant d'aller plus loin
 
Ces catégories sont **ignorées** : elles ne sont ni résumées, ni comptées, ni
mentionnées dans la synthèse finale, même groupées. Elles n'existent pas pour
l'utilisateur dans le résultat.
 
- newsletters ;
- promotions ;
- publicités ;
- notifications automatiques ;
- confirmations de paiement de routine ;
- reçus standards ;
- notifications de lecture ;
- alertes système sans action nécessaire.
Indices pour repérer ces emails (objet, expéditeur, snippet) : `category:promotions`,
`category:updates`, expéditeur `no-reply@`/`noreply@`, mots-clés "newsletter",
"offre", "promo", "soldes", "votre paiement a été effectué", "reçu n°",
"accusé de réception" sans contenu actionnable.
 
En cas de doute sur un email (l'objet/snippet ne permet pas de trancher s'il
est du bruit ou non), ne pas l'ignorer par défaut : l'ouvrir avec
`Gmail:get_thread` pour vérifier le contenu réel avant de décider. Il vaut
mieux lire un email de trop que d'ignorer à tort un email important.
 
**Ne jamais mentionner les emails ignorés dans la réponse finale** — ni leur
nombre, ni leur sujet, ni un résumé groupé. Ils doivent être complètement
absents de la synthèse, sans aucune trace.
 
### 3. Lire le contenu réel des emails qui semblent pertinents
 
Pour les threads qui ne sont pas du bruit évident, utiliser `Gmail:get_thread`
pour récupérer le corps complet. Ne pas se contenter de l'objet ou du snippet
pour juger de l'importance ou écrire le résumé — le snippet peut être
trompeur ou tronqué.
 
Prioriser la lecture complète pour :
- tout email mentionnant une échéance, une demande, une facture, un paiement,
  une action requise ;
- tout email lié à un projet professionnel ou personnel déjà identifié dans
  la conversation ou le contexte ;
- tout email dont l'expéditeur semble institutionnel (école, banque,
  administration, employeur, fournisseur connu).
### 4. Qualifier chaque email pertinent
 
Pour chaque email qui n'a pas été ignoré à l'étape 2, déterminer s'il s'agit
de :
 
- **une action à réaliser** — quelque chose est explicitement ou implicitement
  attendu de l'utilisateur (répondre, payer, signer, remplir, s'inscrire,
  rappeler un délai...) ;
- **une information à connaître** — pas d'action requise, mais le contenu est
  substantiel et pertinent (mise à jour de dossier, info administrative,
  actualité personnelle/professionnelle pertinente) ;
- **un rendez-vous ou une date importante à noter** — un événement, une
  échéance, une convocation, une invitation avec date précise.
Un même email peut relever de plusieurs catégories (ex: une invitation avec
inscription à faire est à la fois une action et une date à noter) — dans ce
cas, le faire apparaître dans chacune des sections concernées.
 
**Regrouper les emails liés au même sujet** (ex: plusieurs messages d'un même
établissement scolaire sur le même dossier) en une seule ligne/entrée plutôt
que de les lister séparément.
 
### 5. Rédiger la synthèse
 
Format de sortie obligatoire (réponse conversationnelle, pas de fichier sauf
demande explicite) :
 
```
## À faire
 
| Action | Échéance |
|---|---|
| [Action concrète et regroupée] | [date ou "non précisée"] |
 
## À noter
 
- [Résumé en une phrase d'une information importante à connaître.]
 
## Calendrier
 
- [Date] — [Rendez-vous, invitation ou échéance détectée.]
 
## En bref
 
- [3 à 5 points maximum résumant ce qui mérite l'attention cette semaine.]
```
 
Le tableau "À faire" doit être un tableau markdown classique (comme ci-dessus),
pas une liste à puces — confirmé par l'utilisateur comme format préféré.
 
Règles de rédaction :
- rester factuel, concis, orienté gain de temps — pas de phrases creuses ;
- ne jamais recopier de longs passages d'un email (limite : une courte
  citation de moins de 15 mots si nécessaire, sinon paraphraser) ;
- éviter les détails inutiles dans "À noter" — une phrase par information,
  pas un paragraphe ;
- ne conserver dans "À faire" que les actions réellement utiles — si une
  action est mineure ou optionnelle et sans enjeu réel, la mentionner dans
  "À noter" plutôt que dans "À faire" ;
- "En bref" doit rester à 3-5 points maximum, même si plus d'emails sont
  pertinents — prioriser ce qui a le plus d'impact ou d'urgence ;
- ne jamais mentionner les emails ignorés (étape 2), ni leur nombre ;
- n'inventer aucune information : si une échéance ou un détail n'est pas
  écrit dans l'email, ne pas la déduire ni l'estimer — écrire "non précisée"
  plutôt que de combler le vide.
**Personnalisation via le contexte perso** : quand c'est pertinent, expliquer
brièvement *pourquoi* un email compte pour l'utilisateur en s'appuyant sur le
contexte personnel connu (ex: "concerne Lan My" si son prénom apparaît
réellement dans l'email, ou "lié à ton activité de trading" si l'email
provient d'une plateforme que l'utilisateur utilise activement). Cette
explication doit rester courte (incise ou fin de phrase) et respecter la
Règle d'or ci-dessus : elle ne doit jamais servir à deviner un contenu que
l'email ne précise pas.
 
### 6. Cas particuliers
 
- **Aucun email pertinent trouvé** : le dire simplement (ex: "Rien à signaler
  cette semaine, tout ce qui est arrivé est du bruit/newsletters."), ne pas
  forcer une structure avec des sections vides.
- **Une ou plusieurs sections vides** (ex: rien de "À faire" mais des choses
  "À noter") : omettre les sections vides plutôt que d'afficher "Aucun
  élément" sous un titre.
- **Volume très élevé (>100 threads)** : signaler le volume à l'utilisateur
  et proposer de prioriser par catégorie Gmail (`category:primary` d'abord)
  plutôt que de tout lire en détail.
- **Email ambigu sur l'expéditeur réel concerné (ex: lié à un enfant, un
  projet)** : ne pas deviner. Si l'email ne précise pas, le signaler tel
  quel et laisser l'utilisateur faire le lien.
