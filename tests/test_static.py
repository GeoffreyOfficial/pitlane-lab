"""Contrôles statiques : fichiers, JSON, cohérence des références, syntaxe, poids. Aucun navigateur."""
import json
import re
import shutil
import subprocess
import urllib.parse

import pytest

from conftest import ROOT

pytestmark = pytest.mark.static
IMG_RE = re.compile(r"\.(jpe?g|png|webp|gif|svg|avif|ico)$", re.I)


@pytest.fixture(scope="module")
def content():
    return json.loads((ROOT / "content.json").read_text(encoding="utf-8"))


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}.{i}")
    else:
        yield path, o


def test_required_files_exist():
    for f in ["index.html", "admin.html", "content.json", "sw.js", "manifest.webmanifest", "robots.txt", "sitemap.xml", "LISEZ-MOI.md",
              "vendor/heic2any.min.js", "vendor/UTIF.js", "vendor/pako_inflate.min.js", "vendor/LICENCES.txt",
              "fonts/saira-italic.woff2", "fonts/barlow-400.woff2", "images/logo-full.png", "images/car-lines.png",
              "images/og-image.jpg", "images/favicon.ico", "images/apple-touch-icon.png", "images/icon-192.png", "images/icon-512.png"]:
        assert (ROOT / f).is_file(), f"fichier manquant : {f}"


def test_content_json_is_valid_and_complete(content):
    for k in ["hero", "services", "faq", "contact", "zone", "theme", "seo", "legal", "footer", "visibility", "branding", "estimateur", "nav", "etapes"]:
        assert k in content, f"clé absente de content.json : {k}"
    assert isinstance(content["services"], list) and content["services"], "au moins une prestation attendue"
    for i, s in enumerate(content["services"]):
        assert str(s.get("titre", "")).strip(), f"prestation {i} sans titre"
        assert str(s.get("prix", "")).strip(), f"prestation {i} sans prix"


def test_content_ids_are_unique(content):
    for lp in ["services", "avantApres", "etapes", "faq", "avis", "galerie", "zones"]:
        ids = [x.get("_id") for x in content.get(lp, []) if isinstance(x, dict) and x.get("_id")]
        assert len(ids) == len(set(ids)), f"identifiants _id en double dans {lp}"


def test_theme_colors_are_valid_hex(content):
    for k, v in content["theme"].items():
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", v), f"couleur invalide theme.{k} = {v}"


def test_every_referenced_image_exists(content):
    missing = []
    for path, v in walk(content):
        if isinstance(v, str) and v.startswith("images/") and IMG_RE.search(v) and not path.startswith("medias"):
            if not (ROOT / v).is_file():
                missing.append(f"{path} → {v}")
    assert not missing, "images référencées mais absentes :\n - " + "\n - ".join(missing)


def test_contact_formats(content):
    ct = content["contact"]
    if ct.get("email"):
        assert re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", ct["email"]), "e-mail invalide"
    if ct.get("telephone"):
        assert len(re.sub(r"\D", "", ct["telephone"])) >= 9, "téléphone trop court"
    for k in ("instagram", "facebook", "tiktok", "formEndpoint"):
        if ct.get(k):
            assert re.match(r"https?://\S+\.\S+", ct[k]), f"lien invalide : contact.{k}"


def test_design_and_modules_defaults(content):
    d = content["design"]
    assert d["police"] in ("sport", "moderne", "elegant", "technique", "systeme") and d["boutons"] in ("parallelogramme", "carre", "arrondi", "pilule")
    assert d["mouvement"] in ("riche", "calme", "aucun") and isinstance(d["ordre"], list)
    for k in ("annonce", "atouts", "chiffres", "cta"):
        assert k in content["modules"] and "actif" in content["modules"][k]
    assert isinstance(content["blocs"], list)


def test_branding_defaults_are_sane(content):
    b = content["branding"]
    assert 1.4 <= float(b["logoHauteur"]) <= 4.2
    for k in ("logo", "silhouette"):
        if b.get(k):
            assert (ROOT / b[k]).is_file(), f"branding.{k} introuvable"


def test_manifest_is_valid():
    m = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    for k in ("name", "short_name", "start_url", "display", "icons"):
        assert k in m, f"manifeste : {k} manquant"
    assert m["display"] in ("standalone", "minimal-ui", "fullscreen")
    for ic in m["icons"]:
        assert (ROOT / ic["src"]).is_file(), f"icône du manifeste absente : {ic['src']}"


