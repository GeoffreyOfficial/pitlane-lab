"""Configuration commune de la suite de tests Pitlane Lab.

- un petit serveur HTTP local (jamais de dépendance au réseau) ;
- un navigateur Chromium partagé, un contexte neuf par test (aucune fuite d'état) ;
- Google Maps est simulé ; toute autre requête externe est bloquée et enregistrée ;
- les erreurs JavaScript et les réponses HTTP en échec sont collectées pour chaque page ;
- en cas d'échec, une capture d'écran et le journal sont déposés dans tests/artifacts/.
"""
import functools
import http.server
import json
import pathlib
import re
import shutil
import socketserver
import threading
from dataclasses import dataclass, field

import pytest
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
ARTIFACTS = ROOT / "tests" / "artifacts"
COPY_IGNORE = shutil.ignore_patterns("tests", ".git", ".github", "node_modules", "__pycache__", "*.pyc", "*.bak")

MAP_STUB = ("<html><head><meta charset='utf-8'></head><body style='margin:0;background:#e5e3df'>"
            "<div style='position:absolute;left:46%;top:44%;width:22px;height:22px;background:#ea4335;"
            "border-radius:50% 50% 50% 0;transform:rotate(-45deg)'></div><p style='margin:12px'>Carte simulée</p></body></html>")

# (largeur, hauteur, tactile)
VIEWPORTS_FULL = [(320, 568, True), (360, 640, True), (390, 844, True), (430, 932, True), (667, 375, True), (844, 390, True),
                  (768, 1024, True), (820, 1180, True), (1024, 768, False), (1180, 820, False), (1280, 720, False),
                  (1366, 650, False), (1440, 900, False), (1536, 730, False), (1920, 1080, False), (2560, 1440, False), (3440, 1440, False)]
VIEWPORTS_QUICK = [(320, 568, True), (390, 844, True), (844, 390, True), (768, 1024, True), (1366, 650, False), (1920, 1080, False), (2560, 1440, False)]


def pytest_addoption(parser):
    parser.addoption("--headed", action="store_true", help="affiche le navigateur")
    parser.addoption("--slowmo", type=int, default=0, help="ralentit chaque action (ms)")
    parser.addoption("--full", action="store_true", help="teste les 17 tailles d'écran (sinon 7 représentatives)")
    parser.addoption("--launch", action="store_true", help="active aussi les contrôles d'avant mise en ligne (marqueur « launch »)")


def pytest_configure(config):
    for m in ("site: tests du site public", "admin: tests de la page d'administration", "static: contrôles sans navigateur",
              "slow: tests longs", "launch: contrôles d'avant mise en ligne (avec --launch)"):
        config.addinivalue_line("markers", m)


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--launch"):
        skip = pytest.mark.skip(reason="contrôle d'avant mise en ligne : ajoute --launch")
        for it in items:
            if "launch" in it.keywords:
                it.add_marker(skip)


def pytest_generate_tests(metafunc):
    if "viewport" in metafunc.fixturenames:
        vps = VIEWPORTS_FULL if metafunc.config.getoption("--full") else VIEWPORTS_QUICK
        metafunc.parametrize("viewport", vps, ids=[f"{w}x{h}" for w, h, _ in vps])


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


# --------------------------------------------------------------------------- serveur
class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json",
                      ".woff2": "font/woff2", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml",
                      ".avif": "image/avif", ".heic": "image/heic"}

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


