# Pitlane Lab : site vitrine + administration

## Contenu du dossier
- `index.html` : le site (on n'y touche pas).
- `content.json` : tous les textes, prix, réglages, couleurs et noms de photos.
- `admin.html` : la page pour tout modifier sans coder (à garder en favori).
- `images/` : logo, icônes et photos. Les photos envoyées via l'admin vont dans `images/uploads/`.
- `fonts/` : polices hébergées avec le site.
- `.htaccess`, `robots.txt`, `sitemap.xml`, `manifest.webmanifest` : réglages techniques.

## Mise en ligne (première fois)
1. Envoie TOUT le contenu de ce dossier à la racine de l'hébergement (là où se trouve la page d'accueil du domaine).
2. Ouvre `https://ton-domaine/` pour voir le site, et `https://ton-domaine/admin.html` pour l'administration.
3. Dans `robots.txt` et `sitemap.xml`, remplace `pitlanelab.fr` par le vrai nom de domaine (ou garde-le si c'est le bon).
4. Protège `admin.html` par mot de passe (voir `.htaccess`, section en bas).

## Mettre à jour le site (ensuite)
1. Ouvre `admin.html`, modifie, clique sur **Aperçu** pour vérifier.
2. Clique sur **Télécharger le pack** : tu obtiens un `.zip`.
3. Décompresse-le. Envoie `content.json` (il remplace l'ancien) et le dossier `images` s'il y en a un (il fusionne avec l'existant).
4. Recharge le site avec Ctrl+F5.

## À faire avant l'ouverture au public
- Remplacer le téléphone et l'e-mail d'exemple (bloc « Coordonnées et réseaux »).
- Compléter les mentions légales (nom, SIRET, hébergeur).
- Vérifier les tarifs et les descriptions des prestations.
- Ajouter des photos : accueil, prestations, avant/après, galerie, portrait.
- Confirmer l'adresse du site (bloc « Référencement et partage »).
La liste « Avant de publier » en haut de l'admin suit tout ça.

## Tester en local
Un fichier ouvert directement (double-clic) ne peut pas lire `content.json`. Il faut un petit serveur :
`python3 -m http.server 8000` dans ce dossier, puis ouvrir http://localhost:8000/
