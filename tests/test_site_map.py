"""Carte Google Maps (réponse de Google simulée : aucun accès réseau réel)."""
import urllib.parse

import pytest

from helpers import open_site, scroll_to, wait_for

pytestmark = pytest.mark.site

state = lambda p: p.evaluate("""(()=>{const m=document.getElementById('map'),f=document.getElementById('mapFrame');
    return {loaded:m.classList.contains('is-loaded'),slow:m.classList.contains('is-slow'),active:m.classList.contains('is-active'),
            src:f.getAttribute('src')||'',pe:getComputedStyle(f).pointerEvents,veil:parseFloat(getComputedStyle(m,'::before').opacity)}})()""")


def map_page(make_page, site, *, maps="fast", w=1280, h=900, mobile=False, content_fn=None, **kw):
    hd = make_page(site, w=w, h=h, mobile=mobile, maps=maps, content_fn=content_fn, **kw)
    open_site(hd, site)
    return hd


def go_to_map(hd):
    scroll_to(hd.page, "#map")


def test_map_is_requested_only_when_close(make_page, site):
    hd = map_page(make_page, site)
    p = hd.page
    p.wait_for_timeout(600)
    assert hd.map_requests == [], "Google ne doit pas être appelé tant que la carte est loin de l'écran"
    go_to_map(hd)
    wait_for(lambda: len(hd.map_requests) >= 1, msg="la carte n'est pas demandée à l'approche")
    wait_for(lambda: state(p)["loaded"], msg="la carte ne s'affiche pas")
    assert len(hd.map_requests) == 1, "une seule requête attendue"


def test_request_parameters_and_nothing_else_external(make_page, site):
    hd = map_page(make_page, site)
    go_to_map(hd)
    wait_for(lambda: hd.map_requests)
    q = urllib.parse.urlparse(hd.map_requests[0])
    params = urllib.parse.parse_qs(q.query)
    assert q.netloc == "www.google.com" and q.path == "/maps"
    assert params["q"] == ["Mantes-la-Jolie, France"] and params["output"] == ["embed"]
    assert hd.external == [], f"requêtes externes inattendues : {hd.external}"


@pytest.mark.parametrize("radius,zoom", [(5, "11"), (14, "11"), (15, "10"), (30, "10"), (31, "9"), (80, "9")])
def test_zoom_follows_radius(make_page, site, radius, zoom):
    def c(d):
        d["zone"]["rayonKm"] = radius
        return d
    hd = map_page(make_page, site, content_fn=c)
    go_to_map(hd)
    wait_for(lambda: hd.map_requests)
    assert urllib.parse.parse_qs(urllib.parse.urlparse(hd.map_requests[0]).query)["z"] == [zoom]


def test_falls_back_to_coordinates_without_label(make_page, site):
    def c(d):
        d["zone"]["centre"]["label"] = ""
        return d
    hd = map_page(make_page, site, content_fn=c)
    go_to_map(hd)
    wait_for(lambda: hd.map_requests)
    assert "48.9906" in urllib.parse.unquote(hd.map_requests[0])


def test_never_shows_an_empty_frame_while_google_is_slow(make_page, site):
    hd = map_page(make_page, site, maps="hold")
    p = hd.page
    go_to_map(hd)
    wait_for(lambda: hd.held, msg="requête non émise")
    s = state(p)
    assert not s["loaded"] and s["veil"] > 0.9, f"le fond d'attente doit rester opaque : {s}"
    hd.release_maps()
    wait_for(lambda: state(p)["loaded"] and state(p)["veil"] < 0.1, msg="la carte n'apparaît pas après la réponse")


def test_slow_google_shows_message_and_retry_works(make_page, site):
    hd = map_page(make_page, site, maps="hold")
    p = hd.page
    go_to_map(hd)
    wait_for(lambda: hd.held)
    wait_for(lambda: state(p)["slow"], timeout=14, msg="le message de lenteur n'apparaît pas")
    assert p.is_visible("#mapSlow") and not state(p)["loaded"]
    p.click("#mapRetry")
    wait_for(lambda: len(hd.map_requests) >= 2)
    assert "&_=" in hd.map_requests[-1], "le rechargement doit contourner le cache"
    wait_for(lambda: state(p)["loaded"] and not state(p)["slow"])


def test_blocked_google_does_not_break_the_page(make_page, site):
    hd = map_page(make_page, site, maps=None)
    go_to_map(hd)
    hd.page.wait_for_timeout(800)
    assert not hd.errors, hd.errors
    assert hd.page.is_visible(".map-link"), "le lien de secours vers Google Maps doit rester visible"