def test_service_worker_precaches_existing_files():
    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    m = re.search(r"CORE\s*=\s*\[(.*?)\]", sw, re.S)
    assert m, "liste CORE introuvable dans sw.js"
    for f in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
        if f in ("./", "/"):
            continue
        assert (ROOT / f.lstrip("./")).is_file(), f"sw.js met en cache un fichier absent : {f}"


def test_sitemap_and_robots():
    assert "<urlset" in (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /admin.html" in robots, "l'admin doit être exclu de l'indexation"


@pytest.mark.parametrize("name", ["index.html", "admin.html"])
def test_html_basics(name):
    s = (ROOT / name).read_text(encoding="utf-8")
    assert s.lstrip().lower().startswith("<!doctype html>")
    assert s.count("<html") == 1 and s.count("</html>") == 1
    assert 'lang="fr"' in s[:200]
    assert '<meta name="viewport"' in s
    assert "<title>" in s
    # un seul bloc <script> inline fermé correctement (hors chaînes JS)
    assert s.rstrip().endswith("</html>")


def _inline_js(html):
    """Le script principal : balise <script> seule sur sa ligne (les <script> dans des chaînes JS sont ignorés)."""
    a = list(re.finditer(r"(?m)^<script>\s*$", html))
    b = list(re.finditer(r"(?m)^</script>\s*$", html))
    assert a and b, "script principal introuvable"
    return html[a[-1].end():b[-1].start()]


@pytest.mark.parametrize("name", ["index.html", "admin.html", "sw.js"])
def test_javascript_syntax(name, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js absent : contrôle de syntaxe ignoré")
    s = (ROOT / name).read_text(encoding="utf-8")
    js = _inline_js(s) if name.endswith(".html") else s
    f = tmp_path / "check.js"
    f.write_text(js, encoding="utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:800]


def test_no_external_resources_in_site():
    """Le site doit rester autonome : aucune ressource tierce chargée au démarrage (hors carte Google, à la demande)."""
    s = (ROOT / "index.html").read_text(encoding="utf-8")
    hosts = set(re.findall(r"""(?:src|href)=["']https?://([^/"']+)""", s))
    allowed = {"www.google.com", "maps.google.com", "wa.me", "schema.org"}
    assert not (hosts - allowed), f"ressources externes inattendues : {hosts - allowed}"


def test_size_budgets():
    kb = lambda p: (ROOT / p).stat().st_size / 1024
    assert kb("index.html") < 400, f"index.html trop lourd ({kb('index.html'):.0f} Ko)"
    assert kb("admin.html") < 450, f"admin.html trop lourd ({kb('admin.html'):.0f} Ko)"
    fonts = sum(f.stat().st_size for f in (ROOT / "fonts").glob("*")) / 1024
    assert fonts < 400, f"polices trop lourdes ({fonts:.0f} Ko)"
    imgs = sum(f.stat().st_size for f in (ROOT / "images").rglob("*") if f.is_file()) / 1024
    assert imgs < 3000, f"images du dépôt trop lourdes ({imgs:.0f} Ko)"


def test_guide_sections_present():
    s = (ROOT / "admin.html").read_text(encoding="utf-8")
    for a in "ABCDEFGHIJK":
        assert f'id="g{a}"' in s, f"section g{a} absente du guide"


def test_index_and_admin_share_branding_defaults():
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    adm = (ROOT / "admin.html").read_text(encoding="utf-8")
    for needle in ("images/logo-full.png", "images/car-lines.png"):
        assert needle in idx and needle in adm


@pytest.mark.launch
def test_launch_no_placeholder_contact(content):
    assert re.sub(r"\D", "", content["contact"]["telephone"]) != "0600000000", "numéro d'exemple encore en place"
    assert content["contact"]["email"] != "contact@pitlanelab.fr", "e-mail d'exemple encore en place"


@pytest.mark.launch
def test_launch_legal_complete(content):
    assert "[" not in content["legal"]["texte"], "mentions légales : il reste des crochets à compléter"


@pytest.mark.launch
def test_launch_domain_consistency(content):
    base = content["seo"]["siteUrl"].rstrip("/")
    host = urllib.parse.urlparse(base).netloc
    assert host in (ROOT / "sitemap.xml").read_text(encoding="utf-8"), "sitemap.xml ne correspond pas à seo.siteUrl"
    assert host in (ROOT / "robots.txt").read_text(encoding="utf-8"), "robots.txt ne correspond pas à seo.siteUrl"
