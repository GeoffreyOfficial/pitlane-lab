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

## Photothèque (admin)
- Le bouton « Photos » de l'admin ouvre la photothèque : importer (tous formats, y compris HEIC iPhone et TIFF), choisir, recadrer, remplacer, supprimer, nettoyer les photos inutilisées.
- Le dossier `vendor/` (lecteurs HEIC et TIFF, licences MIT) doit être envoyé avec le reste : sans lui, seuls ces deux formats ne s'ouvrent pas.
- Les photos ajoutées vont dans `images/uploads/`. Après une suppression, le pack contient `A-SUPPRIMER.txt` : la liste des fichiers à effacer sur GitHub.
- Le registre des photos est enregistré dans `content.json` (clé « medias »).

## Suivi des modifications (admin)
- L'admin compare en permanence le contenu à la version en ligne : pastille « ✎ N modifications » sur chaque section, bouton ↺ pour annuler une section, indicateur global.
- La fenêtre de comparaison (clic sur l'indicateur ou « Voir les modifications ») liste ajouts, suppressions et modifications avec anciennes et nouvelles valeurs ; chaque ligne s'annule seule.
- Elle s'ouvre aussi avant chaque téléchargement (pack ou content.json) et avant le chargement d'un fichier.
- Les éléments des listes portent un identifiant interne `_id` dans `content.json` : normal, ne pas supprimer.

## Suite de tests (dossier tests/)
- 530 tests automatiques (670 avec `--full`) (site public, administration, parcours complet de publication) : voir `tests/README.md`.
- Lancer : `tests/run-tests.sh` (Linux/macOS) ou `tests\run-tests.bat` (Windows). Rapide : `tests/run-tests.sh -m static`.
- Avant l'ouverture au public : `tests/run-tests.sh --launch --full`.
- Le workflow `.github/workflows/tests.yml` relance tout à chaque envoi sur GitHub et chaque lundi.
- Le dossier `tests/` et `.github/` ne servent pas au site : tu peux les garder dans le dépôt sans effet pour les visiteurs.

## Studio de design (admin)
- Bouton « Design » : aperçu du site en direct (ordinateur, tablette, téléphone) + ambiances, couleurs, style, mise en page, modules.
- Huit ambiances prêtes (dont deux thèmes clairs), générateur de palette, contrôle de lisibilité, ordre des sections, modules ajoutables.
- Sans réglage, l'aspect d'origine du site est strictement conservé. Voir le guide intégré (section 6).
