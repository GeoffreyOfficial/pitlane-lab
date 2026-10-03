"""Socle de l'administration : démarrage, panneaux, champs, validation, historique, brouillon, aperçu, guide, responsive."""
import json

import pytest

from helpers import Problems, confirm_dialog, download_pack, draft, open_admin, open_panel, set_field, wait_for

pytestmark = pytest.mark.admin
PANELS = ["design", "modules", "photos", "identite", "prestations", "estimateur", "details", "accueil", "resultats", "galerie", "apropos", "zone",
          "contact", "methode", "faq", "avis", "menu", "couleurs", "effets", "visibilite", "pied", "seo"]


@pytest.fixture()
def adm(make_page, site):
    hd = make_page(site, "admin.html", w=1280, h=900)
    open_admin(hd, site)
    return hd


def get_path(obj, path):
    for k in path.split("."):
        obj = obj[int(k)] if isinstance(obj, list) else obj[k]
    return obj


# ------------------------------------------------------------------ démarrage
def test_loads_cleanly(adm):
    p = adm.page
    assert not adm.errors, adm.errors
    ids = p.evaluate("[...document.querySelectorAll('.panel[data-id]')].map(e=>e.dataset.id)")
    assert sorted(ids) == sorted(PANELS), f"panneaux attendus {sorted(PANELS)}, obtenus {sorted(ids)}"
    assert "Identique" in p.inner_text("#saveState")
    assert p.is_disabled("#diffBtn") and p.is_disabled("#undoBtn") and p.is_disabled("#redoBtn")
    assert p.locator("#ck button").count() >= 1, "la liste « Avant de publier » est vide"
    assert not [b for b in adm.bad_responses if b[0] != 404]


def test_admin_is_not_indexable_and_has_no_external_requests(adm):
    assert "noindex" in adm.page.get_attribute('meta[name="robots"]', "content")
    assert adm.external == []


@pytest.mark.parametrize("pid", PANELS)
def test_every_panel_opens_renders_and_closes(adm, pid):
    p = adm.page
    open_panel(p, pid)
    assert p.get_attribute(f"#pn_{pid} .ph", "aria-expanded") == "true"
    assert p.evaluate(f"document.getElementById('pb_{pid}').innerText.trim().length") > 20, "panneau vide"
    p.click(f"#pn_{pid} .ph")
    assert p.get_attribute(f"#pn_{pid} .ph", "aria-expanded") == "false"
    assert not adm.errors, adm.errors


# ------------------------------------------------------------------ balayage de tous les champs
def test_every_text_field_writes_to_the_content(adm):
    """Pour chaque champ de chaque panneau : on écrit, on vérifie que le brouillon reçoit la valeur exacte."""
    p, bad, n = adm.page, Problems(), 0
    for pid in PANELS:
        if pid in ("photos",):
            continue
        open_panel(p, pid)
        # ouvre tous les éléments de liste pour atteindre leurs champs
        p.evaluate(f"document.querySelectorAll('#pb_{pid} .item:not(.open) .tg').forEach(b=>b.click())")
        fields = p.evaluate(f"""[...document.querySelectorAll('#pb_{pid} [data-path]')].filter(e=>e.offsetParent!==null&&!e.closest('details')&&((e.tagName==='TEXTAREA')||(e.tagName==='INPUT'&&['text','url','email','tel',''].includes(e.type)))).map(e=>[e.dataset.path,e.tagName,e.id,!!e.dataset.num])""")
        for path, tag, fid, num in fields[:40]:
            if num or path.startswith("theme."):   # nombres et couleurs (7 caractères max) : testés à part
                continue
            val = f"Essai {pid} ✓ é<b>&\"'"
            sel = f'#pb_{pid} [data-path="{path}"]'
            p.fill(sel, val)
            p.dispatch_event(sel, "change")
            stored = draft(p)
            try:
                got = get_path(stored, path)
            except Exception:
                got = None
            bad.check(got == val, f"{path} : « {got} » au lieu de la valeur saisie")
            n += 1
    assert n >= 100, f"balayage trop court ({n} champs)"
    bad.assert_none()
    assert not adm.errors, adm.errors


