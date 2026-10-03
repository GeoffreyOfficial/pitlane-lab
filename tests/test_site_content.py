"""Robustesse du site face au contenu : branding, contenu dégradé ou hostile, SEO, accessibilité, hors ligne."""
import json

import pytest

from helpers import Problems, open_site, overflow, scroll_to, wait_for

pytestmark = pytest.mark.site


def page_with(make_page, site, fn=None, content=None, **kw):
    hd = make_page(site, content_fn=fn, content=content, **kw)
    return hd


# ------------------------------------------------------------------ propreté générale
def test_clean_load_no_errors_no_404_no_external(make_page, site, viewport):
    w, h, mob = viewport
    hd = make_page(site, w=w, h=h, mobile=mob)
    open_site(hd, site)
    for y in range(0, hd.page.evaluate("document.documentElement.scrollHeight"), 700):
        hd.page.evaluate(f"window.scrollTo(0,{y})")
    hd.page.wait_for_timeout(400)
    assert not hd.errors, hd.errors
    assert not hd.bad_responses, f"ressources en échec : {hd.bad_responses}"
    assert not [u for u in hd.external if "google.com/maps" not in u], hd.external


def test_page_weight_budget(make_page, site):
    hd = make_page(site)
    open_site(hd, site)
    total = hd.page.evaluate("performance.getEntriesByType('resource').reduce((a,r)=>a+(r.encodedBodySize||0),0)") / 1024
    assert total < 1500, f"la page pèse {total:.0f} Ko au chargement (budget 1500 Ko)"


# ------------------------------------------------------------------ SEO et accessibilité
def test_seo_metadata(make_page, site):
    c = site.content()
    hd = make_page(site)
    open_site(hd, site)
    p = hd.page
    assert p.title() == c["seo"]["siteTitle"]
    assert p.get_attribute('meta[name="description"]', "content") == c["seo"]["description"]
    assert p.get_attribute('meta[property="og:title"]', "content") == c["seo"]["siteTitle"]
    assert p.get_attribute('meta[property="og:image"]', "content").endswith("og-image.jpg")
    assert p.get_attribute("link[rel=canonical]", "href") == c["seo"]["siteUrl"].rstrip("/") + "/"
    ld = json.loads(p.inner_text("#jsonLd") if p.locator("#jsonLd").count() else p.evaluate("document.querySelector('script[type=\"application/ld+json\"]').textContent"))
    assert ld["@context"] == "https://schema.org" and ld["name"] == c["branding"]["nom"]
    assert len(ld["makesOffer"]) == len([s for s in c["services"] if s.get("visible", True)])
    assert p.get_attribute("html", "lang") == "fr"


def test_document_structure_and_accessibility_basics(make_page, site):
    hd = make_page(site, w=1280, h=900)
    open_site(hd, site)
    p, bad = hd.page, Problems()
    bad.check(p.locator("h1").count() == 1, "il doit y avoir exactement un h1")
    for lm in ["header", "main", "footer", "nav"]:
        bad.check(p.locator(lm).count() >= 1, f"repère de page manquant : <{lm}>")
    levels = p.evaluate("[...document.querySelectorAll('h1,h2,h3')].map(h=>+h.tagName[1])")
    bad.check(all(b - a <= 1 for a, b in zip(levels, levels[1:])), f"hiérarchie de titres cassée : {levels}")
    nameless = p.evaluate("""[...document.querySelectorAll('a,button')].filter(e=>e.offsetParent!==null||e.closest('dialog')).filter(e=>!(e.textContent.trim()||e.getAttribute('aria-label')||e.getAttribute('title')||e.querySelector('img[alt]:not([alt=""])'))).map(e=>e.outerHTML.slice(0,80))""")
    bad.check(not nameless, f"liens ou boutons sans nom accessible : {nameless[:4]}")
    noalt = p.evaluate("[...document.images].filter(i=>!i.hasAttribute('alt')).map(i=>i.src.split('/').pop())")
    bad.check(not noalt, f"images sans attribut alt : {noalt}")
    bad.check(p.evaluate("[...document.querySelectorAll('[id]')].map(e=>e.id).filter((x,i,a)=>a.indexOf(x)!==i).length") == 0, "identifiants HTML en double")
    bad.check(p.evaluate("[...document.querySelectorAll('[aria-controls]')].every(e=>document.getElementById(e.getAttribute('aria-controls')))"), "aria-controls pointe vers un élément absent")
    bad.assert_none()


