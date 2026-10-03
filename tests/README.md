# Suite de tests de Pitlane Lab

Objectif : **ne jamais casser sans le savoir**. Chaque modification du site ou de l'admin peut être validée en une commande.
Les tests pilotent un vrai navigateur (Chromium) comme le ferait un visiteur ou l'administrateur.

## Lancer les tests

| Plateforme | Commande |
|---|---|
| Linux / macOS | `tests/run-tests.sh` |
| Windows | `tests\run-tests.bat` |
| À la main | `pip install -r tests/requirements.txt` puis `python -m playwright install chromium` puis `python -m pytest` |

La première fois, le lanceur crée un environnement Python isolé (`.venv-tests`) et télécharge Chromium. Ensuite, c'est immédiat.
530 tests, 670 avec `--full`. Durée : environ 18 à 22 minutes pour tout. Un rapport est écrit dans `tests/artifacts/rapport.html`.

## Options utiles

| Option | Effet |
|---|---|
| `-m static` | contrôles rapides (≈ 1 s), sans navigateur : fichiers, JSON, syntaxe, poids |
| `-m site` / `-m admin` | seulement le site public / seulement l'administration |
| `-m "not slow"` | sans le parcours complet |
| `--full` | 17 tailles d'écran au lieu de 7 (de 320 à 3440 px) |
| `--launch` | ajoute les contrôles **d'avant mise en ligne** (numéro et e-mail d'exemple, mentions légales, domaine) |
| `-k mot` | seulement les tests dont le nom contient « mot » (ex. `-k carte`) |
| `--headed` | affiche le navigateur ; avec `--slowmo 300` pour suivre à l'œil |
| `-x` | s'arrête au premier échec |

Exemples : `tests/run-tests.sh -m static`, `tests/run-tests.sh -k formulaire --headed --slowmo 200`.

## Ce que couvrent les tests

| Fichier | Sujet |
|---|---|
| `test_static.py` | fichiers requis, `content.json` (clés, identifiants, couleurs, images existantes), manifeste, service worker, syntaxe JavaScript, poids, aucune ressource externe |
| `test_site_layout.py` | responsive : débordement horizontal, accueil, cartes alignées, tailles de texte, cibles tactiles, images, polices, en-tête, animations réduites |
| `test_site_interactions.py` | menu burger, navigation, filtres, fenêtres, FAQ, comparateur, galerie, détails, barre mobile, écran d'intro, accès clavier |
| `test_site_forms.py` | validation, messages WhatsApp et e-mail, estimateur (comparé à la formule), envoi direct, anti-spam, contacts |
| `test_site_map.py` | carte Google : chargement à l'approche, verrouillage, lenteur, rechargement, zoom, mise en page |
| `test_site_content.py` | logo et identité, SEO, accessibilité, contrastes, contenu dégradé ou hostile (injection de code, mots très longs), hors ligne |
| `test_admin_core.py` | démarrage, 20 panneaux, balayage de tous les champs, validation, historique, brouillon, aperçu, guide, responsive |
| `test_admin_lists.py` | prestations, FAQ, étapes, avis, points, estimateur : ajout, déplacement, suppression, annulation, identifiants |
| `test_admin_media.py` | photothèque : 12 formats, fichiers invalides, EXIF, GPS, doublons, bibliothèque, éditeur (rotation, miroir, recadrage, détourage, couleur) vérifiés au pixel près |
| `test_site_design.py` | design : chaque ambiance (lisibilité, mobile et ordinateur), formes, polices, fond, en-tête, mouvement, ordre des sections, modules (annonce, atouts, chiffres, appel à l'action, blocs libres), textes extrêmes |
| `test_admin_studio.py` | studio de design : aperçu en direct (3 appareils), ambiances et survol, générateur de palette, couleurs et lisibilité, style, mise en page, modules, publication |
| `test_admin_diff.py` | pastilles, fenêtre de comparaison, annulation ligne par ligne et par section, revue avant téléchargement |
| `test_e2e_publish.py` | parcours complet : modifier → pack → « mise en ligne » → site → admin → suppression → retour arrière |

## Comment ça marche

- Un **petit serveur local** sert le site : aucun accès au vrai site ni à GitHub.
- **Google Maps est simulé** ; toute autre requête externe est bloquée et enregistrée (un test échoue si le site en fait une).
- Chaque test a son **navigateur neuf** : aucun état ne fuit d'un test à l'autre.
- Les **erreurs JavaScript** et les **ressources en échec (404)** font échouer les tests concernés.
- En cas d'échec : une **capture d'écran** et le journal des erreurs sont déposés dans `tests/artifacts/`.
- Les tests qui modifient des fichiers travaillent sur une **copie jetable** du site (`site_copy`).

## Quand lancer quoi

- **Après chaque modification de code** : `tests/run-tests.sh -m static` (1 seconde), puis le sujet touché (`-k carte`, `-m admin`…).
- **Avant d'envoyer sur GitHub** : tout, avec `tests/run-tests.sh`.
- **Avant l'ouverture au public** : `tests/run-tests.sh --launch --full`.
- **Automatiquement** : le fichier `.github/workflows/tests.yml` relance toute la suite à chaque envoi sur GitHub et chaque lundi (onglet « Actions » du dépôt, rapport téléchargeable).

## Ajouter un test

Chaque fichier utilise les outils de `conftest.py` et `helpers.py` :

```python
def test_mon_cas(make_page, site):
    hd = make_page(site, w=390, h=844, mobile=True)   # une page dans un navigateur neuf
    open_site(hd, site)                                # attend le rendu, passe l'intro
    hd.page.click("#burger")
    assert hd.page.is_visible("#menu a")
    assert not hd.errors                               # aucune erreur JavaScript
```

- `site` : le site du dépôt (lecture seule). `site_copy` : une copie modifiable.
- `make_page(..., content_fn=lambda c: ..., maps="hold", reduced_motion=True, extra_routes=[...])` : contenu modifié à la volée, Google lent, animations réduites, points d'accès simulés.
- Pour l'admin : `open_admin`, `open_panel`, `set_field`, `download_pack`, `import_files` (dans `helpers.py`).
- Les fichiers d'exemple sont dans `tests/fixtures` (régénérables avec `python tests/make_fixtures.py`).

## Si un test échoue

1. Ouvre la capture dans `tests/artifacts/` : elle montre l'écran au moment de l'échec.
2. Relance seulement ce test en le regardant : `tests/run-tests.sh -k nom_du_test --headed --slowmo 300`.
3. Un test peut échouer **à juste titre** si tu as volontairement changé un comportement : mets alors le test à jour.