def test_switches_and_sliders_write_to_the_content(adm):
    p, bad = adm.page, Problems()
    open_panel(p, "visibilite")
    for k in ["resultats", "methode", "apropos", "galerie", "zone", "faq", "avis", "barreMobile"]:
        sel = f'[data-path="visibility.{k}"]'
        before = p.is_checked(sel)
        p.evaluate(f"document.querySelector('{sel}').click()")
        bad.check(draft(p)["visibility"][k] == (not before), f"interrupteur {k} sans effet")
    open_panel(p, "effets")
    for k in ["intro", "essuyage", "details", "marquee", "rail", "curseur"]:
        sel = f'[data-path="effets.{k}"]'
        before = p.is_checked(sel)
        p.evaluate(f"document.querySelector('{sel}').click()")
        bad.check(draft(p)["effets"][k] == (not before), f"effet {k} sans effet")
    open_panel(p, "identite")
    p.evaluate("(()=>{const r=document.getElementById('f_branding_logoHauteur'); r.value=3.4; r.dispatchEvent(new Event('input',{bubbles:true})); r.dispatchEvent(new Event('change',{bubbles:true}))})()")
    bad.check(abs(float(draft(p)["branding"]["logoHauteur"]) - 3.4) < .01, "curseur de taille du logo sans effet")
    bad.assert_none()


def test_string_lists_add_move_delete(adm):
    p = adm.page
    open_panel(p, "accueil")
    before = draft(p) or {}
    base = len(adm.page.evaluate("JSON.parse(JSON.stringify(window.__none||[]))")) if False else None
    n0 = p.locator('#pb_accueil input[data-path^="hero.points."]').count()
    p.click('#pb_accueil [data-act="add-s"][data-p="hero.points"]')
    assert p.locator('#pb_accueil input[data-path^="hero.points."]').count() == n0 + 1
    set_field(p, f'#pb_accueil input[data-path="hero.points.{n0}"]', "Nouveau point")
    assert draft(p)["hero"]["points"][-1] == "Nouveau point"
    p.click(f'#pb_accueil [data-act="mv"][data-p="hero.points"][data-i="{n0}"][data-d="-1"]')
    assert draft(p)["hero"]["points"][n0 - 1] == "Nouveau point"
    p.click(f'#pb_accueil [data-act="del-s"][data-p="hero.points"][data-i="{n0 - 1}"]')
    assert "Nouveau point" not in draft(p)["hero"]["points"]


# ------------------------------------------------------------------ validation
def test_invalid_content_blocks_download_and_points_to_the_field(adm):
    p = adm.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "")
    p.click("#zipBtn")
    wait_for(lambda: "titre" in p.inner_text("#toast").lower() or "corriger" in p.inner_text("#toast").lower(), msg="aucun message de validation")
    assert not p.evaluate("document.getElementById('dlgDiff').open"), "la fenêtre de téléchargement ne doit pas s'ouvrir"
    assert p.is_visible('[data-fp="hero.titre"].bad .err') or p.evaluate("document.querySelector('[data-fp=\"hero.titre\"]').classList.contains('bad')")
    set_field(p, "#f_hero_titre", "Un titre valide")
    z = download_pack(p)
    assert json.loads(z.read("content.json"))["hero"]["titre"] == "Un titre valide"


