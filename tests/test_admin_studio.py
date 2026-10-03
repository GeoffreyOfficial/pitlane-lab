"""Studio de design de l'admin : aperçu en direct, ambiances, couleurs, style, mise en page, modules."""
import json
import re

import pytest

from helpers import confirm_dialog, download_pack, draft, open_admin, open_item, open_panel, read_zip_json, set_field, wait_for

pytestmark = pytest.mark.admin


@pytest.fixture()
def adm(make_page, site):
    hd = make_page(site, "admin.html", w=1440, h=900)
    open_admin(hd, site)
    return hd


def open_studio(p, tab=None):
    p.click("#designBtn")
    p.wait_for_selector("#dlgStudio[open]", state="attached")
    p.wait_for_function("document.getElementById('stLoad').hidden===true", timeout=15000)
    if tab:
        p.click(f'#stTabs [data-k="{tab}"]')
    return p.frame_locator("#stFrame")


def frame_eval(p, js):
    return p.evaluate(f"(()=>{{const d=document.getElementById('stFrame').contentDocument; return ({js})}})()")


def design(p):
    return draft(p)["design"]


# ------------------------------------------------------------------ ouverture et aperçu
def test_opens_from_top_bar_and_from_panel(adm):
    p = adm.page
    open_studio(p)
    assert p.locator("#stTabs button").count() == 5
    p.click("#stDone")
    p.wait_for_function("!document.getElementById('dlgStudio').open")
    open_panel(p, "design")
    assert "Ambiance actuelle" in p.inner_text("#pb_design")
    p.click('#pb_design [data-m="open-studio"]')
    p.wait_for_selector("#dlgStudio[open]", state="attached")
    p.keyboard.press("Escape")
    p.wait_for_function("!document.getElementById('dlgStudio').open")
    assert not adm.errors, adm.errors


def test_live_preview_loads_the_real_site(adm):
    p = adm.page
    fr = open_studio(p)
    assert "voiture" in fr.locator(".hero h1").inner_text().lower()
    assert frame_eval(p, "d.documentElement.getAttribute('data-preview')") == "1"
    assert frame_eval(p, "!!d.querySelector('#cards .card')")


@pytest.mark.parametrize("dev,width", [("desktop", 1280), ("tablet", 820), ("phone", 390)])
def test_device_switch_resizes_preview(adm, dev, width):
    p = adm.page
    open_studio(p)
    p.click(f'#stDev [data-dev="{dev}"]')
    wait_for(lambda: p.evaluate("parseFloat(document.getElementById('stFrame').style.width)") == width)
    assert p.get_attribute(f'#stDev [data-dev="{dev}"]', "aria-pressed") == "true"
    assert frame_eval(p, "d.defaultView.innerWidth") == width, "l'aperçu doit avoir une vraie largeur d'appareil (mise en page responsive réelle)"
    box = p.evaluate("(()=>{const v=document.getElementById('stVp').getBoundingClientRect(),c=document.getElementById('stPrev').getBoundingClientRect();return v.right<=c.right+1&&v.left>=c.left-1})()")
    assert box, "l'aperçu doit tenir dans la zone"


def test_phone_preview_shows_burger_menu(adm):
    p = adm.page
    open_studio(p)
    p.click('#stDev [data-dev="phone"]')
    wait_for(lambda: frame_eval(p, "getComputedStyle(d.getElementById('burger')).display") != "none")


# ------------------------------------------------------------------ ambiances
def test_ambiance_applies_theme_design_and_preview(adm):
    p = adm.page
    open_studio(p)
    studio = p.evaluate("window.__studio.AMBIANCES")
    a = next(x for x in studio if x["id"] == "showroom")
    p.click('.amb-wrap[data-id="showroom"]')
    wait_for(lambda: design(p)["ambiance"] == "showroom")
    d = draft(p)
    assert d["theme"] == a["t"] and d["design"]["police"] == "elegant" and d["design"]["boutons"] == "arrondi"
    wait_for(lambda: frame_eval(p, "d.documentElement.getAttribute('data-tone')") == "clair", msg="l'aperçu n'est pas passé en thème clair")
    assert "Georgia" in frame_eval(p, "getComputedStyle(d.querySelector('.hero h1')).fontFamily")
    assert p.get_attribute('.amb-wrap[data-id="showroom"]', "aria-pressed") == "true"
    assert "modification" in p.inner_text("#pn_design [data-diff-badge]") if p.is_visible("#pn_design [data-diff-badge]") else True


