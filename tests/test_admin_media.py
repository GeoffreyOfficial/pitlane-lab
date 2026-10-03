"""Photothèque et éditeur d'image : formats, import, bibliothèque, recadrage, détourage, persistance, mobile."""
import base64
import mimetypes

import pytest

from conftest import FIXTURES
from helpers import (close_media, confirm_dialog, download_pack, draft, import_files, library_paths, open_admin, open_item, open_panel,
                     pixel_info, read_zip_json, set_field, wait_for)

pytestmark = pytest.mark.admin


@pytest.fixture()
def adm(make_page, site):
    hd = make_page(site, "admin.html", w=1280, h=900)
    open_admin(hd, site)
    return hd


def file_in_page(path):
    """Code JavaScript qui fabrique un objet File à partir d'un fichier de test."""
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"(()=>{{const b=Uint8Array.from(atob('{b64}'),c=>c.charCodeAt(0)); return new File([b],'{path.name}',{{type:'{mime}'}});}})()"


def card(p, path):
    return p.locator(f'#mdGrid .md-card[data-path="{path}"]')


def select_card(p, path):
    card(p, path).click()
    wait_for(lambda: p.evaluate("document.getElementById('mdDetail').classList.contains('show')"))


def detail_src(p):
    return p.get_attribute("#mdDetail .pvw img", "src")


def import_one(p, name):
    """Importe un fichier ; renvoie (chemin de la nouvelle photo ou None, message d'erreur éventuel)."""
    before = set(library_paths(p)) if p.evaluate("document.getElementById('dlgMedia').open") else set()
    import_files(p, [FIXTURES / name])
    if p.evaluate("document.getElementById('dlgInfo').open"):
        msg = p.inner_text("#inBody")
        p.click("#inOk")
        p.wait_for_function("!document.getElementById('dlgInfo').open")
        return None, msg
    new = [x for x in library_paths(p) if x not in before]
    return (new[0] if new else None), ""


# ------------------------------------------------------------------ formats
ACCEPTED = ["photo.jpg", "exif_rot6.jpg", "alpha.png", "photo.webp", "static.gif", "animated.gif", "photo.bmp", "photo.tif", "photo.avif", "photo.heic", "icon.ico", "vector.svg"]
REFUSED = [("corrupt.jpg", "incomplète"), ("fake.jpg", "pas une image"), ("empty.png", "vide"), ("document.pdf", "PDF")]


@pytest.mark.parametrize("name", ACCEPTED)
def test_every_supported_format_imports(adm, name):
    p = adm.page
    path, msg = import_one(p, name)
    assert path, f"{name} refusé : {msg}"
    meta = p.evaluate(f"(()=>{{const e=JSON.parse(localStorage.getItem('pitlanelab_admin_draft_v1')).medias.find(m=>m.path==='{path}'); return e}})()")
    assert meta["w"] > 0 and meta["h"] > 0 and meta["bytes"] > 0
    assert path.startswith("images/uploads/")
    assert not adm.errors, adm.errors


@pytest.mark.parametrize("name,fragment", REFUSED, ids=[r[0] for r in REFUSED])
def test_invalid_files_are_refused_with_a_clear_message(adm, name, fragment):
    p = adm.page
    path, msg = import_one(p, name)
    assert path is None, f"{name} n'aurait pas dû être accepté"
    assert fragment.lower() in msg.lower(), f"message inattendu pour {name} : {msg}"
    assert library_paths(p) == [] and not adm.errors


def test_exif_orientation_is_applied(adm):
    p = adm.page
    path, _ = import_one(p, "exif_rot6.jpg")
    m = p.evaluate(f"JSON.parse(localStorage.getItem('pitlanelab_admin_draft_v1')).medias.find(x=>x.path==='{path}')")
    assert m["h"] > m["w"], f"la photo prise en travers doit être remise à l'endroit ({m['w']}×{m['h']})"


def test_gps_and_camera_metadata_are_stripped(adm):
    p = adm.page
    path, _ = import_one(p, "quad_exif.jpg")
    select_card(p, path)
    has_exif = p.evaluate("""async (s)=>{const b=new Uint8Array(await (await (await fetch(s)).blob()).arrayBuffer()); return String.fromCharCode(...b.slice(0,600)).includes('Exif')}""", detail_src(p))
    assert has_exif is False, "les métadonnées (position GPS, appareil) doivent être retirées"


