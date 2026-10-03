"""Interactions du site public : menu, navigation, filtres, fenêtres, FAQ, comparateur, galerie, barre mobile, intro."""
import json

import pytest

from helpers import open_site, reveal_all, scroll_to, wait_for

pytestmark = pytest.mark.site
MOBILES = [(320, 568), (390, 844), (768, 1024), (844, 390)]


def gallery_content(base):
    base["visibility"]["galerie"] = True
    base["galerie"] = [{"_id": f"g{i}", "src": src, "alt": f"Photo test {i}"} for i, src in
                       enumerate(["images/og-image.jpg", "images/icon-512.png", "images/logo-full.png"])]
    return base


def ba_content(base):
    base["avantApres"] = [{"_id": "a1", "titre": "Cas 1", "vehicule": "Voiture 1", "avant": "images/og-image.jpg", "apres": "images/icon-512.png"},
                          {"_id": "a2", "titre": "Cas 2", "vehicule": "Voiture 2", "avant": "images/icon-512.png", "apres": "images/og-image.jpg"}]
    return base


# ------------------------------------------------------------------ menu burger
@pytest.mark.parametrize("w,h", MOBILES)
class TestBurger:
    def _open(self, make_page, site, w, h):
        hd = make_page(site, w=w, h=h, mobile=True)
        open_site(hd, site)
        hd.page.tap("#burger")
        hd.page.wait_for_function("document.getElementById('menu').classList.contains('open')")
        hd.page.wait_for_timeout(700)   # fin de l'animation d'ouverture
        return hd

    def closed(self, p):
        return p.evaluate("!document.getElementById('menu').classList.contains('open')")

    def test_button_stays_on_top_and_closes_menu(self, make_page, site, w, h):
        hd = self._open(make_page, site, w, h)
        p = hd.page
        on_top = p.evaluate("(()=>{const b=document.getElementById('burger').getBoundingClientRect(),e=document.elementFromPoint(b.left+b.width/2,b.top+b.height/2);return !!e&&!!e.closest('#burger')})()")
        assert on_top, "le bouton burger est recouvert par le menu : impossible de le refermer"
        p.tap("#burger")
        wait_for(lambda: self.closed(p), msg="le burger ne referme pas le menu")
        assert not p.evaluate("document.body.classList.contains('lock')"), "le défilement reste bloqué après fermeture"
        assert p.get_attribute("#burger", "aria-expanded") == "false"

    def test_background_tap_closes(self, make_page, site, w, h):
        hd = self._open(make_page, site, w, h)
        hd.page.tap("#menu", position={"x": w - 12, "y": h - 12})
        wait_for(lambda: self.closed(hd.page), msg="toucher le fond ne ferme pas le menu")

    def test_escape_closes_and_returns_focus(self, make_page, site, w, h):
        hd = self._open(make_page, site, w, h)
        hd.page.keyboard.press("Escape")
        wait_for(lambda: self.closed(hd.page), msg="Échap ne ferme pas le menu")
        assert hd.page.evaluate("document.activeElement&&document.activeElement.id")== "burger"

    def test_link_closes_menu_and_scrolls(self, make_page, site, w, h):
        hd = self._open(make_page, site, w, h)
        p = hd.page
        y0 = p.evaluate("scrollY")
        p.tap("#menu a.ml >> nth=1")
        wait_for(lambda: self.closed(p), msg="un lien du menu ne le referme pas")
        wait_for(lambda: p.evaluate("scrollY") > y0 + 150, msg="le lien du menu ne fait pas défiler")

    def test_can_reopen_many_times(self, make_page, site, w, h):
        hd = self._open(make_page, site, w, h)
        p = hd.page
        for _ in range(4):
            p.tap("#burger")
            wait_for(lambda: self.closed(p))
            p.tap("#burger")
            wait_for(lambda: not self.closed(p))
        assert not hd.errors

    def test_menu_closes_when_rotated_to_desktop_width(self, make_page, site, w, h):
        hd = self._open(make_page, site, w, h)
        hd.page.set_viewport_size({"width": 1280, "height": 800})
        wait_for(lambda: self.closed(hd.page), msg="le menu mobile reste ouvert sur grand écran")


# ------------------------------------------------------------------ navigation bureau
def test_desktop_nav_scrolls_and_highlights(make_page, site):
    hd = make_page(site, w=1440, h=900)
    open_site(hd, site)
    p = hd.page
    for sec in ["prestations", "resultats", "methode", "zone", "faq"]:
        p.click(f'.nav a.nl[data-sec="{sec}"]')
        wait_for(lambda: p.evaluate(f"Math.abs(document.getElementById('{sec}').getBoundingClientRect().top)<200"), msg=f"le lien {sec} ne mène pas à la section")
        reveal_all(p)
        wait_for(lambda: p.evaluate(f"document.querySelector('.nav a.nl.is-active')&&document.querySelector('.nav a.nl.is-active').dataset.sec==='{sec}'"), msg=f"{sec} non surligné dans le menu")
    assert not hd.errors


