"""Listes de l'administration : ajout, déplacement, suppression/annulation, identifiants stables, persistance."""
import pytest

from helpers import confirm_dialog, download_pack, draft, open_admin, open_item, open_panel, read_zip_json, set_field, wait_for

pytestmark = pytest.mark.admin

# (panneau, chemin de liste, champs à remplir pour être valide, champ « nom »)
LISTS = [
    ("prestations", "services", [("titre", "Prestation de test"), ("prix", "10 €")], "titre"),
    ("faq", "faq", [("q", "Question de test ?")], "q"),
    ("methode", "etapes", [("titre", "Étape de test")], "titre"),
    ("avis", "avis", [("nom", "Zoé"), ("texte", "Très bien")], "nom"),
    ("details", "zones", [("titre", "Point de test")], "titre"),
    ("estimateur", "estimateur.tailles", [("label", "Camion"), ("coef", "1.5")], "label"),
    ("estimateur", "estimateur.etats", [("label", "Moyen"), ("coef", "1.1")], "label"),
]


@pytest.fixture()
def adm(make_page, site):
    hd = make_page(site, "admin.html", w=1280, h=900)
    open_admin(hd, site)
    return hd


def items(p, lp):
    node = draft(p)
    for k in lp.split("."):
        node = node[k]
    return node


def fid(lp, i, key):
    return "f_" + lp.replace(".", "_") + f"_{i}_{key}"


def add_item(p, panel, lp, fields):
    open_panel(p, panel)
    n = len(items(p, lp)) if draft(p) else p.locator(f'.item[data-list="{lp}"]').count()
    p.click(f'#pb_{panel} [data-act="add"][data-p="{lp}"]')
    p.wait_for_selector(f'.item[data-lp="{lp}.{n}"]')
    open_item(p, f"{lp}.{n}")
    for key, val in fields:
        set_field(p, "#" + fid(lp, n, key), val)
    return n


def current(p, lp):
    node = draft(p)
    for k in lp.split("."):
        node = node[k]
    return node


@pytest.mark.parametrize("panel,lp,fields,name", LISTS, ids=[x[1] for x in LISTS])
class TestListOperations:
    def test_add_gets_a_unique_stable_id(self, adm, panel, lp, fields, name):
        p = adm.page
        open_panel(p, panel)
        base = p.locator(f'.item[data-list="{lp}"]').count()
        n = add_item(p, panel, lp, fields)
        assert n == base
        wait_for(lambda: len(current(p, lp)) == base + 1)
        ids = [x["_id"] for x in current(p, lp)]
        assert all(ids) and len(set(ids)) == len(ids), f"identifiants _id manquants ou en double : {ids}"
        assert current(p, lp)[-1][fields[0][0]] == fields[0][1]
        assert not adm.errors

    def test_move_up_and_down_keeps_ids(self, adm, panel, lp, fields, name):
        p = adm.page
        open_panel(p, panel)
        if p.locator(f'.item[data-list="{lp}"]').count() < 1:      # une liste vide : il faut deux éléments pour pouvoir déplacer
            add_item(p, panel, lp, fields)
        n = add_item(p, panel, lp, fields)
        wait_for(lambda: len(current(p, lp)) == n + 1)
        ids_before = [x["_id"] for x in current(p, lp)]
        newest = ids_before[-1]
        p.click(f'#pb_{panel} [data-act="mv"][data-p="{lp}"][data-i="{n}"][data-d="-1"]')
        wait_for(lambda: [x["_id"] for x in current(p, lp)][-2] == newest, msg="le déplacement vers le haut n'a pas eu lieu")
        assert sorted(x["_id"] for x in current(p, lp)) == sorted(ids_before), "un déplacement ne doit pas changer les identifiants"
        p.click(f'#pb_{panel} [data-act="mv"][data-p="{lp}"][data-i="{n - 1}"][data-d="1"]')
        wait_for(lambda: [x["_id"] for x in current(p, lp)][-1] == newest)
        assert [x["_id"] for x in current(p, lp)] == ids_before

    def test_delete_confirm_cancel_and_undo(self, adm, panel, lp, fields, name):
        p = adm.page
        n = add_item(p, panel, lp, fields)
        wait_for(lambda: len(current(p, lp)) == n + 1)
        total = n + 1
        # refus : rien ne change
        p.click(f'.item[data-lp="{lp}.{n}"] [data-act="del"]')
        confirm_dialog(p, yes=False)
        assert len(current(p, lp)) == total
        # confirmation : supprimée, puis annulée avec ↶
        p.click(f'.item[data-lp="{lp}.{n}"] [data-act="del"]')
        confirm_dialog(p, yes=True)
        wait_for(lambda: len(current(p, lp)) == total - 1)
        wait_for(lambda: not p.is_disabled("#undoBtn"))
        p.click("#undoBtn")
        wait_for(lambda: len(current(p, lp)) == total, msg="↶ ne restaure pas l'élément supprimé")
        assert current(p, lp)[-1][fields[0][0]] == fields[0][1]

    def test_survives_reload_via_draft(self, adm, panel, lp, fields, name):
        p = adm.page
        add_item(p, panel, lp, fields)
        p.wait_for_timeout(900)
        total = len(current(p, lp))
        p.reload()
        p.wait_for_selector("#dlgConfirm[open]", state="attached")
        p.click("#cYes")
        p.wait_for_selector(".panel")
        assert len(current(p, lp)) == total