def test_animated_gif_keeps_animation_and_svg_is_sanitized(adm):
    p = adm.page
    gif, _ = import_one(p, "animated.gif")
    select_card(p, gif)
    info = p.evaluate("""async (s)=>{const b=await (await fetch(s)).blob(); const u=new Uint8Array(await b.arrayBuffer()); let n=0; for(let i=0;i<u.length-2;i++) if(u[i]==0x21&&u[i+1]==0xF9&&u[i+2]==4) n++; return {type:b.type,frames:n}}""", detail_src(p))
    assert info["type"] == "image/gif" and info["frames"] >= 3
    svg, _ = import_one(p, "vector.svg")
    select_card(p, svg)
    txt = p.evaluate("async (s)=>await (await (await fetch(s)).blob()).text()", detail_src(p))
    assert "<script" not in txt and "onclick" not in txt and "<circle" in txt


def test_transparency_is_preserved_as_png(adm):
    p = adm.page
    path, _ = import_one(p, "alpha.png")
    select_card(p, path)
    assert path.endswith(".png")
    pts = [[(45 * k + 34) / 900, y / 10] for k in range(20) for y in range(1, 10)] + [[(45 * k + 5) / 900, y / 10] for k in range(20) for y in range(1, 10)]   # entre les bandes (transparent) et sur les bandes (opaque)
    alphas = [q[3] for q in pixel_info(p, detail_src(p), pts)["px"]]
    assert min(alphas) < 10 and max(alphas) > 240, "la transparence du PNG doit être conservée (pixels transparents et opaques)"


def test_duplicate_file_is_not_added_twice(adm):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    import_files(p, [FIXTURES / "photo.jpg"])
    assert len(library_paths(p)) == 1
    assert "déjà" in p.inner_text("#toast").lower()


def test_mixed_batch_reports_each_failure_and_keeps_good_files(adm):
    p = adm.page
    import_files(p, [FIXTURES / n for n in ["photo.jpg", "fake.jpg", "alpha.png", "empty.png", "document.pdf"]])
    p.wait_for_selector("#dlgInfo[open]", state="attached")
    assert p.locator("#inBody .fails li").count() == 3
    p.click("#inOk")
    assert len(library_paths(p)) == 2


