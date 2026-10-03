"""Suivi des modifications : pastilles, fenêtre de comparaison, annulation ciblée, revue avant téléchargement."""
import json

import pytest

from conftest import FIXTURES
from helpers import (close_media, confirm_dialog, download_pack, draft, import_files, library_paths, open_admin, open_item, open_panel,
                     read_zip_json, set_field, wait_for)

pytestmark = pytest.mark.admin


@pytest.fixture()
def adm(make_page, site):
    hd = make_page(site, "admin.html", w=1280, h=900)
    open_admin(hd, site)
    return hd


def edit_two_sections(p):
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Un tout nouveau titre d'accueil pour tester la comparaison mot à mot")
    set_field(p, "#f_hero_cta1", "Obtenir mon devis")
    open_panel(p, "prestations")
    open_item(p, "services.0")
    set_field(p, "#f_services_0_prix", "99 €")
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() >= 2, msg="les pastilles n'apparaissent pas")


def open_modal(p):
    p.click("#diffBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    p.wait_for_selector("#dfBody .df-row")


def rows(p):
    return p.locator("#dfBody .df-row").count()


# ------------------------------------------------------------------ pastilles et indicateurs
def test_pills_counts_and_global_line(adm):
    p = adm.page
    assert p.locator("[data-diff-badge]:visible").count() == 0
    edit_two_sections(p)
    assert "2 modifications" in p.inner_text("#pn_accueil [data-diff-badge]")
    assert "1 modification" in p.inner_text("#pn_prestations [data-diff-badge]")
    assert "3 modifications non téléchargées" in p.inner_text("#saveState")
    g = p.inner_text("#globalDiff")
    assert "3 changements" in g and ("Prestations" in g and "accueil" in g.lower())
    assert not p.is_disabled("#diffBtn")
    assert p.is_visible("#pn_accueil [data-restore-section]")


def test_changing_back_removes_the_modification(adm):
    p = adm.page
    open_panel(p, "accueil")
    original = p.input_value("#f_hero_titre")
    set_field(p, "#f_hero_titre", "Autre")
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 1)
    set_field(p, "#f_hero_titre", original)
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 0, msg="une valeur remise à l'identique doit disparaître des modifications")
    assert "Identique" in p.inner_text("#saveState")


# ------------------------------------------------------------------ fenêtre de comparaison
def test_modal_rows_types_and_word_diff(adm):
    p = adm.page
    edit_two_sections(p)
    open_modal(p)
    assert rows(p) == 3 and "3 modifications au total" in p.inner_text("#dfCount")
    assert p.locator("#dfBody .d-words ins").count() >= 1 and p.locator("#dfBody .d-words del").count() >= 1, "comparaison mot à mot attendue sur un long texte"
    txt = p.inner_text("#dfBody")
    assert "89" in txt and "99" in txt, "ancien et nouveau prix attendus"
    assert p.locator("#dfBody .df-row.added, #dfBody .df-row.removed").count() == 0


def test_rename_is_a_modification_not_add_plus_remove(adm):
    p = adm.page
    open_panel(p, "prestations")
    open_item(p, "services.1")
    set_field(p, "#f_services_1_titre", "Intérieur Premium")
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 1)
    open_modal(p)
    assert p.locator("#dfBody .df-row.added").count() == 0 and p.locator("#dfBody .df-row.removed").count() == 0
    assert "Intérieur Premium" in p.inner_text("#dfBody")


def test_revert_single_row_keeps_the_rest(adm):
    p = adm.page
    edit_two_sections(p)
    open_modal(p)
    p.locator("#dfBody .df-row", has_text="Prix").first.locator(".df-undo").click()
    wait_for(lambda: draft(p)["services"][0]["prix"] == "89 €")
    assert draft(p)["hero"]["cta1"] == "Obtenir mon devis"
    assert rows(p) == 2


def test_revert_whole_section_from_modal(adm):
    p = adm.page
    edit_two_sections(p)
    open_modal(p)
    p.locator('.df-sec[data-k="accueil"] .df-secundo').click()
    wait_for(lambda: draft(p)["hero"]["cta1"] != "Obtenir mon devis")
    assert draft(p)["services"][0]["prix"] == "99 €", "les autres sections ne doivent pas être touchées"
    assert p.locator('.df-sec[data-k="accueil"]').count() == 0