def test_hero_buttons_lead_to_expected_sections(make_page, site):
    hd = make_page(site, w=1280, h=800)
    open_site(hd, site)
    p = hd.page
    p.click(".hero-cta .btn >> nth=1")
    wait_for(lambda: p.evaluate("Math.abs(document.getElementById('prestations').getBoundingClientRect().top)<250"))
    p.evaluate("window.scrollTo(0,0)")
    p.click(".hero-cta .btn >> nth=0")
    wait_for(lambda: p.evaluate("Math.abs(document.getElementById('contact').getBoundingClientRect().top)<250"))


def test_skip_link_is_first_focus_and_works(make_page, site):
    hd = make_page(site, w=1280, h=800)
    open_site(hd, site)
    p = hd.page
    p.keyboard.press("Tab")
    assert p.evaluate("document.activeElement.className") == "skip"
    wait_for(lambda: p.evaluate("document.activeElement.getBoundingClientRect().top") >= 0, msg="le lien d'évitement doit apparaître au focus")
    p.keyboard.press("Enter")
    assert p.evaluate("location.hash") == "#main"


def test_keyboard_focus_is_always_visible(make_page, site):
    hd = make_page(site, w=1280, h=800)
    open_site(hd, site)
    p = hd.page
    bad = []
    for i in range(14):
        p.keyboard.press("Tab")
        r = p.evaluate("""(()=>{const e=document.activeElement; if(!e||e===document.body) return null; const c=getComputedStyle(e);
            return {t:e.tagName+'.'+(e.className||e.id), vis:e.getBoundingClientRect().width>0, ring:(c.outlineStyle!=='none'&&parseFloat(c.outlineWidth)>0)||c.boxShadow!=='none'||e.matches('.skip')}})()""")
        if r and r["vis"] and not r["ring"]:
            bad.append(r["t"])
    assert not bad, f"éléments sans indication de focus clavier : {bad}"


# ------------------------------------------------------------------ prestations
def test_category_filters(make_page, site):
    hd = make_page(site, w=1280, h=900)
    open_site(hd, site)
    p = hd.page
    cats = p.evaluate("[...new Set([...document.querySelectorAll('#cards .card')].map(c=>c.dataset.cat))]")
    total = p.locator("#cards .card").count()
    assert len(cats) >= 2
    for cat in cats:
        p.click(f'.chip[data-cat="{cat}"]')
        shown = p.evaluate("[...document.querySelectorAll('#cards .card:not(.hide)')].map(c=>c.dataset.cat)")
        assert shown and set(shown) == {cat}, f"filtre {cat} incorrect : {shown}"
        assert p.get_attribute(f'.chip[data-cat="{cat}"]', "aria-pressed") == "true"
        assert p.get_attribute('.chip[data-cat=""]', "aria-pressed") == "false"
    p.click('.chip[data-cat=""]')
    assert p.evaluate("document.querySelectorAll('#cards .card:not(.hide)').length") == total


class TestServiceDialog:
    def open_first(self, make_page, site, w=1280, h=900, mobile=False):
        hd = make_page(site, w=w, h=h, mobile=mobile)
        open_site(hd, site)
        scroll_to(hd.page, "#cards", "start")
        title = hd.page.inner_text("#cards .card >> nth=0 >> h3")
        hd.page.click("#cards .card >> nth=0")
        hd.page.wait_for_selector("#dlgService[open]", state="attached")
        return hd, title

    def test_opens_with_matching_content(self, make_page, site):
        hd, title = self.open_first(make_page, site)
        assert title.strip().lower() in hd.page.inner_text("#dlgService h3").strip().lower()
        assert hd.page.locator("#dlgService .incl li").count() >= 1
        assert "€" in hd.page.inner_text("#dlgService .price")

    @pytest.mark.parametrize("how", ["button", "escape", "backdrop"])
    def test_closes_every_way(self, make_page, site, how):
        hd, _ = self.open_first(make_page, site)
        p = hd.page
        if how == "button":
            p.click("#dlgService .x")
        elif how == "escape":
            p.keyboard.press("Escape")
        else:
            p.mouse.click(40, 450)
        p.wait_for_function("!document.getElementById('dlgService').open", timeout=4000)
        assert not hd.errors

    def test_quote_button_goes_to_form_and_preselects(self, make_page, site):
        hd, title = self.open_first(make_page, site)
        p = hd.page
        p.click("#dlgService .sheet-foot a")
        p.wait_for_function("!document.getElementById('dlgService').open")
        wait_for(lambda: p.evaluate("Math.abs(document.getElementById('contact').getBoundingClientRect().top)<300"))
        checked = p.evaluate("[...document.querySelectorAll('#est input[name=svc]:checked')].length")
        sel = p.evaluate("(document.getElementById('f-presta')||{}).value||''")
        assert checked == 1 or sel, "la prestation n'est pas présélectionnée dans le formulaire"

    def test_works_on_phone(self, make_page, site):
        hd, _ = self.open_first(make_page, site, 390, 844, True)
        p = hd.page
        w = p.evaluate("document.querySelector('#dlgService .sheet').getBoundingClientRect().width")
        assert w <= 390 + 1
        assert p.evaluate("document.documentElement.scrollWidth") <= 391
        assert p.is_visible("#dlgService .sheet-foot a"), "le bouton de devis doit rester visible"