def test_batch_of_twelve_photos(adm, tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    import random
    files = []
    for i in range(12):
        im = PIL.new("RGB", (1600, 1000), (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
        for k in range(i * 3):
            im.paste((k * 20 % 255, i * 20 % 255, 100), (k * 30, k * 20, k * 30 + 200, k * 20 + 120))
        f = tmp_path / f"lot_{i:02d}.jpg"
        im.save(f, quality=85)
        files.append(f)
    import_files(adm.page, files)
    assert len(library_paths(adm.page)) == 12
    assert adm.page.evaluate("document.getElementById('mdProg').hidden") is True


# ------------------------------------------------------------------ bibliothèque
def test_library_filters_search_sort_and_stats(adm):
    p = adm.page
    import_files(p, [FIXTURES / n for n in ["photo.jpg", "alpha.png", "photo.webp"]])
    assert "3 photos" in p.inner_text("#mdStats")
    p.fill("#mdSearch", "alpha")
    wait_for(lambda: p.locator("#mdGrid .md-card").count() == 1)
    p.fill("#mdSearch", "zzz")
    wait_for(lambda: p.locator("#mdGrid .md-empty").count() == 1)
    p.fill("#mdSearch", "")
    p.click('#mdChips [data-f="unused"]')
    assert p.locator("#mdGrid .md-card").count() == 3
    p.click('#mdChips [data-f="used"]')
    assert p.locator("#mdGrid .md-card").count() == 0
    p.click('#mdChips [data-f="site"]')
    wait_for(lambda: p.locator("#mdGrid .md-card").count() == 10, timeout=8, msg="les fichiers du site doivent être listés")
    wait_for(lambda: p.evaluate("document.querySelectorAll('#mdGrid .md-card.miss').length") == 0, timeout=6, msg="fichier du site introuvable : " + str(p.evaluate("[...document.querySelectorAll('#mdGrid .md-card.miss')].map(c=>c.dataset.path)")) + " | HTTP en échec : " + str(adm.bad_responses) + " | externes : " + str(adm.external) + " | erreurs : " + str(adm.errors))
    p.click('#mdChips [data-f="all"]')
    sizes = []
    p.select_option("#mdSort", "size")
    sizes = p.evaluate("[...document.querySelectorAll('#mdGrid .md-in')].map(e=>e.textContent)")
    assert len(sizes) == 3


def test_pick_photo_for_a_field_and_clear_it(adm):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    close_media(p)
    open_panel(p, "prestations")
    open_item(p, "services.0")
    p.click('.item[data-lp="services.0"] button.thumb')
    p.wait_for_selector("#dlgMedia[open]", state="attached")
    assert "Prestation" in p.inner_text("#mdSub")
    p.locator("#mdGrid .md-card").first.click()
    p.click('#mdFoot [data-f="use"]')
    wait_for(lambda: draft(p)["services"][0]["image"].startswith("images/uploads/"))
    assert "à envoyer" in p.inner_text('.item[data-lp="services.0"] .imgfld .lbl'), "le champ doit signaler une photo à envoyer"
    p.click('.item[data-lp="services.0"] [data-act="img-clear"]')
    wait_for(lambda: draft(p)["services"][0]["image"] == "")


def test_delete_used_photo_clears_field_and_can_be_undone(adm):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    path = library_paths(p)[0]
    close_media(p)
    open_panel(p, "accueil")
    p.fill('.imgfld[data-fp="images.hero"] details input', path) if False else None
    p.click('.imgfld[data-fp="images.hero"] button.thumb')
    p.locator("#mdGrid .md-card").first.click()
    p.click('#mdFoot [data-f="use"]')
    wait_for(lambda: draft(p)["images"]["hero"] == path)
    p.click("#mediaBtn")
    select_card(p, path)
    assert "accueil" in p.inner_text("#mdDetail").lower()
    p.click('#mdDetail [data-d="delete"]')
    p.wait_for_selector("#dlgConfirm[open]", state="attached")
    assert "Photo d'accueil" in p.inner_text("#cText")
    p.click("#cYes")
    wait_for(lambda: draft(p)["images"]["hero"] == "" and not [m for m in draft(p)["medias"] if m["path"] == path])
    close_media(p)
    p.click("#undoBtn")
    wait_for(lambda: draft(p)["images"]["hero"] == path and any(m["path"] == path for m in draft(p)["medias"]))


def test_replace_file_updates_every_usage(adm):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    old = library_paths(p)[0]
    close_media(p)
    open_panel(p, "accueil")
    p.click('.imgfld[data-fp="images.hero"] button.thumb')
    p.locator("#mdGrid .md-card").first.click()
    p.click('#mdFoot [data-f="use"]')
    wait_for(lambda: draft(p)["images"]["hero"] == old)
    p.click("#mediaBtn")
    select_card(p, old)
    p.set_input_files('#mdDetail input[data-d="replace"]', str(FIXTURES / "alpha.png"))
    wait_for(lambda: draft(p)["images"]["hero"] not in ("", old), msg="la photo n'a pas été remplacée")
    assert not any(m["path"] == old for m in draft(p)["medias"])


def test_clean_unused_photos(adm):
    p = adm.page
    import_files(p, [FIXTURES / n for n in ["photo.jpg", "alpha.png", "photo.webp"]])
    p.click("#mdClean")
    p.wait_for_selector("#dlgClean[open]", state="attached")
    assert p.locator("#clList li").count() == 3
    p.locator("#clList input").first.uncheck()
    p.click("#clYes")
    wait_for(lambda: len(library_paths(p)) == 1, msg="le nettoyage n'a pas conservé la photo décochée")
    p.click("#mdClean")
    p.wait_for_selector("#dlgClean[open]", state="attached")
    p.click("#clNo")


def test_gallery_add_from_library_blocks_duplicates(adm):
    p = adm.page
    import_files(p, [FIXTURES / n for n in ["photo.jpg", "alpha.png"]])
    close_media(p)
    open_panel(p, "galerie")
    p.click('#pb_galerie [data-m="gal-pick"]')
    p.wait_for_selector("#dlgMedia[open]", state="attached")
    p.locator("#mdGrid .md-card").nth(0).click()
    p.locator("#mdGrid .md-card").nth(1).click()
    p.click('#mdFoot [data-f="add"]')
    wait_for(lambda: len(draft(p)["galerie"]) == 2)
    p.click('#pb_galerie [data-m="gal-pick"]')
    assert p.locator("#mdGrid .md-card.in-gal").count() == 2, "les photos déjà en galerie doivent être signalées"
    close_media(p)


def test_rename_photo_persists(adm):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    path = library_paths(p)[0]
    select_card(p, path)
    p.fill('#mdDetail input[data-d="rename"]', "Ma belle photo")
    p.dispatch_event('#mdDetail input[data-d="rename"]', "change")
    wait_for(lambda: [m for m in draft(p)["medias"] if m["path"] == path][0]["nom"] == "Ma belle photo")
    assert "Ma belle photo" in p.inner_text("#mdGrid .md-nm")


def test_site_files_are_protected(adm):
    p = adm.page
    p.click("#mediaBtn")
    p.click('#mdChips [data-f="site"]')
    wait_for(lambda: p.locator("#mdGrid .md-card").count() == 10)
    p.locator("#mdGrid .md-card").first.click()
    wait_for(lambda: p.evaluate("document.getElementById('mdDetail').classList.contains('show')"))
    assert p.locator('#mdDetail [data-d="delete"]').count() == 0 and p.locator('#mdDetail input[data-d="replace"]').count() == 0


# ------------------------------------------------------------------ glisser-déposer et collage
def dispatch_files(p, selector, names, events=("dragenter", "dragover", "drop")):
    codes = ",".join(file_in_page(FIXTURES / n) for n in names)
    p.evaluate(f"""(()=>{{const dt=new DataTransfer(); [{codes}].forEach(f=>dt.items.add(f)); const t=document.querySelector({selector!r});
        for(const ty of {list(events)!r}) t.dispatchEvent(new DragEvent(ty,{{bubbles:true,cancelable:true,dataTransfer:dt}}))}})()""")


def test_drop_on_a_field_assigns_the_photo(adm):
    p = adm.page
    open_panel(p, "accueil")
    dispatch_files(p, '.imgfld[data-fp="images.hero"]', ["photo.jpg"])
    wait_for(lambda: (draft(p) or {}).get("images", {}).get("hero", "").startswith("images/uploads/"), timeout=10)


def test_drop_elsewhere_opens_the_library(adm):
    p = adm.page
    dispatch_files(p, "#panels", ["photo.jpg", "alpha.png"])
    p.wait_for_selector("#dlgMedia[open]", state="attached", timeout=10000)
    wait_for(lambda: len(library_paths(p)) == 2)


def test_paste_an_image(adm):
    p = adm.page
    code = file_in_page(FIXTURES / "alpha.png")
    p.evaluate(f"(()=>{{const dt=new DataTransfer(); dt.items.add({code}); document.dispatchEvent(new ClipboardEvent('paste',{{clipboardData:dt,bubbles:true,cancelable:true}}))}})()")
    p.wait_for_selector("#dlgMedia[open]", state="attached", timeout=10000)
    wait_for(lambda: len(library_paths(p)) == 1)


# ------------------------------------------------------------------ éditeur
def open_editor(p, name):
    path, _ = import_one(p, name)
    select_card(p, path)
    p.click('#mdDetail [data-d="crop"]')
    p.wait_for_selector("#dlgCrop[open]", state="attached")
    p.wait_for_function("document.getElementById('ceRead').textContent.includes('×')")
    return path


def save_copy(p):
    """Clique « Enregistrer » dans l'éditeur et renvoie le chemin de la nouvelle photo (trouvée par différence)."""
    before = set(library_paths(p))
    p.click('#ceFoot [data-c="copy"]')
    p.wait_for_function("!document.getElementById('dlgCrop').open", timeout=15000)
    wait_for(lambda: len(set(library_paths(p)) - before) == 1, msg="la copie n'apparaît pas dans la photothèque")
    return (set(library_paths(p)) - before).pop()


def saved_pixels(p, path, pts):
    select_card(p, path)
    return pixel_info(p, detail_src(p), pts)


def near(px, rgb, tol=45):
    return all(abs(a - b) <= tol for a, b in zip(px[:3], rgb))


RED, GREEN, BLUE, YELLOW = (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)


def test_editor_crop_then_rotate_follows_the_frame(adm):
    p = adm.page
    open_editor(p, "quad.png")
    he = p.locator('.ce-h[data-h="e"]').bounding_box()
    box = p.locator("#ceBox").bounding_box()
    cx, cy = he["x"] + he["width"] / 2, he["y"] + he["height"] / 2
    p.mouse.move(cx, cy)
    p.mouse.down()
    p.mouse.move(box["x"] + box["width"] / 2, cy, steps=8)
    p.mouse.up()
    p.click('#cePanel [data-t="cw"]')
    out = save_copy(p)
    r = saved_pixels(p, out, [[.25, .25], [.75, .25], [.25, .75], [.75, .75]])
    assert abs(r["w"] - 200) <= 3 and abs(r["h"] - 200) <= 3, f"dimensions {r['w']}×{r['h']}"
    tl, tr, bl, br = r["px"]
    assert near(tl, BLUE) and near(tr, RED) and near(bl, BLUE) and near(br, RED), r["px"]


def test_editor_mirror_horizontal(adm):
    p = adm.page
    open_editor(p, "quad.png")
    p.click('#cePanel [data-t="fh"]')
    out = save_copy(p)
    tl, tr, bl, br = saved_pixels(p, out, [[.25, .25], [.75, .25], [.25, .75], [.75, .75]])["px"]
    assert near(tl, GREEN) and near(tr, RED) and near(bl, YELLOW) and near(br, BLUE)


def test_editor_keyboard_moves_and_resizes_the_frame(adm):
    p = adm.page
    open_editor(p, "quad.png")
    p.click('#cePanel [data-r="1"]')
    p.focus("#ceBox")
    b0 = p.locator("#ceBox").bounding_box()
    for _ in range(5):
        p.keyboard.press("ArrowRight")
    p.keyboard.press("-")
    b1 = p.locator("#ceBox").bounding_box()
    assert b1["x"] != b0["x"] or b1["width"] != b0["width"]
    assert abs(b1["width"] - b1["height"]) <= 2, "le format 1:1 doit rester carré"


def test_editor_ratio_is_enforced_while_dragging_handles(adm):
    p = adm.page
    open_editor(p, "photo.jpg")
    p.click('#cePanel [data-r="1.7777777777777777"]') if p.locator('#cePanel [data-r="1.7777777777777777"]').count() else p.click('#cePanel [data-r="1"]')
    h = p.locator('.ce-h[data-h="se"]').bounding_box()
    cx, cy = h["x"] + h["width"] / 2, h["y"] + h["height"] / 2
    ratio0 = p.locator("#ceBox").bounding_box()
    p.mouse.move(cx, cy)
    p.mouse.down()
    p.mouse.move(cx - 60, cy - 20, steps=6)
    p.mouse.up()
    b = p.locator("#ceBox").bounding_box()
    assert abs((b["width"] / b["height"]) - (ratio0["width"] / ratio0["height"])) < .03, "le format imposé n'est pas conservé"


def test_editor_background_removal_options(adm):
    p = adm.page
    open_editor(p, "logo_fond_blanc.jpg")
    p.check("#ceBgOn")
    p.wait_for_timeout(500)
    out = save_copy(p)
    r = saved_pixels(p, out, [[.01, .01], [.3, .5], [.45, .5]])["px"]
    assert r[0][3] < 20 and r[1][3] > 240 and r[1][0] > 150, f"détourage incorrect : {r}"
    assert r[2][3] > 240, "le trou intérieur doit rester par défaut"
    assert out.endswith(".png")
    p.click('#mdDetail [data-d="crop"]')
    p.wait_for_selector("#dlgCrop[open]", state="attached")
    p.wait_for_function("document.getElementById('ceRead').textContent.includes('×')")


def test_editor_background_removal_inside_too(adm):
    p = adm.page
    open_editor(p, "logo_fond_blanc.jpg")
    p.check("#ceBgOn")
    p.check("#ceBgIn")
    p.wait_for_timeout(500)
    out = save_copy(p)
    r = saved_pixels(p, out, [[.3, .5], [.45, .5]])["px"]
    assert r[0][3] > 240 and r[1][3] < 20, f"le trou doit devenir transparent : {r}"


def test_editor_tint_and_fill(adm):
    p = adm.page
    open_editor(p, "silhouette_noire.png")
    p.check("#ceTintOn")
    p.wait_for_timeout(400)
    out = save_copy(p)
    white = p.evaluate("""async (s)=>{const b=await createImageBitmap(await (await fetch(s)).blob()); const c=document.createElement('canvas'); c.width=b.width; c.height=b.height; const g=c.getContext('2d'); g.drawImage(b,0,0); const d=g.getImageData(0,0,b.width,b.height).data; let n=0,w=0; for(let i=0;i<d.length;i+=4){ if(d[i+3]>200){n++; if(d[i]>240&&d[i+1]>240&&d[i+2]>240) w++;} } return n? w/n : 0}""", detail_src(p))
    assert white > .99, "la silhouette doit devenir entièrement blanche"
    close_media(p)
    p.click("#mediaBtn")
    open_editor(p, "icone_transparente.png")
    p.check("#ceFillOn")
    p.fill("#ceFill", "#e10a1e")
    p.dispatch_event("#ceFill", "input")
    p.wait_for_timeout(400)
    out2 = save_copy(p)
    px = saved_pixels(p, out2, [[.02, .02], [.5, .5]])["px"]
    assert px[0][3] == 255 and px[0][0] > 200 and px[0][1] < 40 and px[1][:3] == [255, 255, 255]


def test_editor_cancel_asks_confirmation_only_when_changed(adm):
    p = adm.page
    open_editor(p, "quad.png")
    p.click('#ceFoot [data-c="cancel"]')
    p.wait_for_function("!document.getElementById('dlgCrop').open")
    select_card(p, library_paths(p)[0])
    p.click('#mdDetail [data-d="crop"]')
    p.wait_for_selector("#dlgCrop[open]", state="attached")
    p.click('#cePanel [data-t="cw"]')
    p.click('#ceFoot [data-c="cancel"]')
    confirm_dialog(p, yes=False)
    assert p.evaluate("document.getElementById('dlgCrop').open"), "« Continuer » doit garder l'éditeur ouvert"
    p.keyboard.press("Escape")
    confirm_dialog(p, yes=True)
    p.wait_for_function("!document.getElementById('dlgCrop').open")


def test_editor_replace_original_updates_usages(adm):
    p = adm.page
    old = open_editor(p, "quad.png")
    p.click('#ceFoot [data-c="cancel"]')
    p.wait_for_function("!document.getElementById('dlgCrop').open")
    close_media(p)
    open_panel(p, "accueil")
    p.click('.imgfld[data-fp="images.hero"] button.thumb')
    p.locator("#mdGrid .md-card").first.click()
    p.click('#mdFoot [data-f="use"]')
    wait_for(lambda: draft(p)["images"]["hero"] == old)
    p.click('.imgfld[data-fp="images.hero"] [data-m="crop"]')
    p.wait_for_selector("#dlgCrop[open]", state="attached")
    p.wait_for_function("document.getElementById('ceRead').textContent.includes('×')")
    p.click('#cePanel [data-t="cw"]')
    p.click('#ceFoot [data-c="replace"]')
    p.wait_for_function("!document.getElementById('dlgCrop').open", timeout=15000)
    wait_for(lambda: draft(p)["images"]["hero"] not in ("", old))
    assert not any(m["path"] == old for m in draft(p)["medias"])


def test_editor_on_a_site_file_only_offers_a_copy(adm):
    p = adm.page
    p.click("#mediaBtn")
    p.click('#mdChips [data-f="site"]')
    wait_for(lambda: p.locator("#mdGrid .md-card").count() == 10)
    p.locator("#mdGrid .md-card").first.click()
    p.click('#mdDetail [data-d="crop"]')
    p.wait_for_selector("#dlgCrop[open]", state="attached")
    p.wait_for_function("document.getElementById('ceRead').textContent.includes('×')")
    assert p.locator('#ceFoot [data-c="replace"]').count() == 0


# ------------------------------------------------------------------ persistance et cas limites
def test_photos_survive_reload_and_are_published_in_the_pack(adm, tmp_path):
    p = adm.page
    import_files(p, [FIXTURES / "photo.jpg"])
    path = library_paths(p)[0]
    close_media(p)
    p.wait_for_timeout(500)
    p.reload()
    p.wait_for_selector("#dlgConfirm[open]", state="attached")
    p.click("#cYes")
    p.wait_for_selector(".panel")
    p.click("#mediaBtn")
    wait_for(lambda: card(p, path).count() == 1, msg="la photo n'a pas été retrouvée après rechargement")
    assert p.evaluate("document.querySelector('#mdGrid .md-card img').src.startsWith('blob:')")
    assert p.locator("#mdGrid .bdg.new").count() == 1
    close_media(p)
    z = download_pack(p, tmp_path)
    assert path in z.namelist() and path in [m["path"] for m in read_zip_json(z)["medias"]]
    data = z.read(path)
    assert data[:3] == b"\xff\xd8\xff"


def test_works_when_browser_storage_is_unavailable(make_page, site):
    hd = make_page(site, "admin.html", init_scripts=["Object.defineProperty(window,'indexedDB',{value:{open(){throw new Error('indisponible')}}})"])
    open_admin(hd, site)
    p = hd.page
    import_files(p, [FIXTURES / "photo.jpg"])
    assert len(library_paths(p)) == 1
    wait_for(lambda: "navigateur" in p.inner_text("#toast").lower(), msg="aucun avertissement de stockage indisponible")
    close_media(p)
    z = download_pack(p)
    assert any(n.startswith("images/uploads/") for n in z.namelist()), "le pack doit contenir la photo même sans stockage navigateur"


def test_library_on_phone_has_no_overflow_and_detail_sheet(make_page, site):
    hd = make_page(site, "admin.html", w=390, h=844, mobile=True)
    open_admin(hd, site)
    p = hd.page
    import_files(p, [FIXTURES / n for n in ["photo.jpg", "alpha.png"]])
    assert p.evaluate("(()=>{const d=document.getElementById('mdRoot');return d.scrollWidth<=d.clientWidth})()")
    assert not p.evaluate("document.getElementById('mdDetail').classList.contains('show')"), "la fiche ne doit pas s'ouvrir toute seule sur téléphone"
    p.locator("#mdGrid .md-card").first.tap()
    wait_for(lambda: p.evaluate("document.getElementById('mdDetail').classList.contains('show')"))
    top = p.evaluate("document.getElementById('mdDetail').getBoundingClientRect().top")
    assert top >= 0
    p.tap('#mdDetail [data-d="close"]')
    wait_for(lambda: not p.evaluate("document.getElementById('mdDetail').classList.contains('show')"))


def test_editor_touch_drag_on_phone(make_page, site):
    hd = make_page(site, "admin.html", w=390, h=844, mobile=True)
    open_admin(hd, site)
    p = hd.page
    path, _ = import_one(p, "photo.jpg")
    p.locator("#mdGrid .md-card").first.tap()
    wait_for(lambda: p.evaluate("document.getElementById('mdDetail').classList.contains('show')"))
    p.tap('#mdDetail [data-d="crop"]')
    p.wait_for_selector("#dlgCrop[open]", state="attached")
    p.wait_for_function("document.getElementById('ceRead').textContent.includes('×')")
    cdp = hd.context.new_cdp_session(p)
    hb = p.locator('.ce-h[data-h="se"]').bounding_box()
    x, y = hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2
    before = p.inner_text("#ceRead")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for i in range(1, 9):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x - i * 8, "y": y - i * 8}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    wait_for(lambda: p.inner_text("#ceRead") != before, msg="le recadrage au doigt ne fonctionne pas")
    assert p.evaluate("(()=>{const d=document.getElementById('ceRoot');return d.scrollWidth<=d.clientWidth})()")