def test_color_contrast_of_key_pairs(make_page, site):
    hd = make_page(site, w=1280, h=900)
    open_site(hd, site)
    rows = hd.page.evaluate("""(()=>{const rgb=s=>s.match(/[\\d.]+/g).slice(0,3).map(Number);
        const lum=c=>{const a=c.map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
        const bgOf=e=>{while(e){const c=getComputedStyle(e).backgroundColor; if(!/rgba\\(.*,\\s*0\\)|transparent/.test(c)) return rgb(c); e=e.parentElement} return [8,9,11]};
        const ratio=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
        const sel={'texte courant':'.lead','titre':'.h2','carte':'.card p.res','bouton principal':'.hero-cta .btn','lien de menu':'.nav a.nl','pied de page':'.foot-links a'};
        const out={}; for(const [k,s] of Object.entries(sel)){const e=document.querySelector(s); if(!e) continue; out[k]=+ratio(rgb(getComputedStyle(e).color),bgOf(e)).toFixed(2)} return out})()""")
    for k, r in rows.items():
        assert r >= 4.5, f"contraste insuffisant pour « {k} » : {r}:1 (minimum 4,5:1)"


# ------------------------------------------------------------------ branding
def brand(**b):
    def fn(c):
        c["branding"] = {"nom": "Pitlane Lab", "logo": "images/logo-full.png", "logoHauteur": 2.9, "logoPied": "", "silhouette": "images/car-lines.png", "silhouetteActive": True, "icone": "", **b}
        return c
    return fn


def test_old_content_without_branding_keeps_original_look(make_page, site):
    def drop(c):
        c.pop("branding", None)
        return c
    hd = page_with(make_page, site, drop)
    open_site(hd, site)
    assert "logo-full.png" in hd.page.get_attribute(".brand img", "src")
    assert hd.page.locator(".pit-car").count() == 1 and not hd.errors


def test_custom_logo_size_footer_logo_and_hidden_silhouette(make_page, site):
    hd = page_with(make_page, site, brand(nom="Detailing Mantes", logo="images/icon-512.png", logoHauteur=3.8, logoPied="images/favicon-48x48.png", silhouetteActive=False))
    open_site(hd, site)
    p = hd.page
    assert "icon-512" in p.get_attribute(".brand img", "src") and p.get_attribute(".brand img", "alt") == "Detailing Mantes"
    assert p.evaluate("document.querySelector('.brand img').getBoundingClientRect().height") > 55
    assert "favicon-48" in p.get_attribute(".foot-grid img", "src")
    assert p.locator(".pit-car").count() == 0