# ------------------------------------------------------------------ FAQ, méthode, avant/après, galerie
def test_faq_accordion_mouse_and_keyboard(make_page, site):
    hd = make_page(site, w=1280, h=900)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#faq")
    btn = ".qa > button >> nth=0"
    assert p.get_attribute(btn, "aria-expanded") == "false"
    p.click(btn)
    assert p.get_attribute(btn, "aria-expanded") == "true"
    wait_for(lambda: p.evaluate("document.querySelector('.qa .ans p').getBoundingClientRect().height>10"), msg="la réponse ne s'affiche pas")
    p.click(btn)
    assert p.get_attribute(btn, "aria-expanded") == "false"
    p.focus(btn)
    p.keyboard.press("Enter")
    assert p.get_attribute(btn, "aria-expanded") == "true"
    p.keyboard.press("Space")
    assert p.get_attribute(btn, "aria-expanded") == "false"
    for sel in ["aria-controls", "id"]:
        assert p.get_attribute(btn, sel), f"attribut ARIA manquant : {sel}"


def test_method_steps_progress_with_scroll(make_page, site):
    hd = make_page(site, w=1280, h=800)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#steps", "start")
    v0 = p.evaluate("parseFloat(getComputedStyle(document.getElementById('steps')).getPropertyValue('--p'))")
    scroll_to(p, "#steps .step:last-child", "center")
    p.evaluate("window.scrollBy(0,300)")
    wait_for(lambda: p.evaluate("parseFloat(getComputedStyle(document.getElementById('steps')).getPropertyValue('--p'))") > v0 + 0.2, msg="la ligne de progression n'avance pas")
    assert p.evaluate("document.querySelectorAll('#steps .step.is-on').length") >= 3


def test_before_after_slider_keyboard_and_drag(make_page, site):
    hd = make_page(site, w=1280, h=900, content_fn=ba_content)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#ba")
    p.wait_for_timeout(2200)  # invitation à glisser terminée
    pos = lambda: p.evaluate("parseFloat(getComputedStyle(document.getElementById('ba')).getPropertyValue('--pos'))")
    p.focus(".ba-range")
    p.keyboard.press("Home")
    assert pos() == 0
    p.keyboard.press("End")
    assert pos() == 100
    box = p.locator("#ba").bounding_box()
    p.mouse.move(box["x"] + box["width"] * .5, box["y"] + box["height"] * .5)
    p.mouse.down()
    p.mouse.move(box["x"] + box["width"] * .25, box["y"] + box["height"] * .5, steps=6)
    p.mouse.up()
    assert 20 <= pos() <= 30, f"glissement incorrect : {pos()}"
    assert p.locator("#baThumbs button").count() == 2, "les miniatures de comparaisons manquent"
    p.click("#baThumbs button >> nth=1")
    assert "Cas 2" in p.inner_text("#baTitle")
    assert pos() == 50, "la barre doit revenir au centre quand on change de comparaison"


def test_before_after_demo_when_no_pairs(make_page, site):
    hd = make_page(site, w=390, h=844, mobile=True)
    open_site(hd, site)
    scroll_to(hd.page, "#ba")
    assert hd.page.evaluate("document.querySelector('#ba img.after').src.startsWith('data:')"), "illustration de démonstration attendue"


def test_gallery_lightbox(make_page, site):
    hd = make_page(site, w=1280, h=900, content_fn=gallery_content)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#galerie")
    assert p.locator("#galerie .masonry button").count() == 3
    p.click("#galerie .masonry button >> nth=0")
    p.wait_for_selector("#dlgLightbox[open]", state="attached")
    alt = lambda: p.inner_text("#dlgLightbox .cap")
    assert "Photo test 0" in alt()
    p.keyboard.press("ArrowRight")
    assert "Photo test 1" in alt()
    p.click("#dlgLightbox .prev")
    assert "Photo test 0" in alt()
    p.click("#dlgLightbox .prev")
    assert "Photo test 2" in alt(), "la galerie doit boucler"
    p.keyboard.press("Escape")
    p.wait_for_function("!document.getElementById('dlgLightbox').open")
    assert not hd.errors


