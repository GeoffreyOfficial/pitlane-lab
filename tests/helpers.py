"""Fonctions utilitaires partagées par les tests."""
import io
import json
import time
import zipfile

from playwright.sync_api import expect

from conftest import FIXTURES, ROOT  # noqa: F401


ACTIVE = {"page": None}   # page courante : renseignée par conftest.make_page


def _pause(seconds):
    """Attend en laissant Playwright traiter les événements (requêtes interceptées, etc.). Un simple sleep les ignorerait."""
    pg = ACTIVE["page"]
    if pg is not None:
        try:
            pg.wait_for_timeout(max(1, int(seconds * 1000)))
            return
        except Exception:
            pass
    time.sleep(seconds)


def wait_for(pred, timeout=6.0, interval=0.05, msg="condition non atteinte"):
    """Attend qu'une condition Python devienne vraie (sans sommeil fixe)."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = pred()
            if last:
                return last
        except Exception as e:  # la page peut être en train de changer
            last = e
        _pause(interval)
    raise AssertionError(f"{msg} (dernière valeur : {last!r})")


class Problems:
    """Collecte plusieurs constats avant d'échouer : un seul test affiche tous les défauts."""

    def __init__(self):
        self.items = []

    def check(self, cond, message):
        if not cond:
            self.items.append(message)

    def assert_none(self):
        assert not self.items, "\n - " + "\n - ".join(self.items)


# --------------------------------------------------------------------------- site public
def open_site(h, site, *, skip_intro=True, reveal=True):
    """Ouvre le site, attend le rendu complet, passe l'écran d'intro."""
    page = h.page
    if page.url == "about:blank":
        page.goto(site.url + "/index.html")
    page.wait_for_selector("#app .hero", state="attached", timeout=15000)
    if skip_intro:
        page.evaluate("(()=>{const s=document.getElementById('start'); if(s) s.click();})()")
        page.wait_for_function("!document.getElementById('start')", timeout=8000)
    if reveal:
        reveal_all(page)
    return h


def reveal_all(page):
    page.evaluate("document.querySelectorAll('.rv').forEach(e=>e.classList.add('in'))")


def scroll_to(page, selector, block="center"):
    page.evaluate("([s,b])=>{const e=document.querySelector(s); if(!e) throw new Error('introuvable: '+s); e.scrollIntoView({block:b})}", [selector, block])
    reveal_all(page)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - innerWidth")


def last_send(page):
    return page.evaluate("window.__lastSend || null")


# --------------------------------------------------------------------------- admin
def open_admin(h, site, *, path="admin.html"):
    page = h.page
    if page.url == "about:blank":
        page.goto(site.url + "/" + path)
    page.wait_for_selector(".panel", timeout=15000)
    page.wait_for_function("getComputedStyle(document.getElementById('loading')).display==='none'", timeout=15000)
    return h


def draft(page):
    return page.evaluate("JSON.parse(localStorage.getItem('pitlanelab_admin_draft_v1')||'null')")


def open_panel(page, pid):
    if not page.evaluate(f"document.getElementById('pn_{pid}').classList.contains('open')"):
        page.click(f"#pn_{pid} .ph")
    page.wait_for_function(f"document.getElementById('pb_{pid}').children.length>0")


def open_item(page, lp):
    sel = f'.item[data-lp="{lp}"]'
    if page.get_attribute(f"{sel} .tg", "aria-expanded") != "true":
        page.click(f"{sel} .tg")
    page.wait_for_selector(f"{sel} .ibody", state="visible")


def set_field(page, selector, value):
    """Écrit dans un champ et valide, comme le ferait un utilisateur."""
    page.fill(selector, value)
    page.dispatch_event(selector, "change")


def confirm_dialog(page, yes=True):
    page.wait_for_selector("#dlgConfirm[open]", state="attached")
    page.click("#cYes" if yes else "#cNo")
    page.wait_for_function("!document.getElementById('dlgConfirm').open")


def download_pack(page, tmp_path=None, *, confirm=True):
    """Clique « Télécharger le pack », valide la fenêtre des modifications, renvoie le ZipFile."""
    with page.expect_download(timeout=20000) as dl:
        page.click("#zipBtn")
        page.wait_for_selector("#dlgDiff[open]", state="attached", timeout=15000)
        page.click("#dfOk")
    path = dl.value.path()
    return zipfile.ZipFile(io.BytesIO(open(path, "rb").read()))


def read_zip_json(z, name="content.json"):
    return json.loads(z.read(name).decode("utf-8"))


def import_files(page, files, *, wait_idle=True):
    """Importe des fichiers dans la photothèque (ouvre la fenêtre si besoin)."""
    if not page.evaluate("document.getElementById('dlgMedia').open"):
        page.click("#mediaBtn")
    page.set_input_files("#mdFile", [str(f) for f in files])
    if wait_idle:
        page.wait_for_function("document.getElementById('mdProg').hidden===true", timeout=120000)
        page.wait_for_timeout(150)


def close_media(page):
    if page.evaluate("document.getElementById('dlgMedia').open"):
        page.click("#mdFoot [data-f='cancel']")
        page.wait_for_function("!document.getElementById('dlgMedia').open")


def library_paths(page):
    return page.evaluate("[...document.querySelectorAll('#mdGrid .md-card')].map(c=>c.dataset.path)")


def pixel_info(page, src, points):
    """Lit des pixels (x, y en fraction 0..1) d'une image locale ou blob:."""
    return page.evaluate("""async ([src, pts])=>{const b=await createImageBitmap(await (await fetch(src)).blob());
        const c=document.createElement('canvas'); c.width=b.width; c.height=b.height; const g=c.getContext('2d'); g.drawImage(b,0,0);
        return {w:b.width,h:b.height,px:pts.map(([x,y])=>Array.from(g.getImageData(Math.min(b.width-1,Math.floor(x*b.width)),Math.min(b.height-1,Math.floor(y*b.height)),1,1).data))}}""", [src, points])


def expect_visible(locator, timeout=5000):
    expect(locator).to_be_visible(timeout=timeout)