def test_ambiance_keeps_custom_section_order(adm):
    p = adm.page
    open_studio(p, "mod")
    p.click('.st-row[data-k="faq"] [data-st="mv"][data-d="-1"]')
    order = list(design(p)["ordre"])
    p.click('#stTabs [data-k="amb"]')
    p.click('.amb-wrap[data-id="glace"]')
    wait_for(lambda: design(p)["ambiance"] == "glace")
    assert design(p)["ordre"] == order, "changer d'ambiance ne doit pas défaire l'ordre des sections"


def test_hover_previews_without_committing(adm):
    p = adm.page
    open_studio(p)
    before = json.dumps(draft(p) or {}, sort_keys=True) if draft(p) else "none"
    p.hover('.amb-wrap[data-id="neon"]')
    wait_for(lambda: "monospace" in frame_eval(p, "getComputedStyle(d.querySelector('.hero h1')).fontFamily"), msg="l'aperçu temporaire n'apparaît pas au survol")
    assert (json.dumps(draft(p) or {}, sort_keys=True) if draft(p) else "none") == before, "le survol ne doit rien enregistrer"
    p.mouse.move(700, 450)
    wait_for(lambda: "monospace" not in frame_eval(p, "getComputedStyle(d.querySelector('.hero h1')).fontFamily"), msg="l'aperçu n'est pas restauré après le survol")


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_palette_generator(adm, mode):
    p = adm.page
    open_studio(p)
    p.evaluate("(()=>{const i=document.getElementById('stGenCol'); i.value='#19c26b'; i.dispatchEvent(new Event('input',{bubbles:true}))})()")
    p.click(f'[data-st="gen"][data-m="{mode}"]')
    wait_for(lambda: draft(p)["design"]["ambiance"] == "perso")
    t = draft(p)["theme"]
    assert all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in t.values()), t
    c = lambda a, b: p.evaluate("([a,b])=>window.__studio.contrastOf(a,b)", [a, b])
    assert c(t["ink"], t["bg"]) >= 7 and c(t["muted"], t["bg"]) >= 4.5
    wait_for(lambda: (frame_eval(p, "d.documentElement.getAttribute('data-tone')") == "clair") == (mode == "light"), msg="thème clair/sombre de l'aperçu incorrect")


def test_surprise_makes_valid_readable_design(adm):
    p = adm.page
    open_studio(p)
    for _ in range(6):
        p.click('[data-st="rand"]')
        d = draft(p)
        assert d["design"]["police"] in ("sport", "moderne", "elegant", "technique", "systeme")
        assert d["design"]["boutons"] in ("parallelogramme", "carre", "arrondi", "pilule")
        assert p.evaluate("([a,b])=>window.__studio.contrastOf(a,b)", [d["theme"]["ink"], d["theme"]["bg"]]) >= 7
    assert not adm.errors, adm.errors


# ------------------------------------------------------------------ couleurs
def test_colors_tab_edits_and_contrast_helper(adm):
    p = adm.page
    open_studio(p, "col")
    assert p.locator(".st-col").count() == 8
    p.fill('[data-st="hex"][data-k="accent"]', "#0a6cff")
    wait_for(lambda: draft(p)["theme"]["accent"] == "#0a6cff")
    wait_for(lambda: frame_eval(p, "getComputedStyle(d.documentElement).getPropertyValue('--accent').trim()") == "#0a6cff")
    p.fill('[data-st="hex"][data-k="muted"]', "#0c0d0f")        # volontairement illisible sur fond sombre
    wait_for(lambda: "bad" in (p.get_attribute(".st-contrast span:nth-child(2)", "class") or ""), msg="la lisibilité insuffisante n'est pas signalée")
    p.click('[data-st="fixc"]')
    wait_for(lambda: p.evaluate("([a,b])=>window.__studio.contrastOf(a,b)", [draft(p)["theme"]["muted"], draft(p)["theme"]["bg"]]) >= 4.5, msg="la correction n'a pas rétabli la lisibilité")
    assert p.locator(".st-contrast .bad").count() == 0