@dataclass
class Site:
    url: str
    dir: pathlib.Path
    _srv: object = None

    def content(self) -> dict:
        return json.loads((self.dir / "content.json").read_text(encoding="utf-8"))

    def write_content(self, data: dict):
        (self.dir / "content.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _serve(directory) -> Site:
    srv = _Server(("127.0.0.1", 0), functools.partial(_Handler, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return Site(url=f"http://127.0.0.1:{srv.server_address[1]}", dir=pathlib.Path(directory), _srv=srv)


@pytest.fixture(scope="session")
def site():
    """Le site tel qu'il est dans le dépôt (lecture seule : ne rien modifier)."""
    s = _serve(ROOT)
    yield s
    s._srv.shutdown()


@pytest.fixture()
def site_copy(tmp_path):
    """Une copie jetable du site, que le test peut modifier (simule une mise en ligne)."""
    dst = tmp_path / "site"
    shutil.copytree(ROOT, dst, ignore=COPY_IGNORE)
    s = _serve(dst)
    yield s
    s._srv.shutdown()


# --------------------------------------------------------------------------- navigateur
@pytest.fixture(scope="session")
def browser(pytestconfig):
    with sync_playwright() as p:
        b = p.chromium.launch(headless=not pytestconfig.getoption("--headed"), slow_mo=pytestconfig.getoption("--slowmo"))
        yield b
        b.close()


@dataclass
class Handle:
    page: object
    context: object
    errors: list = field(default_factory=list)          # exceptions JavaScript et console.error
    bad_responses: list = field(default_factory=list)   # (statut, url) sur le serveur local
    external: list = field(default_factory=list)        # requêtes externes bloquées
    held: list = field(default_factory=list)            # requêtes Google retenues (mode « hold »)
    map_requests: list = field(default_factory=list)

    def release_maps(self):
        while self.held:
            self.held.pop().fulfill(body=MAP_STUB, content_type="text/html; charset=utf-8")


@pytest.fixture()
def make_page(browser, request):
    """Fabrique de pages : make_page(site, 'index.html', w=1280, h=800, mobile=False, content=..., maps='fast')."""
    handles = []

    def make(site, path="index.html", *, w=1280, h=800, mobile=False, reduced_motion=False, content=None, content_fn=None,
             maps="fast", sw="block", goto=True, locale="fr-FR", dpr=None, intro=False, init_scripts=(), instant_scroll=True, extra_routes=()):
        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile,
                                  device_scale_factor=dpr or (2 if mobile else 1), accept_downloads=True, locale=locale,
                                  reduced_motion="reduce" if reduced_motion else "no-preference", service_workers=sw)
        if not intro:
            ctx.add_init_script("try{sessionStorage.setItem('pl_intro','1')}catch(e){}")   # pas d'écran d'intro (sauf tests dédiés)
        if instant_scroll:   # le défilement fluide rend les mesures instables : on le coupe en test
            ctx.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='html{scroll-behavior:auto!important}';document.head.appendChild(s)})")
        for sc in init_scripts:
            ctx.add_init_script(sc)
        page = ctx.new_page()
        hd = Handle(page=page, context=ctx)
        base = site.url

        def on_console(m):
            if m.type == "error" and "Failed to load resource" not in m.text:
                hd.errors.append("console.error: " + m.text)

        page.on("pageerror", lambda e: hd.errors.append(f"pageerror: {e}"))
        page.on("console", on_console)
        page.on("response", lambda r: hd.bad_responses.append((r.status, r.url)) if r.status >= 400 and r.url.startswith(base) else None)

        def router(route):
            url = route.request.url
            if url.startswith(base):
                if content is not None or content_fn is not None:
                    if re.search(r"/content\.json(\?|$)", url):
                        data = content if content is not None else content_fn(site.content())
                        return route.fulfill(body=json.dumps(data, ensure_ascii=False), content_type="application/json")
                return route.continue_()
            if url.startswith(("data:", "blob:", "about:")):
                return route.continue_()
            for needle, fn in extra_routes:      # points d'accès simulés propres à un test (ex. envoi de formulaire)
                if needle in url:
                    return fn(route)
            if "google.com/maps" in url and "output=embed" in url:
                hd.map_requests.append(url)
                if maps == "fast":
                    return route.fulfill(body=MAP_STUB, content_type="text/html; charset=utf-8")
                if maps == "hold_all" or (maps == "hold" and len(hd.map_requests) == 1):   # « hold » : seule la 1re requête est retenue
                    hd.held.append(route)
                    return
                if maps == "hold":
                    return route.fulfill(body=MAP_STUB, content_type="text/html; charset=utf-8")
            hd.external.append(url)
            return route.abort()

        ctx.route("**/*", router)
        handles.append(hd)
        import helpers
        helpers.ACTIVE["page"] = page
        if goto:
            page.goto(base + "/" + path)
        return hd

    yield make

    failed = getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed
    for i, hd in enumerate(handles):
        if failed:
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", request.node.nodeid)[-120:]
            try:
                hd.page.screenshot(path=str(ARTIFACTS / f"{safe}-{i}.png"), full_page=False)
            except Exception:
                pass
            (ARTIFACTS / f"{safe}-{i}.txt").write_text("\n".join(hd.errors + [f"HTTP {s} {u}" for s, u in hd.bad_responses] + hd.external), encoding="utf-8")
        try:
            hd.context.close()
        except Exception:
            pass