def test_filter_pills_hide_and_show_rows(adm):
    p = adm.page
    open_panel(p, "faq")
    p.click('#pb_faq [data-act="add"][data-p="faq"]')
    set_field(p, "#f_faq_7_q", "Une question ajoutée ?")
    open_panel(p, "accueil")
    set_field(p, "#f_hero_cta1", "Autre bouton")
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 2)
    open_modal(p)
    assert p.locator("#dfStats .df-stat").count() == 2
    p.click("#dfStats .df-stat.is-added")
    assert p.locator("#dfBody .df-row.added:visible").count() == 0 and p.locator("#dfBody .df-row.modified:visible").count() == 1
    p.click("#dfStats .df-stat.is-added")
    assert p.locator("#dfBody .df-row:visible").count() == 2


def test_modal_closes_with_escape_button_and_backdrop(adm):
    p = adm.page
    edit_two_sections(p)
    for how in ("escape", "close", "cancel"):
        open_modal(p)
        if how == "escape":
            p.keyboard.press("Escape")
        elif how == "close":
            p.click("#dfClose")
        else:
            p.click("#dfCancel")
        p.wait_for_function("!document.getElementById('dlgDiff').open")


def test_restore_everything_from_header_button(adm):
    p = adm.page
    edit_two_sections(p)
    p.click("#discardBtn")
    confirm_dialog(p)
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 0)
    assert "Identique" in p.inner_text("#saveState")


def test_section_header_undo_button_confirms(adm):
    p = adm.page
    edit_two_sections(p)
    p.click("#pn_accueil [data-restore-section]")
    confirm_dialog(p, yes=False)
    assert "2 modifications" in p.inner_text("#pn_accueil [data-diff-badge]")
    p.click("#pn_accueil [data-restore-section]")
    confirm_dialog(p, yes=True)
    wait_for(lambda: not p.is_visible("#pn_accueil [data-diff-badge]"))


# ------------------------------------------------------------------ listes, photos, identité, couleurs
def test_list_add_remove_reorder_rows_and_their_reverts(adm):
    p = adm.page
    open_panel(p, "prestations")
    p.click('#pb_prestations [data-act="add"][data-p="services"]')
    set_field(p, "#f_services_6_prix", "10 €")
    p.click('.item[data-lp="services.2"] [data-act="del"]')
    confirm_dialog(p)
    p.click('.item[data-lp="services.3"] [data-act="mv"][data-d="-1"]')
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 1)
    open_modal(p)
    txt = p.inner_text("#dfBody")
    assert "Nouvelle prestation" in txt and "supprimée" in txt and "Ordre des prestations" in txt
    removed = draft(p)["services"]
    n = len(removed)
    p.locator("#dfBody .df-row.removed .df-undo").first.click()
    wait_for(lambda: len(draft(p)["services"]) == n + 1, msg="annuler une suppression doit restaurer l'élément")
    p.locator("#dfBody .df-row.added .df-undo").first.click()
    wait_for(lambda: not any(s["titre"] == "Nouvelle prestation" for s in draft(p)["services"]))


def test_new_photo_row_has_thumbnail_and_can_be_reverted(adm):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    close_media(p)
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 1)
    open_modal(p)
    assert "Nouvelle photo" in p.inner_text("#dfBody") and p.locator("#dfBody .d-th img").count() >= 1
    p.locator("#dfBody .df-row", has_text="Nouvelle photo").locator(".df-undo").click()
    wait_for(lambda: draft(p)["medias"] == [])


def test_branding_and_color_changes_are_listed(adm):
    p = adm.page
    open_panel(p, "couleurs")
    p.click(".pre button >> nth=1")
    open_panel(p, "identite")
    p.evaluate("(()=>{const r=document.getElementById('f_branding_logoHauteur'); r.value=3.6; r.dispatchEvent(new Event('input',{bubbles:true})); r.dispatchEvent(new Event('change',{bubbles:true}))})()")
    wait_for(lambda: p.locator("[data-diff-badge]:visible").count() == 2)
    open_modal(p)
    t = p.inner_text("#dfBody")
    assert "Ambiance de couleurs" in t and "Taille du logo" in t
    assert p.locator("#dfBody .d-sw").count() >= 2, "pastilles de couleur attendues"