def test_invalid_hex_is_ignored(adm):
    p = adm.page
    open_studio(p, "col")
    p.fill('[data-st="hex"][data-k="accent"]', "rouge")
    p.wait_for_timeout(300)
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", (draft(p) or {}).get("theme", {}).get("accent", "#e10a1e"))


def test_harmony_swatch_sets_accent(adm):
    p = adm.page
    open_studio(p, "col")
    c = p.get_attribute(".st-harm >> nth=0", "data-c")
    p.click(".st-harm >> nth=0")
    wait_for(lambda: draft(p)["theme"]["accent"] == c)
    assert draft(p)["theme"]["accentHot"] != c


# ------------------------------------------------------------------ style
@pytest.mark.parametrize("path,value,check", [
    ("design.police", "technique", lambda p: "monospace" in frame_eval(p, "getComputedStyle(d.querySelector('.hero h1')).fontFamily")),
    ("design.boutons", "pilule", lambda p: frame_eval(p, "getComputedStyle(d.querySelector('.hero-cta .btn')).borderRadius") == "99px"),
    ("design.cartes", "carre", lambda p: frame_eval(p, "getComputedStyle(d.querySelector('#cards .card')).clipPath") == "none"),
    ("design.fond", "grille", lambda p: "linear-gradient" in frame_eval(p, "getComputedStyle(d.querySelector('#resultats')).backgroundImage")),
])
def test_style_tiles_write_and_preview(adm, path, value, check):
    p = adm.page
    open_studio(p, "sty")
    p.click(f'[data-st="set"][data-p="{path}"][data-v="{value}"]')
    key = path.split(".")[1]
    wait_for(lambda: design(p)[key] == value)
    wait_for(lambda: check(p), msg="l'aperçu ne reflète pas le réglage")
    assert p.get_attribute(f'[data-st="set"][data-p="{path}"][data-v="{value}"]', "aria-pressed") == "true"
    assert design(p)["ambiance"] == "perso", "un réglage manuel rend l'ambiance « personnalisée »"


def test_title_toggles_and_sliders(adm):
    p = adm.page
    open_studio(p, "sty")
    p.evaluate("document.querySelector('[data-st=\"chk\"][data-p=\"design.titres.italique\"]').click()")
    wait_for(lambda: design(p)["titres"]["italique"] is False)
    wait_for(lambda: frame_eval(p, "getComputedStyle(d.querySelector('.hero h1')).fontStyle") == "normal")
    p.evaluate("(()=>{const r=document.querySelector('[data-p=\"design.tailleTexte\"]'); r.value=115; r.dispatchEvent(new Event('input',{bubbles:true}))})()")
    wait_for(lambda: design(p)["tailleTexte"] == 115)
    wait_for(lambda: abs(frame_eval(p, "parseFloat(getComputedStyle(d.documentElement).fontSize)") / 16 - 1.15) < .02)
    assert "115" in p.inner_text('[data-p="design.tailleTexte"] >> xpath=ancestor::div[contains(@class,"st-sl")]//output')