@pytest.mark.parametrize("ratio_img,expected", [("images/icon-512.png", "512/512"), ("images/og-image.jpg", "1200/630")])
def test_custom_silhouette_proportions_are_respected(make_page, site, ratio_img, expected):
    hd = page_with(make_page, site, brand(silhouette=ratio_img))
    open_site(hd, site)
    wait_for(lambda: hd.page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--car-ar').trim()") == expected, msg="proportions de la silhouette non appliquées")
    assert ratio_img in hd.page.get_attribute("#dxCar img", "src")


def test_text_logo_when_no_image(make_page, site):
    hd = page_with(make_page, site, brand(nom="Jermaine Detailing", logo=""))
    open_site(hd, site)
    p = hd.page
    assert p.locator(".brand-txt").count() == 1 and p.locator(".foot-txt").count() == 1 and p.locator(".brand img").count() == 0
    assert p.locator("#start .slogo").count() == 0
    assert p.evaluate("document.querySelector('.brand-txt').getBoundingClientRect().right") < p.evaluate("innerWidth")


@pytest.mark.parametrize("value", [1.4, 4.2, 99, -5, "abc", None])
def test_logo_height_is_clamped_on_mobile(make_page, site, value):
    hd = page_with(make_page, site, brand(logoHauteur=value), w=390, h=844, mobile=True)
    open_site(hd, site)
    hh = hd.page.evaluate("document.querySelector('.brand img').getBoundingClientRect().height")
    assert 10 < hh <= 80 and overflow(hd.page) <= 0


def test_site_icon_and_dynamic_manifest(make_page, site):
    hd = page_with(make_page, site, brand(nom="Jermaine Detailing", icone="images/icon-512.png"))
    open_site(hd, site)
    p = hd.page
    icons = p.evaluate("[...document.querySelectorAll('link[rel=icon]')].map(l=>l.href)")
    assert len(icons) == 1 and "icon-512" in icons[0]
    assert "icon-512" in p.get_attribute("link[rel=apple-touch-icon]", "href")
    mf = p.evaluate("fetch(document.querySelector('link[rel=manifest]').href).then(r=>r.json())")
    assert mf["name"] == "Jermaine Detailing" and mf["display"] == "standalone" and "icon-512" in mf["icons"][0]["src"]


# ------------------------------------------------------------------ thème et visibilité
def test_theme_colors_are_applied(make_page, site):
    def fn(c):
        c["theme"].update({"accent": "#0a6cff", "accentHot": "#3b8bff", "bg": "#101418"})
        return c
    hd = page_with(make_page, site, fn)
    open_site(hd, site)
    p = hd.page
    assert p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()") == "#0a6cff"
    assert p.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(16, 20, 24)"
    assert p.get_attribute('meta[name="theme-color"]', "content") == "#101418"


def test_invalid_theme_colors_are_ignored(make_page, site):
    def fn(c):
        c["theme"].update({"accent": "rouge", "bg": "#zzz"})
        return c
    hd = page_with(make_page, site, fn)
    open_site(hd, site)
    assert not hd.errors
    assert hd.page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()") == "#e10a1e"


@pytest.mark.parametrize("key,section", [("resultats", "resultats"), ("methode", "methode"), ("apropos", "apropos"), ("zone", "zone"), ("faq", "faq")])
def test_hiding_a_section_hides_its_menu_link(make_page, site, key, section):
    def fn(c):
        c["visibility"][key] = False
        return c
    hd = page_with(make_page, site, fn, w=1440, h=900)
    open_site(hd, site)
    p = hd.page
    assert p.locator(f"#{section}").count() == 0, f"la section {section} doit disparaître"
    assert p.locator(f'.nav a.nl[data-sec="{section}"]').count() == 0, "le lien de menu doit disparaître avec la section"
    assert not hd.errors


def test_mobile_bar_can_be_disabled(make_page, site):
    def fn(c):
        c["visibility"]["barreMobile"] = False
        return c
    hd = page_with(make_page, site, fn, w=390, h=844, mobile=True)
    open_site(hd, site)
    hd.page.evaluate("window.scrollTo(0,1500)")
    assert hd.page.evaluate("getComputedStyle(document.getElementById('mbar')).display") == "none"


# ------------------------------------------------------------------ contenu dégradé ou hostile
DEGRADED = {
    "vide": lambda c: {},
    "listes vides": lambda c: {**c, "services": [], "faq": [], "etapes": [], "avantApres": [], "galerie": [], "avis": [], "zones": [], "nav": []},
    "valeurs nulles": lambda c: {k: (None if isinstance(v, (str, int, float)) else v) for k, v in c.items()},
    "types inattendus": lambda c: {**c, "services": "oups", "faq": {"a": 1}, "hero": ["x"], "zone": 12, "theme": "rouge", "contact": None, "nav": [None, 3, {"id": "x"}]},
    "éléments partiels": lambda c: {**c, "services": [{}, {"titre": "Seul"}, {"prix": "10 €"}], "faq": [{}, {"q": "Q seule"}], "etapes": [{}], "avis": [{}]},
}


@pytest.mark.parametrize("name", list(DEGRADED))
def test_degraded_content_never_crashes(make_page, site, name):
    hd = page_with(make_page, site, DEGRADED[name])
    hd.page.wait_for_selector("#app", state="attached")
    hd.page.wait_for_timeout(700)
    assert not hd.errors, f"erreur JavaScript avec le contenu « {name} » : {hd.errors}"
    assert hd.page.inner_text("#app").strip(), "la page est vide"
    assert overflow(hd.page) <= 0


def test_content_fetch_failure_shows_a_recovery_message(make_page, site):
    hd = make_page(site, goto=False)
    hd.context.route("**/content.json", lambda r: r.fulfill(status=500, body="erreur"))
    hd.page.goto(site.url + "/index.html")
    hd.page.wait_for_selector("#app h1", state="attached", timeout=10000)
    txt = hd.page.inner_text("#app")
    assert "pas pu se charger" in txt.lower() and hd.page.locator("#app button").count() == 1
    assert not [e for e in hd.errors if "pageerror" in e]


XSS = '<img src=x onerror="window.__xss=1"><script>window.__xss=2</script>"\'><b>gras</b>'


def test_hostile_text_is_never_executed_or_interpreted(make_page, site):
    def fn(c):
        c["hero"]["titre"] = XSS
        c["services"][0]["titre"] = XSS
        c["services"][0]["description"] = XSS
        c["services"][0]["inclus"] = [XSS]
        c["faq"][0]["q"] = XSS
        c["faq"][0]["a"] = XSS
        c["avis"] = [{"_id": "x", "nom": XSS, "vehicule": XSS, "texte": XSS}]
        c["zone"]["communes"] = [XSS]
        c["footer"]["copyright"] = XSS
        c["legal"]["texte"] = XSS
        c["galerie"] = [{"_id": "g", "src": "images/og-image.jpg", "alt": XSS}]
        c["visibility"]["galerie"] = True
        c["visibility"]["avis"] = True
        return c
    hd = page_with(make_page, site, fn)
    open_site(hd, site)
    p = hd.page
    scroll_to(p, "#cards")
    p.click("#cards .card >> nth=0")
    p.wait_for_selector("#dlgService[open]", state="attached")
    p.keyboard.press("Escape")
    p.click("#legalBtn")
    p.keyboard.press("Escape")
    p.wait_for_timeout(500)
    assert p.evaluate("window.__xss") is None, "du code saisi dans le contenu a été exécuté"
    assert p.evaluate("document.querySelectorAll('#app img[onerror], #app script, dialog img[onerror], dialog script').length") == 0
    assert "img src=x" in p.inner_text("#app .hero h1").lower(), "le texte doit être affiché tel quel, sans être interprété"


def test_dangerous_link_schemes_are_not_rendered(make_page, site):
    def fn(c):
        c["contact"].update({"instagram": "javascript:window.__xss=1", "facebook": "data:text/html,<script>1</script>", "tiktok": "vbscript:x"})
        return c
    hd = page_with(make_page, site, fn)
    open_site(hd, site)
    hrefs = hd.page.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))")
    bad = [h for h in hrefs if h.lower().strip().startswith(("javascript:", "data:", "vbscript:"))]
    assert not bad, f"liens dangereux présents dans la page : {bad}"