@pytest.mark.parametrize("panel,fid,value,fragment", [
    ("contact", "#f_contact_email", "pas-un-mail", "e-mail"),
    ("contact", "#f_contact_telephone", "12", "incomplet"),
    ("contact", "#f_contact_instagram", "instagram.com/x", "https"),
    ("contact", "#f_contact_formEndpoint", "ftp://x", "https"),
    ("seo", "#f_seo_siteUrl", "pitlanelab.fr", "https"),
    ("zone", "#f_zone_rayonKm", "-4", "rayon"),
    ("identite", "#f_branding_nom", "", "nom"),
])
def test_field_validation_messages(adm, panel, fid, value, fragment):
    p = adm.page
    open_panel(p, panel)
    set_field(p, fid, value)
    fp = p.evaluate(f"document.querySelector('{fid}').closest('.fld').dataset.fp")
    wait_for(lambda: p.evaluate(f"document.querySelector('[data-fp=\"{fp}\"]').classList.contains('bad')"), msg="champ non signalé")
    assert fragment in p.inner_text(f'[data-fp="{fp}"] .err').lower()


def test_service_requires_title_and_price(adm):
    p = adm.page
    open_panel(p, "prestations")
    p.click('#pb_prestations [data-act="add"][data-p="services"]')
    p.wait_for_selector('.item[data-lp="services.6"]')
    set_field(p, "#f_services_6_titre", "")
    p.click("#zipBtn")
    wait_for(lambda: "corriger" in p.inner_text("#toast").lower() or "titre" in p.inner_text("#toast").lower() or "prix" in p.inner_text("#toast").lower())


# ------------------------------------------------------------------ historique, brouillon, restauration
def test_undo_redo_with_labels_and_keyboard(adm):
    p = adm.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Titre A")
    p.wait_for_timeout(900)   # au-delà du regroupement de la saisie : deux étapes d'historique distinctes
    set_field(p, "#f_hero_cta1", "Bouton B")
    p.wait_for_timeout(900)
    wait_for(lambda: not p.is_disabled("#undoBtn"))
    assert "Annuler" in p.get_attribute("#undoBtn", "title")
    p.click("#undoBtn")
    wait_for(lambda: draft(p)["hero"]["cta1"] != "Bouton B")
    assert draft(p)["hero"]["titre"] == "Titre A"
    assert "Rétablir" in p.get_attribute("#redoBtn", "title")
    p.click("#redoBtn")
    wait_for(lambda: draft(p)["hero"]["cta1"] == "Bouton B")
    p.click("body", position={"x": 5, "y": 300})
    p.keyboard.press("Control+z")
    wait_for(lambda: draft(p)["hero"]["cta1"] != "Bouton B", msg="Ctrl+Z ne fonctionne pas")
    p.keyboard.press("Control+y")
    wait_for(lambda: draft(p)["hero"]["cta1"] == "Bouton B", msg="Ctrl+Y ne fonctionne pas")


def test_ctrl_z_inside_a_text_field_does_not_trigger_the_admin_history(adm):
    p = adm.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Étape 1")
    p.wait_for_timeout(900)
    p.click("#f_hero_cta2")
    p.evaluate("document.getElementById('toast').textContent=''")
    p.keyboard.press("Control+z")
    p.wait_for_timeout(300)
    assert "Annulé" not in p.inner_text("#toast"), "Ctrl+Z dans un champ ne doit pas déclencher l'historique de l'admin (le navigateur gère sa propre saisie)"


def test_draft_is_offered_after_reload_and_can_be_kept(adm):
    p = adm.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Brouillon conservé")
    p.reload()
    p.wait_for_selector("#dlgConfirm[open]", state="attached")
    assert "brouillon" in p.inner_text("#cTitle").lower()
    p.click("#cYes")
    p.wait_for_selector(".panel")
    open_panel(p, "accueil")
    assert p.input_value("#f_hero_titre") == "Brouillon conservé"
    assert "non téléchargée" in p.inner_text("#saveState")


def test_draft_can_be_discarded_at_startup(adm):
    p = adm.page
    open_panel(p, "accueil")
    original = p.input_value("#f_hero_titre")
    set_field(p, "#f_hero_titre", "À jeter")
    p.reload()
    p.wait_for_selector("#dlgConfirm[open]", state="attached")
    p.click("#cNo")
    p.wait_for_selector(".panel")
    open_panel(p, "accueil")
    assert p.input_value("#f_hero_titre") == original