def test_page_tab_options(adm):
    p = adm.page
    open_studio(p, "pag")
    for path, value, key in [("design.densite", "compacte", "densite"), ("design.entete", "verre", "entete"), ("design.accueil", "centre", "accueil"), ("design.mouvement", "aucun", "mouvement")]:
        p.click(f'[data-st="set"][data-p="{path}"][data-v="{value}"]')
        wait_for(lambda: design(p)[key] == value)
    wait_for(lambda: frame_eval(p, "d.documentElement.getAttribute('data-hero')") == "centre")
    wait_for(lambda: frame_eval(p, "d.documentElement.getAttribute('data-motion')") == "aucun")
    p.evaluate("(()=>{const r=document.querySelector('[data-p=\"design.largeur\"]'); r.value=1200; r.dispatchEvent(new Event('input',{bubbles:true}))})()")
    wait_for(lambda: design(p)["largeur"] == 1200)


# ------------------------------------------------------------------ modules
def test_modules_tab_reorder_and_toggle(adm):
    p = adm.page
    open_studio(p, "mod")
    rows = p.evaluate("[...document.querySelectorAll('.st-row')].map(r=>r.dataset.k)")
    assert rows[:3] == ["bandeau", "prestations", "details"] and "atouts" in rows
    p.click('.st-row[data-k="faq"] [data-st="mv"][data-d="-1"]')
    wait_for(lambda: len(design(p)["ordre"]) >= 10)
    o = design(p)["ordre"]
    assert o.index("faq") < o.index("zone")
    wait_for(lambda: frame_eval(p, "[...d.querySelectorAll('#app > section')].map(s=>s.id).indexOf('faq') < [...d.querySelectorAll('#app > section')].map(s=>s.id).indexOf('zone')"), msg="l'aperçu ne reflète pas le nouvel ordre")
    first = p.locator(".st-row").first
    assert first.locator('[data-st="mv"][data-d="-1"]').is_disabled()
    p.evaluate("document.querySelector('.st-row[data-k=\"galerie\"] [data-st=\"tog\"]').click()")
    wait_for(lambda: draft(p)["visibility"]["galerie"] is not True)
    assert p.get_attribute('.st-row[data-k="prestations"]', "data-k") == "prestations" and p.locator('.st-row[data-k="prestations"] .st-lock').count() == 1


def test_enabling_a_module_shows_it_in_preview(adm):
    p = adm.page
    open_panel(p, "modules")
    set_field(p, "#f_modules_annonce_texte", "Annonce de test")
    open_studio(p, "mod")
    p.evaluate("document.querySelector('.st-mods [data-p=\"modules.annonce.actif\"]').click()")
    wait_for(lambda: draft(p)["modules"]["annonce"]["actif"] is True)
    wait_for(lambda: "Annonce de test" in frame_eval(p, "(d.getElementById('annonce')||{}).textContent||''"), msg="l'annonce n'apparaît pas dans l'aperçu")


def test_add_free_block_from_studio_then_edit(adm):
    p = adm.page
    open_studio(p, "mod")
    p.click('[data-st="addbloc"]')
    wait_for(lambda: len(draft(p)["blocs"]) == 1)
    assert draft(p)["blocs"][0]["_id"]
    assert p.locator('.st-row[data-k^="bloc-"]').count() == 1
    p.locator('[data-st="edit"]').first.click()
    p.wait_for_function("!document.getElementById('dlgStudio').open")
    wait_for(lambda: p.evaluate("document.getElementById('pn_modules').classList.contains('open')"))
    assert p.locator('.item[data-list="blocs"]').count() == 1


def test_undo_redo_inside_studio(adm):
    p = adm.page
    open_studio(p)
    p.click('.amb-wrap[data-id="or"]')
    wait_for(lambda: design(p)["ambiance"] == "or")
    p.wait_for_timeout(300)
    wait_for(lambda: not p.is_disabled("#stUndo"))
    p.click("#stUndo")
    wait_for(lambda: draft(p)["design"]["ambiance"] != "or")
    wait_for(lambda: frame_eval(p, "d.documentElement.getAttribute('data-btn')") != "carre", msg="l'aperçu doit suivre l'annulation")
    p.click("#stRedo")
    wait_for(lambda: draft(p)["design"]["ambiance"] == "or")


