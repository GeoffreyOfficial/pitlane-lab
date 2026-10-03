"""Parcours complet : modifier dans l'admin → télécharger le pack → « mettre en ligne » → vérifier le site → recommencer."""
import io
import zipfile

import pytest

from conftest import FIXTURES
from helpers import (close_media, download_pack, draft, import_files, library_paths, open_admin, open_item, open_panel, open_site,
                     read_zip_json, set_field, wait_for)

pytestmark = [pytest.mark.admin, pytest.mark.site, pytest.mark.slow]


def deploy(z, site):
    """Simule l'envoi du pack sur l'hébergement : on dépose les fichiers dans la copie du site."""
    for name in z.namelist():
        if name == "content.json" or name.startswith("images/"):
            dest = site.dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(name))


def test_full_publish_cycle(make_page, site_copy):
    # ---- 1) l'administrateur modifie plusieurs choses
    hd = make_page(site_copy, "admin.html", w=1280, h=900)
    open_admin(hd, site_copy)
    p = hd.page
    import_files(p, [FIXTURES / "photo.jpg", FIXTURES / "alpha.png"])
    photo, logo = None, None
    paths = library_paths(p)
    close_media(p)
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Titre publié par le test complet")
    p.click('.imgfld[data-fp="images.hero"] button.thumb')
    p.locator("#mdGrid .md-card").first.click()
    p.click('#mdFoot [data-f="use"]')
    hero_photo = draft(p)["images"]["hero"]
    assert hero_photo in paths
    open_panel(p, "prestations")
    open_item(p, "services.0")
    set_field(p, "#f_services_0_prix", "123 €")
    open_panel(p, "faq")
    p.click('#pb_faq [data-act="add"][data-p="faq"]')
    set_field(p, "#f_faq_7_q", "Question publiée ?")
    set_field(p, "#f_faq_7_a", "Réponse publiée.")
    open_panel(p, "couleurs")
    p.click(".pre button >> nth=1")
    p.wait_for_timeout(800)
    z = download_pack(p)
    assert hero_photo in z.namelist()
    deploy(z, site_copy)
    c = read_zip_json(z)
    assert c["hero"]["titre"] == "Titre publié par le test complet"

    # ---- 2) le site public reflète les changements
    hs = make_page(site_copy, w=1280, h=900)
    open_site(hs, site_copy)
    s = hs.page
    assert "titre publié par le test complet" in s.inner_text(".hero h1").lower()
    assert "123" in s.inner_text("#cards .card >> nth=0")
    assert s.evaluate("document.querySelector('.hero-photo') && document.querySelector('.hero-photo').src.includes('images/uploads/')")
    assert s.evaluate("document.querySelector('.hero-photo').complete && document.querySelector('.hero-photo').naturalWidth>0"), "la photo d'accueil publiée ne se charge pas"
    assert s.locator(".qa").count() == 8 and "question publiée" in s.inner_text("#faq").lower()
    assert s.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()") == "#0a6cff"
    assert not hs.errors and not hs.bad_responses, (hs.errors, hs.bad_responses)

    # ---- 3) l'admin rouvert sur le site publié : plus rien en attente
    ha = make_page(site_copy, "admin.html", w=1280, h=900)
    open_admin(ha, site_copy)
    a = ha.page
    assert not a.evaluate("document.getElementById('dlgConfirm').open"), "aucune proposition de brouillon : la version en ligne est à jour"
    wait_for(lambda: "Identique" in a.inner_text("#saveState"), msg="l'admin devrait être « identique au site en ligne »")
    assert a.locator("[data-diff-badge]:visible").count() == 0
    a.click("#mediaBtn")
    wait_for(lambda: len(library_paths(a)) == 2)
    wait_for(lambda: a.locator("#mdGrid .md-in", has_text="×").count() == 2, msg="dimensions des photos publiées non lues")
    assert a.locator("#mdGrid .bdg.new").count() == 0, "les photos publiées ne sont plus « nouvelles »"
    close_media(a)

    # ---- 4) deuxième cycle : retirer une photo publiée → le pack liste le fichier à supprimer
    a.click("#mediaBtn")
    unused = [x for x in library_paths(a) if x != hero_photo][0]
    a.locator(f'#mdGrid .md-card[data-path="{unused}"]').click()
    a.click('#mdDetail [data-d="delete"]')
    a.wait_for_selector("#dlgConfirm[open]", state="attached")
    assert "GitHub" in a.inner_text("#cText")
    a.click("#cYes")
    close_media(a)
    z2 = download_pack(a)
    assert "A-SUPPRIMER.txt" in z2.namelist() and unused in z2.read("A-SUPPRIMER.txt").decode()
    assert not [n for n in z2.namelist() if n.startswith("images/")], "aucune photo à renvoyer : elles sont déjà en ligne"
    deploy(z2, site_copy)
    (site_copy.dir / unused).unlink()

    # ---- 5) le site reste cohérent après la suppression
    hs2 = make_page(site_copy, w=390, h=844, mobile=True)
    open_site(hs2, site_copy)
    assert not hs2.errors and not hs2.bad_responses, (hs2.errors, hs2.bad_responses)
    assert hs2.page.evaluate("document.documentElement.scrollWidth") <= 390


def test_rollback_with_previous_content_file(make_page, site_copy):
    original = site_copy.content()
    hd = make_page(site_copy, "admin.html")
    open_admin(hd, site_copy)
    p = hd.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Version B")
    z = download_pack(p)
    deploy(z, site_copy)
    # le site est maintenant en version B ; on recharge un ancien fichier (version A) dans une nouvelle session d'admin
    p.reload()
    p.wait_for_selector(".panel")
    old = site_copy.dir / "ancien.json"
    old.write_text(__import__("json").dumps(original, ensure_ascii=False), encoding="utf-8")
    p.set_input_files("#loadFile", str(old))
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    assert "Version B" in p.inner_text("#dfBody"), "la comparaison doit montrer ce qui change par rapport à la version B en cours"
    p.click("#dfOk")
    wait_for(lambda: draft(p)["hero"]["titre"] == original["hero"]["titre"])
    z2 = download_pack(p)
    deploy(z2, site_copy)
    hs = make_page(site_copy)
    open_site(hs, site_copy)
    assert original["hero"]["titre"].lower()[:15] in hs.page.inner_text(".hero h1").lower()