def test_service_visibility_switch_and_header_summary(adm):
    p = adm.page
    open_panel(p, "prestations")
    sw = '.item[data-lp="services.0"] .ih input[type=checkbox]'
    assert p.is_checked(sw)
    p.evaluate(f"document.querySelector('{sw}').click()")
    wait_for(lambda: draft(p)["services"][0]["visible"] is False)
    assert "off" in p.get_attribute('.item[data-lp="services.0"]', "class")
    title = draft(p)["services"][0]["titre"]
    open_item(p, "services.0")
    set_field(p, "#f_services_0_titre", "Titre renommé")
    wait_for(lambda: "Titre renommé" in p.inner_text('.item[data-lp="services.0"] [data-ti]'), msg="l'en-tête de ligne ne suit pas le titre")
    assert title != "Titre renommé"


def test_inclusions_list_inside_a_service(adm):
    p = adm.page
    open_panel(p, "prestations")
    open_item(p, "services.0")
    n0 = p.locator('.item[data-lp="services.0"] input[data-path^="services.0.inclus."]').count()
    p.click('.item[data-lp="services.0"] [data-act="add-s"][data-p="services.0.inclus"]')
    set_field(p, f'.item[data-lp="services.0"] input[data-path="services.0.inclus.{n0}"]', "Nouveau point inclus")
    assert draft(p)["services"][0]["inclus"][-1] == "Nouveau point inclus"
    p.click(f'.item[data-lp="services.0"] [data-act="del-s"][data-p="services.0.inclus"][data-i="{n0}"]')
    assert len(draft(p)["services"][0]["inclus"]) == n0


def test_before_after_pair_needs_both_photos_to_publish(adm):
    p = adm.page
    open_panel(p, "resultats")
    p.click('#pb_resultats [data-act="add"][data-p="avantApres"]')
    p.wait_for_selector('.item[data-lp="avantApres.0"]')
    p.click("#zipBtn")
    wait_for(lambda: "photo" in p.inner_text("#toast").lower() or "corriger" in p.inner_text("#toast").lower())
    assert not p.evaluate("document.getElementById('dlgDiff').open")


def test_published_pack_keeps_ids_and_order(adm, tmp_path):
    p = adm.page
    n = add_item(p, "faq", "faq", [("q", "Question ajoutée ?"), ("a", "Réponse ajoutée.")])
    p.click(f'#pb_faq [data-act="mv"][data-p="faq"][data-i="{n}"][data-d="-1"]')
    p.wait_for_timeout(900)
    z = download_pack(p, tmp_path)
    c = read_zip_json(z)
    assert c["faq"][n - 1]["q"] == "Question ajoutée ?"
    assert all(x.get("_id") for x in c["faq"]) and len({x["_id"] for x in c["faq"]}) == len(c["faq"])