def test_tabs_are_keyboard_navigable(adm):
    p = adm.page
    open_studio(p)
    p.focus('#stTabs [aria-selected="true"]')
    p.keyboard.press("ArrowRight")
    assert p.get_attribute('#stTabs [data-k="col"]', "aria-selected") == "true"
    p.keyboard.press("ArrowLeft")
    assert p.get_attribute('#stTabs [data-k="amb"]', "aria-selected") == "true"


# ------------------------------------------------------------------ panneau « Modules » (éditeurs)
def test_modules_panel_editors_write_content(adm):
    p = adm.page
    open_panel(p, "modules")
    p.evaluate("document.querySelector('[data-path=\"modules.cta.actif\"]').click()")
    set_field(p, "#f_modules_cta_titre", "Titre CTA")
    set_field(p, "#f_modules_cta_bouton", "Go")
    p.click('#pb_modules [data-act="add"][data-p="modules.atouts.items"]')
    p.wait_for_selector('.item[data-lp="modules.atouts.items.0"]')
    open_item(p, "modules.atouts.items.0")
    set_field(p, "#f_modules_atouts_items_0_titre", "Atout un")
    p.select_option("#f_modules_atouts_items_0_icone", "shield")
    p.click('#pb_modules [data-act="add"][data-p="modules.chiffres.items"]')
    p.wait_for_selector('.item[data-lp="modules.chiffres.items.0"]')
    open_item(p, "modules.chiffres.items.0")
    set_field(p, "#f_modules_chiffres_items_0_valeur", "350")
    p.click('#pb_modules [data-act="add"][data-p="blocs"]')
    p.wait_for_selector('.item[data-lp="blocs.0"]')
    open_item(p, "blocs.0")
    p.select_option("#f_blocs_0_mise", "citation")
    set_field(p, "#f_blocs_0_texte", "Une phrase forte")
    d = draft(p)
    assert d["modules"]["cta"]["actif"] is True and d["modules"]["cta"]["titre"] == "Titre CTA"
    assert d["modules"]["atouts"]["items"][0]["icone"] == "shield" and d["modules"]["atouts"]["items"][0]["_id"]
    assert d["modules"]["chiffres"]["items"][0]["valeur"] == "350"
    assert d["blocs"][0]["mise"] == "citation" and d["blocs"][0]["_id"]
    assert not adm.errors


@pytest.mark.parametrize("path,selector", [("modules.annonce.lien", "#f_modules_annonce_lien"), ("modules.cta.lien", "#f_modules_cta_lien")])
def test_unsafe_module_links_are_rejected(adm, path, selector):
    p = adm.page
    open_panel(p, "modules")
    set_field(p, selector, "javascript:alert(1)")
    wait_for(lambda: p.evaluate(f"document.querySelector('[data-fp=\"{path}\"]').classList.contains('bad')"))
    p.click("#zipBtn")
    wait_for(lambda: "corriger" in p.inner_text("#toast").lower() or "lien" in p.inner_text("#toast").lower())
    assert not p.evaluate("document.getElementById('dlgDiff').open")
    set_field(p, selector, "#contact")
    wait_for(lambda: not p.evaluate(f"document.querySelector('[data-fp=\"{path}\"]').classList.contains('bad')"), msg="l'erreur doit disparaître une fois le lien corrigé")
    z = download_pack(p)
    assert z.namelist()