def test_gallery_swipe_on_phone(make_page, site):
    hd = make_page(site, w=390, h=844, mobile=True, content_fn=gallery_content)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#galerie")
    p.tap("#galerie .masonry button >> nth=0")
    p.wait_for_selector("#dlgLightbox[open]", state="attached")
    cdp = hd.context.new_cdp_session(p)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 300, "y": 400}]})
    for i in range(1, 8):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 300 - i * 30, "y": 400}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    wait_for(lambda: "Photo test 1" in p.inner_text("#dlgLightbox .cap"), msg="le balayage ne change pas de photo")


# ------------------------------------------------------------------ détails de la voiture, mentions légales
def test_detail_hotspots_update_card(make_page, site):
    hd = make_page(site, w=1280, h=900)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#dxCar")
    n = p.locator("#dxCar .hot").count()
    assert n >= 3
    titles = set()
    for i in range(n):
        p.locator("#dxCar .hot").nth(i).click(force=True)
        titles.add(p.inner_text("#dxCard h3"))
    assert len(titles) == n, f"chaque point doit afficher sa propre fiche : {titles}"
    for i in range(n):
        assert p.locator("#dxCar .hot").nth(i).get_attribute("aria-label") or p.locator("#dxCar .hot").nth(i).inner_text(), "point sans nom accessible"


def test_legal_dialog(make_page, site):
    hd = make_page(site, w=390, h=844, mobile=True)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#legalBtn")
    p.tap("#legalBtn")
    p.wait_for_selector("#dlgLegal[open]", state="attached")
    assert "Données personnelles" in p.inner_text("#dlgLegal")
    p.tap("#dlgLegal .x")
    p.wait_for_function("!document.getElementById('dlgLegal').open")


# ------------------------------------------------------------------ barre mobile
def test_mobile_bar_behaviour(make_page, site):
    hd = make_page(site, w=390, h=844, mobile=True)
    open_site(hd, site)
    p = hd.page
    shown = lambda: p.evaluate("document.getElementById('mbar').classList.contains('show')")
    assert not shown(), "la barre ne doit pas gêner l'accueil"
    p.evaluate("window.scrollTo(0,1400)")
    wait_for(shown, msg="la barre n'apparaît pas après l'accueil")
    hrefs = p.evaluate("[...document.querySelectorAll('#mbar a')].map(a=>a.getAttribute('href'))")
    assert any(h.startswith("tel:+33") for h in hrefs) and any("wa.me/33" in h for h in hrefs) and "#contact" in hrefs
    scroll_to(p, "#contact", "start")
    wait_for(lambda: not shown(), msg="la barre doit se retirer dans la section contact")


def test_mobile_bar_hidden_on_desktop(make_page, site):
    hd = make_page(site, w=1366, h=768)
    open_site(hd, site)
    hd.page.evaluate("window.scrollTo(0,1500)")
    assert hd.page.evaluate("getComputedStyle(document.getElementById('mbar')).display") == "none"


# ------------------------------------------------------------------ écran d'intro
class TestIntro:
    def test_shows_then_can_be_skipped_by_click(self, make_page, site):
        hd = make_page(site, intro=True, w=1280, h=800)
        p = hd.page
        p.wait_for_selector("#start", state="attached")
        assert p.is_visible("#start")
        p.click("#start")
        p.wait_for_function("!document.getElementById('start')", timeout=4000)

    def test_can_be_skipped_with_escape(self, make_page, site):
        hd = make_page(site, intro=True, w=1280, h=800)
        hd.page.wait_for_selector("#start", state="attached")
        hd.page.keyboard.press("Escape")
        hd.page.wait_for_function("!document.getElementById('start')", timeout=4000)

    def test_ends_by_itself_and_never_blocks(self, make_page, site):
        hd = make_page(site, intro=True, w=390, h=844, mobile=True)
        hd.page.wait_for_function("!document.getElementById('start')", timeout=7000)
        assert not hd.page.evaluate("document.documentElement.classList.contains('pre')")

    def test_shown_once_per_session(self, make_page, site):
        hd = make_page(site, intro=True, w=1280, h=800)
        hd.page.wait_for_selector("#start", state="attached")
        hd.page.keyboard.press("Escape")
        hd.page.wait_for_function("!document.getElementById('start')")
        hd.page.reload()
        hd.page.wait_for_selector("#app .hero", state="attached")
        assert hd.page.locator("#start").count() == 0

    def test_skipped_with_url_hash(self, make_page, site):
        hd = make_page(site, "index.html#prestations", intro=True)
        hd.page.wait_for_selector("#app .hero", state="attached")
        assert hd.page.locator("#start").count() == 0
        wait_for(lambda: hd.page.evaluate("Math.abs(document.getElementById('prestations').getBoundingClientRect().top)<300"))