def test_restore_everything_button(adm):
    p = adm.page
    open_panel(p, "accueil")
    original = p.input_value("#f_hero_titre")
    set_field(p, "#f_hero_titre", "Modifié")
    wait_for(lambda: not p.is_hidden("#discardBtn"))
    p.click("#discardBtn")
    confirm_dialog(p)
    wait_for(lambda: p.input_value("#f_hero_titre") == original)
    assert "Identique" in p.inner_text("#saveState")


def test_leaving_with_unsaved_changes_is_guarded(adm):
    p = adm.page
    open_panel(p, "accueil")
    assert p.evaluate("(()=>{const e=new Event('beforeunload',{cancelable:true}); window.dispatchEvent(e); return e.defaultPrevented})()") is False
    set_field(p, "#f_hero_titre", "Non téléchargé")
    wait_for(lambda: p.evaluate("(()=>{const e=new Event('beforeunload',{cancelable:true}); window.dispatchEvent(e); return e.defaultPrevented})()"), msg="aucun avertissement avant de quitter")


def test_copy_json_to_clipboard(adm):
    adm.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=adm.page.url.split("/admin")[0])
    p = adm.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Copié")
    p.click("#copyBtn")
    wait_for(lambda: "copi" in p.inner_text("#toast").lower())
    data = json.loads(p.evaluate("navigator.clipboard.readText()"))
    assert data["hero"]["titre"] == "Copié"


# ------------------------------------------------------------------ aperçu et guide
def test_preview_shows_unpublished_changes_on_desktop_and_phone(adm):
    p = adm.page
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Titre visible dans l'aperçu")
    p.click("#previewBtn")
    p.wait_for_selector("#dlgPreview[open]", state="attached")
    fr = p.frame_locator("#pvFrame")
    fr.locator(".hero h1").wait_for(timeout=10000)
    assert "titre visible dans l'aperçu" in fr.locator(".hero h1").inner_text().lower()
    w_desktop = p.evaluate("document.getElementById('pvFrame').getBoundingClientRect().width")
    p.click("#pvMob")
    wait_for(lambda: p.evaluate("document.getElementById('pvFrame').getBoundingClientRect().width") <= 392, msg="le mode téléphone ne rétrécit pas l'aperçu")
    assert w_desktop > 800
    set_field_after = None
    p.click("#pvClose")
    p.wait_for_function("!document.getElementById('dlgPreview').open")
    assert "Titre visible" not in (p.evaluate("localStorage.getItem('pitlanelab_content_cache_v1')") or ""), "l'aperçu ne doit pas polluer le cache du vrai site"


def test_guide_dialog_search_and_navigation(adm):
    p = adm.page
    p.click("#guideBtn")
    p.wait_for_selector("#dlgGuide[open]", state="attached")
    assert p.locator("#dlgGuide .gsec").count() == 11
    p.click('#guideToc a[href="#gG"]')
    wait_for(lambda: p.evaluate("(()=>{const r=document.getElementById('gG').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0})()"))
    p.fill("#guideSearch", "détourer")
    wait_for(lambda: 0 < p.locator("#dlgGuide .gsec:visible").count() < 11)
    p.fill("#guideSearch", "zzzzqq")
    wait_for(lambda: "Aucun résultat" in p.inner_text("#guideNone"))
    p.fill("#guideSearch", "")
    wait_for(lambda: p.locator("#dlgGuide .gsec:visible").count() == 11)
    p.click("#gClose")
    p.wait_for_function("!document.getElementById('dlgGuide').open")


def test_checklist_items_open_the_right_panel(adm):
    p = adm.page
    n = p.locator("#ck button").count()
    opened = 0
    for i in range(n):
        p.locator("#ck button").nth(i).click()
        p.wait_for_timeout(120)
        opened += p.evaluate("document.querySelectorAll('.panel.open[data-id]').length") > 0
    assert opened >= 1, "la liste de contrôle n'ouvre aucun panneau"