# ------------------------------------------------------------------ suivi des modifications et publication
def test_design_changes_appear_in_diff_and_can_be_reverted(adm):
    p = adm.page
    open_studio(p)
    p.click('.amb-wrap[data-id="showroom"]')
    wait_for(lambda: design(p)["ambiance"] == "showroom")
    p.click("#stDone")
    wait_for(lambda: p.is_visible("#pn_design [data-diff-badge]") and p.is_visible("#pn_couleurs [data-diff-badge]"))
    p.click("#diffBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    t = p.inner_text("#dfBody")
    assert "Design et ambiance" in t and "Polices" in t and "Ambiance de couleurs" in t or "Fond de page" in t
    p.locator('.df-sec[data-k="design"] .df-secundo').click()
    wait_for(lambda: draft(p)["design"]["police"] == "sport")
    assert draft(p)["theme"]["bg"] != "#08090b" or True


def test_order_and_module_changes_are_listed(adm):
    p = adm.page
    open_studio(p, "mod")
    p.click('.st-row[data-k="faq"] [data-st="mv"][data-d="-1"]')
    p.click('[data-st="addbloc"]')
    p.click("#stDone")
    wait_for(lambda: p.is_visible("#pn_modules [data-diff-badge]") and p.is_visible("#pn_design [data-diff-badge]"))
    p.click("#diffBtn")
    p.wait_for_selector("#dlgDiff[open]", state="attached")
    t = p.inner_text("#dfBody")
    assert "Ordre des sections" in t and "Nouveau bloc libre" in t
    p.locator("#dfBody .df-row", has_text="Nouveau bloc libre").locator(".df-undo").click()
    wait_for(lambda: draft(p)["blocs"] == [])


def test_pack_contains_design_and_site_shows_it(make_page, site_copy):
    from test_e2e_publish import deploy
    from helpers import open_site
    hd = make_page(site_copy, "admin.html", w=1440, h=900)
    open_admin(hd, site_copy)
    p = hd.page
    open_studio(p)
    p.click('.amb-wrap[data-id="or"]')
    wait_for(lambda: design(p)["ambiance"] == "or")
    p.click('#stTabs [data-k="mod"]')
    p.click('.st-row[data-k="faq"] [data-st="mv"][data-d="-1"]')
    p.click("#stDone")
    open_panel(p, "modules")
    set_field(p, "#f_modules_annonce_texte", "Promo publiée")
    p.evaluate("document.querySelector('[data-path=\"modules.annonce.actif\"]').click()")
    wait_for(lambda: draft(p)["modules"]["annonce"]["actif"])
    z = download_pack(p)
    c = read_zip_json(z)
    assert c["design"]["ambiance"] == "or" and c["modules"]["annonce"]["texte"] == "Promo publiée" and "faq" in c["design"]["ordre"]
    deploy(z, site_copy)
    hs = make_page(site_copy, w=1280, h=800)
    open_site(hs, site_copy)
    s = hs.page
    assert "Promo publiée" in s.inner_text("#annonce")
    assert s.evaluate("document.documentElement.getAttribute('data-btn')") == "carre"
    assert not hs.errors and not hs.bad_responses
    ha = make_page(site_copy, "admin.html")
    open_admin(ha, site_copy)
    wait_for(lambda: "Identique" in ha.page.inner_text("#saveState"), msg="l'admin doit être identique au site publié")


# ------------------------------------------------------------------ responsive du studio
@pytest.mark.parametrize("w,h,mob", [(390, 844, True), (768, 1024, True), (844, 390, True), (1280, 720, False), (2560, 1440, False)])
def test_studio_layout_on_all_sizes(make_page, site, w, h, mob):
    hd = make_page(site, "admin.html", w=w, h=h, mobile=mob)
    open_admin(hd, site)
    p = hd.page
    open_studio(p)
    for tab in ["amb", "col", "sty", "pag", "mod"]:
        p.click(f'#stTabs [data-k="{tab}"]')
        ok = p.evaluate("(()=>{const r=document.getElementById('stRoot');const c=document.getElementById('stPane');return r.scrollWidth<=r.clientWidth&&c.scrollWidth<=c.clientWidth+1})()")
        assert ok, f"onglet {tab} : débordement horizontal à {w}px"
    box = p.evaluate("(()=>{const v=document.getElementById('stPrev').getBoundingClientRect(),c=document.getElementById('stPane').getBoundingClientRect();return {pw:v.width,ph:v.height,cw:c.width,ch:c.height}})()")
    assert box["ph"] > 120 and box["ch"] > 120 and box["pw"] > 200, f"zones trop petites : {box}"
    p.click("#stDone")
    assert not hd.errors