# ------------------------------------------------------------------ verrouillage
class TestLock:
    def test_locked_by_default_and_taps_do_not_unlock(self, make_page, site):
        hd = map_page(make_page, site, w=390, h=844, mobile=True)
        p = hd.page
        go_to_map(hd)
        wait_for(lambda: state(p)["loaded"])
        assert not state(p)["active"] and state(p)["pe"] == "none"
        box = p.locator("#map").bounding_box()
        p.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + 40)
        p.mouse.click(box["x"] + box["width"] / 2, box["y"] + 40)
        assert not state(p)["active"], "un simple contact ne doit pas déverrouiller la carte"

    def test_page_scrolls_when_swiping_over_locked_map(self, make_page, site):
        hd = map_page(make_page, site, w=390, h=844, mobile=True)
        p = hd.page
        go_to_map(hd)
        wait_for(lambda: state(p)["loaded"])
        box = p.locator("#map").bounding_box()
        x, y0 = box["x"] + box["width"] / 2, max(80, min(700, box["y"] + box["height"] / 2))
        cdp = hd.context.new_cdp_session(p)
        before = p.evaluate("scrollY")
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
        for i in range(1, 9):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 - i * 40}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        wait_for(lambda: p.evaluate("scrollY") > before + 80, msg="la page ne défile pas au-dessus de la carte verrouillée")
        assert not state(p)["active"]

    def test_wheel_scrolls_page_over_locked_map_on_desktop(self, make_page, site):
        hd = map_page(make_page, site)
        p = hd.page
        go_to_map(hd)
        wait_for(lambda: state(p)["loaded"])
        box = p.locator("#map").bounding_box()
        p.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        before = p.evaluate("scrollY")
        p.mouse.wheel(0, 400)
        wait_for(lambda: p.evaluate("scrollY") > before + 100, msg="la molette ne fait pas défiler la page au-dessus de la carte")

    def test_button_unlocks_and_relocks(self, make_page, site):
        hd = map_page(make_page, site)
        p = hd.page
        go_to_map(hd)
        wait_for(lambda: state(p)["loaded"])
        assert p.get_attribute("#mapHint", "aria-pressed") == "false"
        p.click("#mapHint")
        s = state(p)
        assert s["active"] and s["pe"] == "auto" and p.get_attribute("#mapHint", "aria-pressed") == "true"
        assert "Verrouiller" in p.inner_text("#mapHint")
        p.click("#mapHint")
        assert not state(p)["active"]

    @pytest.mark.parametrize("how", ["tap_outside", "escape", "scroll_away"])
    def test_auto_relock(self, make_page, site, how):
        hd = map_page(make_page, site)
        p = hd.page
        go_to_map(hd)
        wait_for(lambda: state(p)["loaded"])
        p.click("#mapHint")
        assert state(p)["active"]
        if how == "tap_outside":
            p.mouse.click(5, 5)
        elif how == "escape":
            p.keyboard.press("Escape")
        else:
            p.evaluate("window.scrollTo(0,0)")
        wait_for(lambda: not state(p)["active"], msg=f"la carte reste déverrouillée ({how})")


# ------------------------------------------------------------------ lien de secours + mise en page
def test_open_in_maps_link_is_outside_the_map(make_page, site):
    hd = map_page(make_page, site)
    p = hd.page
    go_to_map(hd)
    link = p.locator(".map-link")
    href = link.get_attribute("href")
    assert href.startswith("https://www.google.com/maps/search/") and "Mantes-la-Jolie" in urllib.parse.unquote(href)
    assert link.get_attribute("target") == "_blank" and "noopener" in link.get_attribute("rel")
    assert p.evaluate("document.querySelectorAll('#map a').length") == 0, "aucun lien ne doit se trouver sur la carte (touches accidentelles)"


def test_map_accessibility(make_page, site):
    hd = map_page(make_page, site)
    p = hd.page
    go_to_map(hd)
    assert "Mantes-la-Jolie" in p.get_attribute("#mapFrame", "title")
    assert p.evaluate("document.getElementById('mapHint').tagName") == "BUTTON"


def test_map_layout_on_all_sizes(make_page, site, viewport):
    w, h, mob = viewport
    hd = map_page(make_page, site, w=w, h=h, mobile=mob)
    p = hd.page
    go_to_map(hd)
    wait_for(lambda: state(p)["loaded"])
    m = p.evaluate("(()=>{const r=document.getElementById('map').getBoundingClientRect(),l=document.querySelector('.map-link').getBoundingClientRect(),hint=document.getElementById('mapHint').getBoundingClientRect();return {w:r.width,h:r.height,right:r.right,linkBelow:l.top>=r.bottom-1,hintInside:hint.left>=r.left-1&&hint.right<=r.right+1,sw:document.documentElement.scrollWidth}})()")
    assert m["h"] >= 240 and m["right"] <= w + 1 and m["sw"] <= w
    assert m["linkBelow"], "le lien « Ouvrir dans Google Maps » doit être sous la carte"
    assert m["hintInside"], "le bouton d'interaction sort de la carte"