def test_very_long_unbroken_words_do_not_break_the_layout(make_page, site):
    long = "A" * 300

    def fn(c):
        c["services"][0].update({"titre": long, "resume": long, "categorie": long})
        c["faq"][0].update({"q": long, "a": long})
        c["hero"]["titre"] = long
        c["footer"]["tagline"] = long
        c["apropos"]["titre"] = long
        return c
    for w, h, mob in [(320, 568, True), (1280, 800, False)]:
        hd = page_with(make_page, site, fn, w=w, h=h, mobile=mob)
        open_site(hd, site)
        for y in range(0, hd.page.evaluate("document.documentElement.scrollHeight"), 500):
            hd.page.evaluate(f"window.scrollTo(0,{y})")
            assert overflow(hd.page) <= 0, f"débordement horizontal ({w}px) avec un mot très long à y={y}"


def test_emoji_unicode_and_rtl_text(make_page, site):
    def fn(c):
        c["hero"]["titre"] = "Voiture 🚗✨ مرحبا 日本語 Ünïcödé"
        c["services"][0]["titre"] = "Lavage 🧽 مرحبا"
        return c
    hd = page_with(make_page, site, fn)
    open_site(hd, site)
    assert "🚗" in hd.page.inner_text(".hero h1") and not hd.errors


# ------------------------------------------------------------------ hors ligne et service worker
def test_renders_from_cache_when_content_is_unreachable(make_page, site):
    hd = make_page(site)
    open_site(hd, site)
    hd.context.route("**/content.json", lambda r: r.abort())
    hd.page.reload()
    hd.page.wait_for_selector("#app .hero", state="attached", timeout=10000)
    assert hd.page.locator("#cards .card").count() >= 3, "le site doit s'afficher depuis la copie locale"


def test_service_worker_serves_updates_and_works_offline(make_page, site_copy):
    hd = make_page(site_copy, sw="allow", maps=None)
    p = hd.page
    p.wait_for_selector("#app .hero", state="attached")
    p.evaluate("navigator.serviceWorker.ready.then(()=>true)")
    p.reload()
    wait_for(lambda: p.evaluate("!!navigator.serviceWorker.controller"), timeout=10, msg="le service worker ne prend pas le contrôle")
    title = p.inner_text(".hero h1")
    # mise à jour publiée : le visiteur doit la voir au rechargement
    c = site_copy.content()
    c["hero"]["titre"] = "Nouveau titre publié"
    site_copy.write_content(c)
    p.reload()
    p.wait_for_selector("#app .hero", state="attached")
    wait_for(lambda: "nouveau titre publié" in p.inner_text(".hero h1").lower(), msg="la mise à jour de content.json n'apparaît pas (cache périmé)")
    assert title.lower() != "nouveau titre publié"
    # hors ligne
    hd.context.set_offline(True)
    p.reload()
    p.wait_for_selector("#app .hero", state="attached", timeout=10000)
    assert p.locator("#cards .card").count() >= 3, "le site ne s'ouvre pas hors ligne"
    hd.context.set_offline(False)
