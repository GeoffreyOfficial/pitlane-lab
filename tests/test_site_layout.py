"""Mise en page responsive du site public, sur 7 tailles d'écran (17 avec --full)."""
import pytest

from helpers import Problems, open_site, overflow, reveal_all, scroll_to

pytestmark = pytest.mark.site


@pytest.fixture()
def home(make_page, site, viewport):
    w, h, mob = viewport
    hd = make_page(site, w=w, h=h, mobile=mob)
    open_site(hd, site)
    return hd, w, h, mob


def test_no_horizontal_overflow_while_scrolling(home):
    hd, w, h, _ = home
    p, bad = hd.page, Problems()
    total = p.evaluate("document.documentElement.scrollHeight")
    for y in range(0, total, max(200, h // 2)):
        p.evaluate(f"window.scrollTo(0,{y})")
        reveal_all(p)
        bad.check(overflow(p) <= 0, f"débordement horizontal de {overflow(p)} px à y={y}")
    bad.assert_none()
    assert not hd.errors, hd.errors


def test_every_section_is_rendered_and_visible_size(home):
    hd, w, h, _ = home
    p, bad = hd.page, Problems()
    for sec in ["accueil", "prestations", "details", "resultats", "methode", "apropos", "zone", "faq", "contact"]:
        box = p.evaluate(f"(()=>{{const e=document.getElementById('{sec}'); if(!e) return null; const r=e.getBoundingClientRect(); return [r.width,r.height]}})()")
        bad.check(box is not None, f"section #{sec} absente")
        if box:
            bad.check(box[0] >= w - 2 and box[1] > 80, f"section #{sec} de taille anormale {box}")
    bad.assert_none()


def test_hero_fits_and_does_not_overlap(home):
    hd, w, h, _ = home
    p, bad = hd.page, Problems()
    p.evaluate("window.scrollTo(0,0)")
    m = p.evaluate("""(()=>{const R=s=>{const e=document.querySelector(s); return e?e.getBoundingClientRect():null};
        const hero=R('.hero'),pts=R('.hero-points'),car=R('.pit-car'),h1=R('.hero h1'),hd=R('.header'),btn=R('.hero-cta');
        return {heroH:hero.height,heroBottom:hero.bottom,ptsBottom:pts?pts.bottom:0,carTop:car?car.top:null,h1Top:h1.top,h1Left:h1.left,h1Right:h1.right,headerBottom:hd.bottom,btnBottom:btn?btn.bottom:0}})()""")
    bad.check(m["h1Top"] >= m["headerBottom"] - 2, f"le titre passe sous l'en-tête ({m['h1Top']:.0f} < {m['headerBottom']:.0f})")
    bad.check(m["h1Left"] >= 0 and m["h1Right"] <= w + 1, "le titre déborde horizontalement")
    if w >= 900 and h >= 600:
        bad.check(m["heroH"] <= h + 2, f"l'accueil ({m['heroH']:.0f}px) dépasse la hauteur de l'écran ({h}px)")
    if w >= 700 and h > 520 and m["carTop"] is not None:
        bad.check(m["ptsBottom"] <= m["carTop"] + 1, f"le texte d'accueil chevauche la silhouette de {m['ptsBottom'] - m['carTop']:.0f}px")
    bad.check(m["btnBottom"] > 0, "boutons d'accueil introuvables")
    bad.assert_none()


def test_cards_are_aligned_and_equal(home):
    hd, w, h, _ = home
    p, bad = hd.page, Problems()
    scroll_to(p, "#cards", "start")
    rects = p.evaluate("[...document.querySelectorAll('#cards .card')].map(e=>{const r=e.getBoundingClientRect(); return [r.left,r.top+scrollY,r.width,r.height]})")
    assert len(rects) >= 3
    widths = [round(r[2]) for r in rects]
    bad.check(max(widths) - min(widths) <= 2, f"cartes de largeurs différentes : {widths}")
    rows = {}
    for r in rects:
        rows.setdefault(round(r[1] / 10), []).append(r)
    for _, row in rows.items():
        hs = [round(r[3]) for r in row]
        bad.check(max(hs) - min(hs) <= 2, f"cartes d'une même ligne de hauteurs différentes : {hs}")
        lefts = sorted(r[0] for r in row)
        bad.check(all(lefts[i + 1] - lefts[i] > 20 for i in range(len(lefts) - 1)), "cartes qui se chevauchent")
    bad.assert_none()


def test_typography_has_sane_sizes(home):
    hd, w, h, _ = home
    p, bad = hd.page, Problems()
    sizes = p.evaluate("""(()=>{const f=s=>{const e=document.querySelector(s); return e?parseFloat(getComputedStyle(e).fontSize):null};
        return {h1:f('.hero h1'),h2:f('.h2'),lead:f('.lead'),body:f('body'),card:f('.card p.res'),price:f('.price b'),nav:f('.nav a.nl')||f('.menu a.ml')}})()""")
    bad.check(sizes["h1"] <= 96, f"titre d'accueil trop grand : {sizes['h1']:.0f}px")
    bad.check(sizes["h2"] <= 56, f"titre de section trop grand : {sizes['h2']:.0f}px")
    bad.check(sizes["lead"] <= 24, f"texte d'introduction trop grand : {sizes['lead']:.0f}px")
    bad.check(sizes["body"] <= 19, f"texte courant trop grand : {sizes['body']:.0f}px")
    bad.check(sizes["card"] >= 14, f"texte des cartes trop petit : {sizes['card']:.0f}px")
    bad.check(sizes["h1"] >= 30 and sizes["h2"] >= 24, f"titres trop petits : h1 {sizes['h1']:.0f}, h2 {sizes['h2']:.0f}")
    bad.assert_none()


def test_touch_targets_on_mobile(home):
    hd, w, h, mob = home
    if not mob:
        pytest.skip("cibles tactiles : écrans tactiles uniquement")
    p, bad = hd.page, Problems()
    scroll_to(p, "#prestations", "start")
    small = p.evaluate("""[...document.querySelectorAll('.btn,.chip,.card,.burger,.qa>button,.mbar a')].filter(e=>e.offsetParent&&!e.closest('dialog')&&getComputedStyle(e).visibility!=='hidden').map(e=>{const r=e.getBoundingClientRect();return [e.className||e.tagName,Math.round(r.height),Math.round(r.width)]}).filter(x=>x[1]>0&&(x[1]<40||x[2]<40))""")
    bad.check(not small, f"cibles tactiles trop petites (<40px) : {small[:6]}")
    bad.assert_none()


def test_header_navigation_mode_matches_width(home):
    hd, w, h, _ = home
    p = hd.page
    burger = p.is_visible("#burger")
    links = p.is_visible(".nav a.nl >> nth=0")
    if w <= 980:
        assert burger and not links, "sous 980px : le burger doit remplacer les liens"
    else:
        assert links and not burger, "au-dessus de 980px : liens visibles, pas de burger"
    box = p.evaluate("(()=>{const l=document.querySelector('.brand img, .brand-txt').getBoundingClientRect(), h=document.querySelector('.header').getBoundingClientRect(); return [l.top>=h.top-1, l.bottom<=h.bottom+1, l.right<=innerWidth]})()")
    assert all(box), f"le logo sort de l'en-tête ou de l'écran : {box}"


def test_images_load_and_keep_their_proportions(home):
    hd, w, h, _ = home
    p, bad = hd.page, Problems()
    for y in range(0, p.evaluate("document.documentElement.scrollHeight"), max(300, h)):
        p.evaluate(f"window.scrollTo(0,{y})")
        p.wait_for_timeout(60)
    reveal_all(p)
    res = p.evaluate("""[...document.images].filter(i=>i.offsetParent&&getComputedStyle(i).visibility!=='hidden').map(i=>({src:i.currentSrc.split('/').slice(-2).join('/'),ok:i.complete&&i.naturalWidth>0,
        dist:(i.naturalWidth&&i.clientWidth&&i.clientHeight&&getComputedStyle(i).objectFit==='fill')?Math.abs((i.clientWidth/i.clientHeight)/(i.naturalWidth/i.naturalHeight)-1):0}))""")
    for r in res:
        bad.check(r["ok"], f"image non chargée : {r['src']}")
        bad.check(r["dist"] < 0.03, f"image déformée ({r['dist']:.0%}) : {r['src']}")
    bad.assert_none()


def test_fonts_are_loaded(home):
    hd, *_ = home
    ok = hd.page.evaluate("Promise.all([document.fonts.load('italic 800 20px Saira'),document.fonts.load('400 16px Barlow')]).then(()=>document.fonts.check('italic 800 20px Saira')&&document.fonts.check('400 16px Barlow'))")
    assert ok, "les polices du site ne se chargent pas"


def test_sticky_header_and_progress_bar(home):
    hd, w, h, _ = home
    p = hd.page
    p.evaluate("window.scrollTo(0,600)")
    p.wait_for_function("document.querySelector('.header').classList.contains('is-stuck')")
    top = p.evaluate("document.querySelector('.header').getBoundingClientRect().top")
    assert abs(top) <= 1, "l'en-tête doit rester collé en haut"
    p.evaluate("window.scrollTo(0,document.documentElement.scrollHeight)")
    p.wait_for_function("getComputedStyle(document.getElementById('lap')).transform!=='none' && new DOMMatrix(getComputedStyle(document.getElementById('lap')).transform).a>0.9")


def test_reduced_motion_shows_everything_immediately(make_page, site, viewport):
    w, h, mob = viewport
    hd = make_page(site, w=w, h=h, mobile=mob, reduced_motion=True)
    p = hd.page
    p.wait_for_selector("#app .hero", state="attached")
    assert p.locator("#start").count() == 0, "pas d'écran d'intro en mode « réduire les animations »"
    assert p.is_visible(".hero h1")
    p.evaluate("window.scrollTo(0,1200)")
    assert p.evaluate("[...document.querySelectorAll('.rv')].filter(e=>getComputedStyle(e).opacity==='0').length") == 0, "des éléments restent invisibles"
    assert not hd.errors
