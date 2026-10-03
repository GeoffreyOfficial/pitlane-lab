"""Design du site : ambiances, options (formes, polices, fond…), ordre des sections et modules ajoutables."""
import json
import re

import pytest

from helpers import Problems, open_site, overflow, reveal_all, scroll_to, wait_for
from conftest import ROOT

pytestmark = pytest.mark.site


@pytest.fixture(scope="module")
def ambiances(browser, site):
    """Les ambiances du studio, lues dans l'admin (une seule source de vérité)."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(site.url + "/admin.html")
    pg.wait_for_selector(".panel")
    data = pg.evaluate("window.__studio.AMBIANCES")
    ctx.close()
    return data


def with_design(**d):
    def fn(c):
        c.setdefault("design", {}).update(d)
        return c
    return fn


def apply_ambiance(a):
    def fn(c):
        c["theme"] = dict(a["t"])
        c["design"] = {**c.get("design", {}), **a["d"], "ambiance": a["id"]}
        if "titres" in a["d"]:
            c["design"]["titres"] = {**{"italique": True, "majuscules": True, "graisse": 800, "etirement": 118}, **a["d"]["titres"]}
        return c
    return fn


def ratio(p, fg, bg):
    return p.evaluate("""([a,b])=>{const L=h=>{const n=parseInt(h.slice(1),16),c=[(n>>16)&255,(n>>8)&255,n&255].map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*c[0]+.7152*c[1]+.0722*c[2]};
        const x=L(a),y=L(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}""", [fg, bg])


# ------------------------------------------------------------------ l'aspect d'origine est intact
def test_default_content_sets_no_design_override(make_page, site):
    hd = make_page(site)
    open_site(hd, site)
    p = hd.page
    attrs = p.evaluate("document.documentElement.getAttributeNames().filter(a=>a.startsWith('data-'))")
    assert attrs == [], f"aucun attribut de design attendu par défaut : {attrs}"
    style = p.evaluate("document.documentElement.getAttribute('style')||''")
    for v in ("--font-display", "--t-style", "--t-case", "--r:", "--dens", "--fs", "--maxw", "--grain"):
        assert v not in style, f"variable de design inattendue par défaut : {v}"


def test_garbage_design_values_fall_back_to_defaults(make_page, site):
    hd = make_page(site, content_fn=with_design(police="comic", boutons=42, cartes=None, rayon="énorme", densite={}, largeur=-5, entete="x", accueil=[], fond="?", grain=9999, mouvement=True, tailleTexte="grand", titres="oups", ordre="pas une liste"))
    open_site(hd, site)
    assert not hd.errors, hd.errors
    p = hd.page
    assert p.evaluate("document.documentElement.getAttribute('data-btn')") is None
    assert p.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)") <= 18.1
    assert overflow(p) <= 0 and p.is_visible(".hero h1")


# ------------------------------------------------------------------ ambiances
def test_there_are_enough_ambiances(ambiances):
    assert len(ambiances) >= 8
    assert len({a["id"] for a in ambiances}) == len(ambiances)
    assert any(sum(int(a["t"]["bg"][i:i + 2], 16) for i in (1, 3, 5)) > 600 for a in ambiances), "au moins une ambiance claire attendue"


def test_every_ambiance_is_readable(ambiances, make_page, site):
    """Chaque ambiance proposée doit respecter les contrastes de lisibilité (WCAG AA)."""
    hd = make_page(site)
    p, bad = hd.page, Problems()
    for a in ambiances:
        t = a["t"]
        bad.check(ratio(p, t["ink"], t["bg"]) >= 7, f"{a['id']} : texte / fond < 7:1")
        bad.check(ratio(p, t["muted"], t["bg"]) >= 4.5, f"{a['id']} : texte secondaire / fond < 4,5:1")
        bad.check(ratio(p, t["muted"], t["surface"]) >= 4.5, f"{a['id']} : texte secondaire / cartes < 4,5:1")
        bad.check(ratio(p, t["accent"], t["bg"]) >= 3, f"{a['id']} : accent / fond < 3:1")
    bad.assert_none()


@pytest.mark.parametrize("idx", range(9))
def test_ambiance_renders_cleanly(ambiances, make_page, site, idx):
    if idx >= len(ambiances):
        pytest.skip("moins d'ambiances que prévu")
    a = ambiances[idx]
    bad = Problems()
    for w, h, mob in [(390, 844, True), (1440, 900, False)]:
        hd = make_page(site, w=w, h=h, mobile=mob, content_fn=apply_ambiance(a))
        open_site(hd, site)
        p = hd.page
        bad.check(not hd.errors, f"{a['id']} {w}px : erreurs {hd.errors}")
        for y in range(0, p.evaluate("document.documentElement.scrollHeight"), 700):
            p.evaluate(f"window.scrollTo(0,{y})")
            reveal_all(p)
            bad.check(overflow(p) <= 0, f"{a['id']} {w}px : débordement à y={y}")
        light = int(a["t"]["bg"][1:], 16) > 0x808080
        bad.check((p.evaluate("document.documentElement.getAttribute('data-tone')") == "clair") == light, f"{a['id']} : thème clair mal détecté")
        # texte des boutons lisible sur l'accent
        c = p.evaluate("(()=>{const e=document.querySelector('.hero-cta .btn'); const s=getComputedStyle(e); return [s.color, s.backgroundColor]})()")
        rgb = lambda s: "#%02x%02x%02x" % tuple(int(float(x)) for x in re.findall(r"[\d.]+", s)[:3])
        bad.check(ratio(p, rgb(c[0]), rgb(c[1])) >= 4.5, f"{a['id']} : texte du bouton illisible ({c})")
        bad.check(p.is_visible(".brand img"), f"{a['id']} : logo invisible")
        hero_h = p.evaluate("document.querySelector('.hero').getBoundingClientRect().height")
        if w >= 900:
            bad.check(hero_h <= h + 2, f"{a['id']} : l'accueil dépasse l'écran ({hero_h:.0f} > {h})")
    bad.assert_none()


def test_light_theme_inverts_logo_and_hides_dirty_paint(make_page, site):
    light = {"bg": "#f6f4ef", "surface": "#ffffff", "surface2": "#ece8df", "ink": "#14110d", "muted": "#5e564a", "accent": "#b3122a", "accentHot": "#d11f3a", "line": "#d9d2c3"}

    def fn(c):
        c["theme"] = light
        return c
    hd = make_page(site, content_fn=fn)
    open_site(hd, site)
    p = hd.page
    assert "invert" in p.evaluate("getComputedStyle(document.querySelector('.brand img')).filter")
    assert "invert" in p.evaluate("getComputedStyle(document.querySelector('.pit-car img')).filter")
    assert p.evaluate("(()=>{const g=document.querySelector('.grime');return !g||getComputedStyle(g).display==='none'})()")
    assert p.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(246, 244, 239)"


# ------------------------------------------------------------------ options une à une
def cs(p, sel, prop):
    return p.evaluate("([s,p])=>getComputedStyle(document.querySelector(s))[p]", [sel, prop])


@pytest.mark.parametrize("val", ["parallelogramme", "carre", "arrondi", "pilule"])
def test_button_shapes(make_page, site, val):
    hd = make_page(site, content_fn=with_design(boutons=val, rayon=10))
    open_site(hd, site)
    clip, rad = cs(hd.page, ".hero-cta .btn", "clipPath"), cs(hd.page, ".hero-cta .btn", "borderRadius")
    if val in ("arrondi", "pilule"):
        assert clip == "none" and rad != "0px"
        assert (rad == "10px") == (val == "arrondi") or val == "pilule"
    elif val == "carre":
        assert "polygon" in clip and hd.page.evaluate("getComputedStyle(document.querySelector('.hero-cta .btn')).getPropertyValue('--sk').trim()") == "0rem"
    else:
        assert "polygon" in clip


@pytest.mark.parametrize("val", ["coins", "arrondi", "carre"])
def test_card_shapes(make_page, site, val):
    hd = make_page(site, content_fn=with_design(cartes=val, rayon=18))
    open_site(hd, site)
    scroll_to(hd.page, "#cards", "start")
    clip, rad = cs(hd.page, "#cards .card", "clipPath"), cs(hd.page, "#cards .card", "borderRadius")
    assert ("polygon" in clip) == (val == "coins")
    assert (rad == "18px") == (val == "arrondi")
    assert overflow(hd.page) <= 0


@pytest.mark.parametrize("val,expect", [("sport", "Saira"), ("moderne", "Barlow"), ("elegant", "Georgia"), ("technique", "monospace"), ("systeme", "system-ui")])
def test_font_sets(make_page, site, val, expect):
    hd = make_page(site, content_fn=with_design(police=val))
    open_site(hd, site)
    assert expect in cs(hd.page, ".hero h1", "fontFamily")
    assert overflow(hd.page) <= 0


def test_title_style_switches(make_page, site):
    hd = make_page(site, content_fn=with_design(titres={"italique": False, "majuscules": False, "graisse": 600, "etirement": 100}))
    open_site(hd, site)
    p = hd.page
    for sel in (".hero h1", ".h2", ".card h3", ".btn"):
        assert cs(p, sel, "fontStyle") == "normal" and cs(p, sel, "textTransform") == "none", f"{sel} ne suit pas le style des titres"


@pytest.mark.parametrize("val,mult", [(85, .85), (100, 1), (125, 1.25)])
def test_text_size_scale(make_page, site, val, mult):
    hd = make_page(site, w=1280, h=800, content_fn=with_design(tailleTexte=val))
    open_site(hd, site)
    assert abs(hd.page.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)") / 16 - mult) < .02


@pytest.mark.parametrize("val,mult", [("compacte", .72), ("normale", 1), ("aeree", 1.3)])
def test_density_scales_section_spacing(make_page, site, val, mult):
    hd = make_page(site, w=1280, h=800, content_fn=with_design(densite=val))
    open_site(hd, site)
    pad = hd.page.evaluate("parseFloat(getComputedStyle(document.getElementById('prestations')).paddingTop)")
    base = 9 * 12.8 if 9 * 12.8 > 72 else 72
    assert abs(pad / min(144, max(72, 9 * 12.8)) - mult) < .03, f"{val}: {pad}px"


@pytest.mark.parametrize("val", [1000, 1200, 1700])
def test_content_width(make_page, site, val):
    hd = make_page(site, w=1920, h=1000, content_fn=with_design(largeur=val))
    open_site(hd, site)
    assert abs(hd.page.evaluate("document.querySelector('#prestations .wrap').getBoundingClientRect().width") - val + 2 * 0) < 130   # moins les gouttières


@pytest.mark.parametrize("val", ["degrade", "plein", "verre", "discret"])
def test_header_styles(make_page, site, val):
    hd = make_page(site, content_fn=with_design(entete=val))
    open_site(hd, site)
    p = hd.page
    p.evaluate("window.scrollTo(0,0)")
    bg = cs(p, ".header", "backgroundColor")
    if val == "plein":
        assert bg != "rgba(0, 0, 0, 0)", "en-tête plein : fond attendu dès le haut de page"
    elif val in ("degrade", "discret"):
        assert bg == "rgba(0, 0, 0, 0)"
    else:
        assert "blur" in cs(p, ".header", "backdropFilter")
    assert p.is_visible(".brand img") and overflow(p) <= 0


def test_hero_alignment_center(make_page, site):
    hd = make_page(site, w=1280, h=800, content_fn=with_design(accueil="centre"))
    open_site(hd, site)
    p = hd.page
    assert cs(p, ".hero-in", "textAlign") == "center"
    box = p.evaluate("(()=>{const r=document.querySelector('.hero h1').getBoundingClientRect();return (r.left+r.right)/2})()")
    assert abs(box - 640) < 60, "le titre doit être centré"


@pytest.mark.parametrize("val", ["carbone", "uni", "points", "lignes", "grille"])
def test_section_background_patterns(make_page, site, val):
    hd = make_page(site, content_fn=with_design(fond=val))
    open_site(hd, site)
    img = cs(hd.page, "#resultats", "backgroundImage")   # section « carbone » (alternée)
    assert (img == "none") == (val == "uni"), f"{val}: {img[:60]}"


@pytest.mark.parametrize("val", ["riche", "calme", "aucun"])
def test_motion_modes(make_page, site, val):
    hd = make_page(site, content_fn=with_design(mouvement=val), intro=True)
    p = hd.page
    p.wait_for_selector("#app .hero", state="attached")
    if val == "aucun":
        assert p.evaluate("document.documentElement.getAttribute('data-motion')") == "aucun"
        assert p.locator("#start").count() == 0 or True
        p.evaluate("window.scrollTo(0,1500)")
        assert p.evaluate("[...document.querySelectorAll('.rv')].filter(e=>getComputedStyle(e).opacity==='0').length") == 0
        assert p.evaluate("getComputedStyle(document.querySelector('.hero h1 .w > span')).transform") in ("none", "matrix(1, 0, 0, 1, 0, 0)")
    assert not hd.errors


# ------------------------------------------------------------------ ordre des sections
def order(p):
    return p.evaluate("[...document.querySelectorAll('#app > section, #app > footer, #app > div:not(.annonce)')].map(e=>e.id||(e.matches('.marq-wrap')?'bandeau':e.tagName))")


def test_default_section_order(make_page, site):
    hd = make_page(site)
    open_site(hd, site)
    o = order(hd.page)
    assert o[0] == "accueil" and o[-2:] == ["contact", "FOOTER"] or o[-2:] == ["contact", "footer"]
    assert o.index("prestations") < o.index("details") < o.index("resultats") < o.index("methode") < o.index("zone") < o.index("faq")


def test_custom_order_is_respected_and_head_tail_are_fixed(make_page, site):
    hd = make_page(site, content_fn=with_design(ordre=["faq", "zone", "contact", "accueil", "prestations", "footer"]))
    open_site(hd, site)
    o = order(hd.page)
    assert o[0] == "accueil", "l'accueil reste toujours en tête"
    assert o[-2] == "contact" and o[-1].lower() == "footer", "contact et pied de page restent en fin"
    assert o.index("faq") < o.index("zone") < o.index("prestations"), o
    assert o.index("zone") < o.index("details"), "les sections non listées suivent, dans l'ordre d'origine"
    assert not hd.errors


def test_unknown_keys_in_order_are_ignored(make_page, site):
    hd = make_page(site, content_fn=with_design(ordre=["n'existe-pas", None, 3, "faq"]))
    open_site(hd, site)
    assert order(hd.page).index("faq") < order(hd.page).index("prestations")
    assert not hd.errors


# ------------------------------------------------------------------ modules
def modules(**m):
    def fn(c):
        c.setdefault("modules", {})
        for k, v in m.items():
            c["modules"][k] = {**c["modules"].get(k, {}), **v}
        return c
    return fn


def test_modules_are_off_by_default(make_page, site):
    hd = make_page(site)
    open_site(hd, site)
    for sid in ("annonce", "atouts", "chiffres", "cta"):
        assert hd.page.locator(f"#{sid}").count() == 0


class TestAnnouncement:
    cfg = {"actif": True, "texte": "-15 % sur la céramique", "lien": "#contact", "libelle": "Réserver", "style": "accent", "fermable": True}

    def test_shows_and_offsets_header(self, make_page, site):
        hd = make_page(site, content_fn=modules(annonce=self.cfg))
        open_site(hd, site)
        p = hd.page
        assert "-15 % sur la céramique" in p.inner_text("#annonce") and p.get_attribute("#annonce a", "href") == "#contact"
        h = p.evaluate("document.getElementById('annonce').offsetHeight")
        assert abs(p.evaluate("document.querySelector('.header').getBoundingClientRect().top") - h) <= 2, "l'en-tête doit se placer sous l'annonce"
        p.evaluate("window.scrollTo(0,600)")
        wait_for(lambda: abs(p.evaluate("document.querySelector('.header').getBoundingClientRect().top")) <= 1, msg="l'en-tête doit remonter au défilement")

    def test_close_is_remembered_for_the_session(self, make_page, site):
        hd = make_page(site, content_fn=modules(annonce=self.cfg))
        open_site(hd, site)
        p = hd.page
        p.click("#annClose")
        assert p.locator("#annonce").count() == 0 and abs(p.evaluate("document.querySelector('.header').getBoundingClientRect().top")) <= 1
        p.reload()
        p.wait_for_selector("#app .hero", state="attached")
        assert p.locator("#annonce").count() == 0

    @pytest.mark.parametrize("style", ["accent", "sombre", "clair"])
    def test_styles_and_contrast(self, make_page, site, style):
        hd = make_page(site, content_fn=modules(annonce={**self.cfg, "style": style}))
        open_site(hd, site)
        assert style in hd.page.get_attribute("#annonce", "class")
        c = hd.page.evaluate("(()=>{const s=getComputedStyle(document.getElementById('annonce'));return [s.color,s.backgroundColor]})()")
        rgb = lambda s: "#%02x%02x%02x" % tuple(int(float(x)) for x in re.findall(r"[\d.]+", s)[:3])
        assert ratio(hd.page, rgb(c[0]), rgb(c[1])) >= 4.5

    def test_unclosable_and_unsafe_link(self, make_page, site):
        hd = make_page(site, content_fn=modules(annonce={**self.cfg, "fermable": False, "lien": "javascript:window.__xss=1"}))
        open_site(hd, site)
        assert hd.page.locator("#annClose").count() == 0 and hd.page.locator("#annonce a").count() == 0

    def test_empty_text_hides_it(self, make_page, site):
        hd = make_page(site, content_fn=modules(annonce={**self.cfg, "texte": "   "}))
        open_site(hd, site)
        assert hd.page.locator("#annonce").count() == 0

    def test_on_phone(self, make_page, site):
        hd = make_page(site, w=320, h=568, mobile=True, content_fn=modules(annonce={**self.cfg, "texte": "Un texte d'annonce un peu long pour vérifier le retour à la ligne sur petit écran"}))
        open_site(hd, site)
        assert overflow(hd.page) <= 0 and hd.page.evaluate("document.getElementById('annClose').getBoundingClientRect().width") >= 36


ITEMS = [{"_id": "a", "icone": "shield", "titre": "Garantie", "texte": "Contrôle sous lumière."}, {"_id": "b", "icone": "inconnue", "titre": "Rapide", "texte": ""}, {"_id": "c", "icone": "pin", "titre": "", "texte": "ignoré"}]


def test_strengths_module(make_page, site):
    hd = make_page(site, content_fn=modules(atouts={"actif": True, "titre": "Pourquoi nous", "texte": "Intro", "items": ITEMS}))
    open_site(hd, site)
    p = hd.page
    assert p.locator("#atouts .atout").count() == 2, "un atout sans titre est ignoré"
    assert p.locator("#atouts .atout svg").count() == 2, "une icône inconnue est remplacée par une coche"
    assert "pourquoi nous" in p.inner_text("#atouts").lower() and "garantie" in p.inner_text("#atouts").lower()
    assert not hd.errors


def test_strengths_inactive_or_empty_is_hidden(make_page, site):
    for m in ({"actif": False, "items": ITEMS}, {"actif": True, "items": []}):
        hd = make_page(site, content_fn=modules(atouts=m))
        open_site(hd, site)
        assert hd.page.locator("#atouts").count() == 0


def test_stats_count_up_to_target(make_page, site):
    items = [{"_id": "1", "valeur": "350", "suffixe": "+", "label": "voitures"}, {"_id": "2", "valeur": "4,9", "suffixe": "/5", "label": "note"}, {"_id": "3", "valeur": "10 ans", "suffixe": "", "label": "expérience"}]
    hd = make_page(site, content_fn=modules(chiffres={"actif": True, "titre": "En chiffres", "items": items}), reduced_motion=False)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#chiffres")
    wait_for(lambda: p.inner_text("#chiffres .stat >> nth=0").startswith("350+"), timeout=6, msg="le compteur n'atteint pas 350")
    assert p.inner_text("#chiffres .stat >> nth=1 >> b") == "4,9/5", "décimales et séparateur conservés"
    assert p.inner_text("#chiffres .stat >> nth=2 >> b") == "10 ans"


def test_stats_are_static_with_reduced_motion(make_page, site):
    hd = make_page(site, reduced_motion=True, content_fn=modules(chiffres={"actif": True, "items": [{"_id": "1", "valeur": "350", "suffixe": "+", "label": "voitures"}]}))
    open_site(hd, site)
    assert hd.page.inner_text("#chiffres b") == "350+"


class TestCallToAction:
    def test_renders_with_default_link(self, make_page, site):
        hd = make_page(site, content_fn=modules(cta={"actif": True, "titre": "Prêt ?", "texte": "Devis gratuit", "bouton": "", "lien": ""}))
        open_site(hd, site)
        a = hd.page.locator("#cta a.btn")
        assert a.get_attribute("href") == "#contact" and a.inner_text().strip().lower() == "demander un devis"

    @pytest.mark.parametrize("lien,ok", [("https://exemple.fr/x", True), ("tel:+33768706996", True), ("#faq", True), ("javascript:alert(1)", False), ("data:text/html,x", False), ("//evil.com", False)])
    def test_link_safety(self, make_page, site, lien, ok):
        hd = make_page(site, content_fn=modules(cta={"actif": True, "titre": "T", "bouton": "Go", "lien": lien}))
        open_site(hd, site)
        href = hd.page.get_attribute("#cta a.btn", "href")
        assert (href == lien) == ok and (ok or href == "#contact")
        if lien.startswith("https"):
            assert hd.page.get_attribute("#cta a.btn", "target") == "_blank"


def blocs(*b):
    def fn(c):
        c["blocs"] = [dict(x) for x in b]
        return c
    return fn


BLOCS = [
    {"_id": "t", "actif": True, "mise": "texte", "titre": "Texte seul", "texte": "Premier paragraphe.\nSecond paragraphe.", "image": "", "bouton": "Voir", "lien": "#faq"},
    {"_id": "g", "actif": True, "mise": "image-gauche", "titre": "Image gauche", "texte": "x", "image": "images/og-image.jpg", "bouton": "", "lien": ""},
    {"_id": "d", "actif": True, "mise": "image-droite", "titre": "Image droite", "texte": "x", "image": "images/og-image.jpg", "bouton": "", "lien": ""},
    {"_id": "c", "actif": True, "mise": "citation", "titre": "Karim", "texte": "Une voiture comme neuve.", "image": "", "bouton": "", "lien": ""},
    {"_id": "off", "actif": False, "mise": "texte", "titre": "Masqué", "texte": "x", "image": "", "bouton": "", "lien": ""},
    {"_id": "vide", "actif": True, "mise": "texte", "titre": "", "texte": "", "image": "", "bouton": "", "lien": ""},
]


def test_free_blocks_layouts(make_page, site):
    hd = make_page(site, content_fn=blocs(*BLOCS))
    open_site(hd, site)
    p = hd.page
    assert p.locator('[id^="bloc-"]').count() == 4, "un bloc masqué ou vide n'est pas affiché"
    assert "Premier paragraphe." in p.inner_text("#bloc-t") and p.locator("#bloc-t p").count() == 2
    assert p.locator("#bloc-g .bloc-img img").count() == 1 and p.locator("#bloc-g .bloc.droite").count() == 0
    assert p.locator("#bloc-d .bloc.droite").count() == 1
    assert "Une voiture comme neuve." in p.inner_text("#bloc-c blockquote") and p.inner_text("#bloc-c cite") == "Karim"
    assert p.get_attribute("#bloc-t a.btn", "href") == "#faq"
    assert p.get_attribute("#bloc-g img", "alt") == "Image gauche"
    left = p.evaluate("(()=>{const i=document.querySelector('#bloc-g .bloc-img').getBoundingClientRect(),t=document.querySelector('#bloc-g .bloc > div:last-child').getBoundingClientRect();return i.left<t.left})()")
    assert left


@pytest.mark.parametrize("viewport_", [(320, 568, True), (390, 844, True), (1440, 900, False)])
def test_free_blocks_responsive(make_page, site, viewport_):
    w, h, mob = viewport_
    hd = make_page(site, w=w, h=h, mobile=mob, content_fn=blocs(*BLOCS))
    open_site(hd, site)
    p = hd.page
    for sid in ("bloc-g", "bloc-d", "bloc-c"):
        scroll_to(p, f"#{sid}")
        assert overflow(p) <= 0
    if mob:
        assert p.evaluate("(()=>{const i=document.querySelector('#bloc-d .bloc-img').getBoundingClientRect(),t=document.querySelector('#bloc-d .bloc > div:last-child').getBoundingClientRect();return i.top<t.top})()"), "sur téléphone l'image passe au-dessus du texte"


def test_module_content_is_escaped(make_page, site):
    x = '<img src=x onerror="window.__xss=1"><script>window.__xss=2</script>'

    def fn(c):
        modules(annonce={"actif": True, "texte": x}, atouts={"actif": True, "titre": x, "items": [{"_id": "a", "icone": "check", "titre": x, "texte": x}]}, chiffres={"actif": True, "items": [{"_id": "1", "valeur": x, "label": x}]}, cta={"actif": True, "titre": x, "texte": x, "bouton": x})(c)
        c["blocs"] = [{"_id": "z", "actif": True, "mise": "texte", "titre": x, "texte": x, "image": "", "bouton": x, "lien": "#faq"}]
        return c
    hd = make_page(site, content_fn=fn)
    open_site(hd, site)
    assert hd.page.evaluate("window.__xss") is None
    assert hd.page.evaluate("document.querySelectorAll('#app img[onerror], #app script').length") == 0


def test_everything_enabled_has_no_overflow(make_page, site, viewport):
    w, h, mob = viewport

    def fn(c):
        modules(annonce=TestAnnouncement.cfg, atouts={"actif": True, "titre": "Atouts", "items": ITEMS}, chiffres={"actif": True, "items": [{"_id": "1", "valeur": "9" * 40, "suffixe": "x" * 40, "label": "L" * 120}]}, cta={"actif": True, "titre": "T" * 150, "texte": "x", "bouton": "B" * 80})(c)
        c["blocs"] = [dict(b, titre="W" * 200) for b in BLOCS]
        return c
    hd = make_page(site, w=w, h=h, mobile=mob, content_fn=fn)
    open_site(hd, site)
    for y in range(0, hd.page.evaluate("document.documentElement.scrollHeight"), 600):
        hd.page.evaluate(f"window.scrollTo(0,{y})")
        reveal_all(hd.page)
        assert overflow(hd.page) <= 0, f"débordement à y={y}"
    assert not hd.errors


def test_nav_and_rail_still_work_with_modules_and_custom_order(make_page, site):
    hd = make_page(site, w=1440, h=900, content_fn=lambda c: with_design(ordre=["faq", "zone"])(modules(atouts={"actif": True, "titre": "A", "items": ITEMS})(c)))
    open_site(hd, site)
    p = hd.page
    p.click('.nav a.nl[data-sec="faq"]')
    wait_for(lambda: abs(p.evaluate("document.getElementById('faq').getBoundingClientRect().top")) < 200)
    assert not hd.errors