# ------------------------------------------------------------------ revue avant téléchargement
def test_download_goes_through_the_review_and_respects_reverts(adm, tmp_path):
    p = adm.page
    edit_two_sections(p)
    p.click("#zipBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    assert "télécharger le pack" in p.inner_text("#dfTitle").lower()
    assert "content.json" in p.inner_text("#dfExtra")
    p.locator("#dfBody .df-row", has_text="Prix").first.locator(".df-undo").click()
    with p.expect_download() as dl:
        p.click("#dfOk")
    import io, zipfile
    z = zipfile.ZipFile(io.BytesIO(open(dl.value.path(), "rb").read()))
    c = read_zip_json(z)
    assert c["hero"]["cta1"] == "Obtenir mon devis" and c["services"][0]["prix"] == "89 €", "le pack doit refléter les annulations faites dans la revue"
    wait_for(lambda: "non téléchargée" not in p.inner_text("#saveState") and "téléchargée" in p.inner_text("#saveState"))


def test_download_review_can_be_cancelled_without_downloading(adm):
    p = adm.page
    edit_two_sections(p)
    downloads = []
    p.on("download", lambda d: downloads.append(d))
    p.click("#zipBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    assert "Continuer à modifier" in p.inner_text("#dfCancel")
    p.click("#dfCancel")
    p.wait_for_timeout(500)
    assert downloads == [] and "non téléchargée" in p.inner_text("#saveState")


def test_review_when_nothing_changed_offers_download_anyway(adm):
    p = adm.page
    p.click("#zipBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    assert "Aucune différence" in p.inner_text("#dfBody") and "quand même" in p.inner_text("#dfOk")
    with p.expect_download():
        p.click("#dfOk")


def test_json_only_download_warns_about_missing_photos(adm):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    close_media(p)
    p.click("#jsonBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    assert "pas incluse" in p.inner_text("#dfExtra") or "ne seront pas" in p.inner_text("#dfExtra") or "ne sera pas" in p.inner_text("#dfExtra")
    p.click("#dfCancel")


def test_missing_referenced_photo_is_flagged_in_the_review(adm):
    p = adm.page
    open_panel(p, "accueil")
    p.locator('.imgfld[data-fp="images.hero"] summary').click()
    set_field(p, '.imgfld[data-fp="images.hero"] details input', "images/nexiste-pas.jpg")
    p.click('#mediaBtn')
    p.wait_for_selector("#dlgMedia[open]", state="attached")
    p.wait_for_timeout(1500)
    close_media(p)
    p.click("#zipBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    wait_for(lambda: "introuvable" in p.inner_text("#dfExtra").lower(), msg="la photo manquante n'est pas signalée avant publication")
    p.click("#dfCancel")


# ------------------------------------------------------------------ chargement d'un fichier
def test_loading_a_file_shows_a_readonly_diff_and_is_undoable(adm, tmp_path):
    p = adm.page
    c = json.loads(json.dumps(adm.page.evaluate("JSON.parse(localStorage.getItem('pitlanelab_admin_draft_v1')||'null')") or {})) or None
    base = json.loads((tmp_path / "x").read_text()) if False else None
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Titre courant")
    other = draft(p)
    other["hero"]["titre"] = "Titre venu d'un autre fichier"
    f = tmp_path / "autre.json"
    f.write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
    p.set_input_files("#loadFile", str(f))
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    assert "autre fichier" in p.inner_text("#dfBody") and p.locator("#dfBody .df-undo").count() == 0 and "Charger" in p.inner_text("#dfOk")
    assert draft(p)["hero"]["titre"] == "Titre courant", "rien ne doit être appliqué avant la confirmation"
    p.click("#dfOk")
    wait_for(lambda: draft(p)["hero"]["titre"].startswith("Titre venu"))
    p.click("#undoBtn")
    wait_for(lambda: draft(p)["hero"]["titre"] == "Titre courant")


def test_loading_an_invalid_file_is_rejected(adm, tmp_path):
    p = adm.page
    f = tmp_path / "mauvais.json"
    f.write_text("ceci n'est pas du JSON", encoding="utf-8")
    p.set_input_files("#loadFile", str(f))
    wait_for(lambda: "valide" in p.inner_text("#toast").lower())
    assert not p.evaluate("document.getElementById('dlgDiff').open")


def test_identical_file_is_recognised(adm, tmp_path):
    p = adm.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Même contenu")
    f = tmp_path / "meme.json"
    f.write_text(json.dumps(draft(p), ensure_ascii=False), encoding="utf-8")
    p.set_input_files("#loadFile", str(f))
    wait_for(lambda: "identique" in p.inner_text("#toast").lower())
