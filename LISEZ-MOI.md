# Pitlane Lab : site vitrine + administration (V2)

## Contenu du dossier
- `index.html` : le site (on n'y touche pas).
- `content.json` : tous les textes, prix, réglages, couleurs et noms de photos.
- `admin.html` : la page pour tout modifier sans coder (à garder en favori).
- `sw.js` : mode hors ligne et chargement plus rapide aux visites suivantes.
- `images/`, `fonts/` : logo, icônes, photos, polices.
- `.htaccess` (hébergement Apache uniquement), `robots.txt`, `sitemap.xml`, `manifest.webmanifest`.

## Ce qui est inclus
- Intro « feux de départ » (une fois par visite, passable d'un clic).
- Page d'accueil à essuyer : le visiteur « polit » la peinture avec la souris ou le doigt.
- Bandeau défilant, rail de navigation, curseur lumineux, titres animés.
- « Chaque détail compte » : points cliquables sur la voiture, reliés aux prestations.
- Estimateur de prix dans le formulaire (taille, état, prestations) + message prêt pour WhatsApp / e-mail.
- Date souhaitée, badge de disponibilité, fiche contact à enregistrer (.vcf).
- Tout se règle ou se coupe dans l'admin (bloc « Effets et animations »).

## Mise en ligne sur GitHub Pages
1. Crée un dépôt public, envoie le CONTENU du dossier à la racine (index.html à la racine, avec images/ et fonts/).
2. Settings, puis Pages : Deploy from a branch, branche main, dossier / (root).
3. Dans l'admin, bloc « Référencement et partage », renseigne l'adresse du site. Mets-la aussi dans robots.txt et sitemap.xml.

## Mettre à jour
1. Ouvre admin.html, modifie, clique sur Aperçu.
2. « Télécharger le pack », décompresse, envoie content.json (remplace l'ancien) et le dossier images.
3. Recharge avec Ctrl+F5. Sur GitHub Pages, le changement peut prendre quelques minutes.

## À faire avant l'ouverture
- Téléphone et e-mail (ce sont des exemples), mentions légales (nom, SIRET, hébergeur).
- Vérifier les tarifs, descriptions et coefficients de l'estimateur.
- Ajouter les photos : accueil, prestations, avant/après, galerie, portrait.
La liste « Avant de publier » en haut de l'admin suit tout ça.

## Tester en local
`python3 -m http.server 8000` dans ce dossier, puis http://localhost:8000/ (un double-clic sur index.html ne suffit pas).

## Mise en ligne sur GitHub Pages
1. Crée un dépôt public, envoie TOUT le contenu de ce dossier à la racine (index.html doit être à la racine, avec `images/`, `fonts/` et `sw.js`).
2. Settings > Pages > Source : « Deploy from a branch », branche `main`, dossier `/ (root)`.
3. Le site est sur https://TON-PSEUDO.github.io/NOM-DU-DEPOT/ et l'admin sur .../admin.html.
4. `.htaccess` ne sert que sur un hébergement Apache (OVH...) : GitHub Pages l'ignore.

## Ce que fait le site
- Écran d'intro « feux de départ » : une fois par session, passable d'un clic, absent si l'on a demandé de réduire les animations.
- Accueil : la peinture est « sale » et on la polit à la souris ou au doigt.
- Bandeau défilant, section « Chaque détail compte » (points cliquables sur la voiture), rail de navigation, curseur personnalisé : chacun se désactive dans l'admin (bloc Effets).
- Formulaire de devis avec estimateur indicatif (taille de voiture, état, prestations). Les coefficients se règlent dans l'admin : à valider avec Jermaine.
- `sw.js` : permet au site de s'ouvrir même avec un réseau instable. Il relit toujours `content.json` et `index.html` en ligne en priorité, donc les mises à jour apparaissent normalement.