# ------------------------------------------------------------------ robustesse
def test_admin_without_content_json_still_usable(make_page, site):
    hd = make_page(site, "admin.html", content_fn=None, goto=False)
    hd.context.route("**/content.json", lambda r: r.fulfill(status=404, body="absent"))
    hd.page.goto(site.url + "/admin.html")
    hd.page.wait_for_selector(".panel", timeout=15000)
    assert "n'a pas pu être chargé" in hd.page.inner_text("#errBanner")
    open_panel(hd.page, "accueil")
    set_field(hd.page, "#f_hero_titre", "Sans fichier")
    assert draft(hd.page)["hero"]["titre"] == "Sans fichier"
    assert not [e for e in hd.errors if "pageerror" in e]


def test_admin_survives_degraded_content_json(make_page, site):
    hd = make_page(site, "admin.html", content={"hero": {"titre": "Seul"}, "services": [{}, {"titre": "A"}], "faq": "oups"})
    open_admin(hd, site)
    for pid in PANELS:
        open_panel(hd.page, pid)
    assert not [e for e in hd.errors if "pageerror" in e], hd.errors


# ------------------------------------------------------------------ responsive
@pytest.mark.parametrize("w,h,mob", [(320, 568, True), (390, 844, True), (768, 1024, True), (844, 390, True), (1366, 650, False), (2560, 1440, False)])
def test_admin_has_no_horizontal_overflow_and_reachable_actions(make_page, site, w, h, mob):
    hd = make_page(site, "admin.html", w=w, h=h, mobile=mob)
    open_admin(hd, site)
    p, bad = hd.page, Problems()
    for pid in ["prestations", "estimateur", "zone", "couleurs", "identite", "photos"]:
        open_panel(p, pid)
    p.evaluate("document.querySelectorAll('.item .tg').forEach(b=>b.click())")
    bad.check(p.evaluate("document.documentElement.scrollWidth") <= w, f"débordement horizontal : {p.evaluate('document.documentElement.scrollWidth')}px")
    for sel in ["#zipBtn", "#undoBtn", "#previewBtn", "#mediaBtn", "#guideBtn"]:
        box = p.evaluate(f"(()=>{{const r=document.querySelector('{sel}').getBoundingClientRect();return [r.left,r.right,r.top,r.bottom]}})()")
        bad.check(box[0] >= -1 and box[1] <= w + 1 and box[3] <= h + 1, f"{sel} hors de l'écran : {box}")
    bad.assert_none()


@pytest.mark.parametrize("w,h,mob", [(320, 568, True), (390, 844, True), (1280, 800, False)])
def test_admin_dialogs_fit_the_screen(make_page, site, w, h, mob):
    hd = make_page(site, "admin.html", w=w, h=h, mobile=mob)
    open_admin(hd, site)
    p, bad = hd.page, Problems()
    open_panel(p, "accueil")
    set_field(p, "#f_hero_titre", "Modifié pour ouvrir la fenêtre")
    wait_for(lambda: not p.is_disabled("#diffBtn"))
    for name, opener, dlg, closer in [("modifications", "#diffBtn", "dlgDiff", "#dfClose"), ("guide", "#guideBtn", "dlgGuide", "#gClose"), ("photothèque", "#mediaBtn", "dlgMedia", "#mdClose")]:
        p.click(opener)
        p.wait_for_selector(f"#{dlg}[open]", state="attached")
        p.wait_for_timeout(250)
        m = p.evaluate(f"(()=>{{const d=document.getElementById('{dlg}').firstElementChild.getBoundingClientRect();return [d.left>=-1,d.right<=innerWidth+1,d.top>=-1,d.bottom<=innerHeight+1]}})()")
        bad.check(all(m), f"fenêtre « {name} » hors de l'écran : {m}")
        p.click(closer)
        p.wait_for_function(f"!document.getElementById('{dlg}').open")
    bad.assert_none()
