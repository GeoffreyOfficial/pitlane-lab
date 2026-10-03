"""Formulaire de devis, estimateur de prix et canaux de contact."""
import json
import math
import re
import urllib.parse

import pytest

from helpers import last_send, open_site, scroll_to, wait_for

pytestmark = pytest.mark.site
SPY_OPEN = "window.open=(...a)=>{window.__opened=a;return null}"   # évite d'ouvrir de vrais onglets WhatsApp


def contact_page(make_page, site, *, w=1280, h=900, mobile=False, content_fn=None, reduced=True, extra_routes=()):
    hd = make_page(site, w=w, h=h, mobile=mobile, content_fn=content_fn, reduced_motion=reduced, init_scripts=[SPY_OPEN], extra_routes=extra_routes)
    open_site(hd, site)
    scroll_to(hd.page, "#quote", "start")
    return hd


def fill(p, **kw):
    ids = {"nom": "#f-nom", "tel": "#f-tel", "mail": "#f-mail", "ville": "#f-ville", "veh": "#f-veh", "date": "#f-date", "msg": "#f-msg"}
    for k, v in kw.items():
        p.fill(ids[k], v)


def errors(p):
    return {i: p.inner_text(f"#{i} ~ .err").strip() for i in ("f-nom", "f-tel", "f-mail", "f-veh") if p.inner_text(f"#{i} ~ .err").strip()}


def tick(p, name, value):
    """Coche une option de l'estimateur (les cases sont stylisées : on clique l'élément lui-même)."""
    p.evaluate("([n,v])=>document.querySelector('#est input[name=\"'+n+'\"][value=\"'+v+'\"]').click()", [name, str(value)])


def send(p, kind="wa"):
    p.click(f'[data-send="{kind}"]')


def price(s):
    return float(re.search(r"[\d.,]+", s).group().replace(",", "."))


def expected(content, idx, size, etat):
    E = content["estimateur"]
    sc, ec = float(E["tailles"][size]["coef"]), float(E["etats"][etat]["coef"])
    return sum(math.floor(price(content["services"][i]["prix"]) * sc * ec / 5 + .5) * 5 for i in idx)


# ------------------------------------------------------------------ accessibilité
def test_every_field_has_a_label_and_good_mobile_size(make_page, site):
    hd = contact_page(make_page, site, w=320, h=568, mobile=True)
    p = hd.page
    res = p.evaluate("""[...document.querySelectorAll('#quote input:not([type=hidden]):not([type=radio]):not([type=checkbox]),#quote select,#quote textarea')].filter(e=>!e.closest('.hp')).map(e=>{
        const l=e.id&&document.querySelector('label[for="'+e.id+'"]'); const r=e.getBoundingClientRect();
        return {id:e.id||e.name,label:!!l,h:Math.round(r.height),fs:parseFloat(getComputedStyle(e).fontSize)}})""")
    assert len(res) >= 8
    for r in res:
        assert r["label"], f"champ sans étiquette : {r['id']}"
        assert r["h"] >= 44 or r["id"] == "f-msg", f"champ trop petit pour le doigt ({r['h']}px) : {r['id']}"
        assert r["fs"] >= 16, f"police < 16px : le navigateur iPhone zoomera sur {r['id']}"
    assert p.evaluate("document.documentElement.scrollWidth") <= 320


def test_radios_are_grouped_and_keyboard_operable(make_page, site):
    hd = contact_page(make_page, site)
    p = hd.page
    assert p.locator('#est [role="radiogroup"]').count() == 2
    first = p.evaluate("document.querySelector('#est input[name=taille]:checked').value")
    p.focus('#est input[name=taille]:checked')
    p.keyboard.press("ArrowRight")
    assert p.evaluate("document.querySelector('#est input[name=taille]:checked').value") != first


# ------------------------------------------------------------------ validation
CASES = [
    ("vide", {}, {"f-nom", "f-veh"}),
    ("sans contact", {"nom": "Karim", "veh": "BMW M2"}, {"f-tel"}),
    ("téléphone court", {"nom": "Karim", "veh": "BMW M2", "tel": "0612"}, {"f-tel"}),
    ("e-mail invalide", {"nom": "Karim", "veh": "BMW M2", "mail": "karim@"}, {"f-mail"}),
    ("nom en espaces", {"nom": "   ", "veh": "BMW M2", "tel": "0612345678"}, {"f-nom"}),
    ("tout invalide", {"nom": "", "veh": "", "tel": "12", "mail": "x"}, {"f-nom", "f-veh", "f-tel", "f-mail"}),
]


@pytest.mark.parametrize("label,data,expected_err", CASES, ids=[c[0] for c in CASES])
def test_validation_messages(make_page, site, label, data, expected_err):
    hd = contact_page(make_page, site)
    p = hd.page
    fill(p, **data)
    send(p, "wa")
    assert set(errors(p)) == expected_err, f"{label} : {errors(p)}"
    assert last_send(p) is None, "rien ne doit être envoyé quand le formulaire est invalide"
    first = p.evaluate("document.querySelector('#quote [aria-invalid=\"true\"]').id")   # premier champ invalide dans l'ordre de la page
    assert p.evaluate("document.activeElement.id") == first, "le focus doit aller au premier champ en erreur"
    for i in expected_err:
        assert p.get_attribute(f"#{i}", "aria-invalid") == "true"


def test_errors_clear_once_fixed(make_page, site):
    hd = contact_page(make_page, site)
    p = hd.page
    send(p)
    assert errors(p)
    fill(p, nom="Karim", veh="BMW M2", tel="07 68 70 69 96")
    send(p)
    assert not errors(p)
    assert last_send(p)["kind"] == "wa"


# ------------------------------------------------------------------ contenu des messages
def test_whatsapp_message_is_complete(make_page, site):
    hd = contact_page(make_page, site)
    p = hd.page
    fill(p, nom="Karim B.", veh="BMW M2 2021", tel="07 68 70 69 96", mail="karim@example.com", ville="Limay", msg="Rayures sur le capot")
    tick(p, "svc", 3)
    p.select_option("#f-moment", "Matin")
    send(p, "wa")
    s = last_send(p)
    assert s["kind"] == "wa" and s["url"].startswith("https://wa.me/33768706996?text=")
    msg = urllib.parse.unquote(s["url"].split("text=")[1])
    assert msg == s["message"]
    for needle in ["Jermaine", "BMW M2 2021", "Commune : Limay", "Rayures sur le capot", "Nom : Karim B.", "Téléphone : 07 68 70 69 96", "E-mail : karim@example.com", "Estimation : environ", "moment souhaité : matin"]:
        assert needle.lower() in msg.lower(), f"« {needle} » absent du message :\n{msg}"
    assert re.search(r"- .+ : \d+", msg), "ligne de prestation attendue"
    assert p.evaluate("window.__opened[0].startsWith('https://wa.me/')")
    assert "WhatsApp" in p.inner_text("#formOk")


def test_mail_message_and_subject(make_page, site):
    hd = contact_page(make_page, site)
    p = hd.page
    fill(p, nom="Léa", veh="Audi RS3", mail="lea@example.com")
    send(p, "mail")
    s = last_send(p)
    assert s["kind"] == "mail" and s["url"].startswith("mailto:contact@pitlanelab.fr?subject=")
    assert "Audi RS3" in urllib.parse.unquote(s["url"].split("subject=")[1].split("&")[0])
    assert "Léa" in urllib.parse.unquote(s["url"].split("body=")[1])
    assert "e-mail" in p.inner_text("#formOk").lower()


def test_special_characters_survive_encoding(make_page, site):
    hd = contact_page(make_page, site)
    p = hd.page
    weird = 'Peugeot 208 & "GTi" <b>é€ñ</b> 日本 😀\nligne 2'
    fill(p, nom="Zoé & Co", veh=weird, tel="0768706996", msg="a=b&c=d?e#f")
    send(p, "wa")
    msg = urllib.parse.unquote(last_send(p)["url"].split("text=")[1])
    assert "Peugeot 208 & \"GTi\" <b>é€ñ</b> 日本 😀" in msg and "a=b&c=d?e#f" in msg
    assert p.evaluate("document.querySelectorAll('#formOk b').length") <= 1, "le HTML saisi ne doit jamais être interprété"


def test_honeypot_blocks_bots(make_page, site):
    hd = contact_page(make_page, site)
    p = hd.page
    fill(p, nom="Bot", veh="X", tel="0768706996")
    p.evaluate("document.querySelector('input[name=website]').value='http://spam'")
    send(p)
    assert last_send(p) is None and not p.evaluate("document.getElementById('formOk').classList.contains('show')")


def test_form_fields_are_remembered_during_the_visit(make_page, site):
    hd = contact_page(make_page, site)
    p = hd.page
    fill(p, nom="Karim", veh="BMW M2", tel="0768706996", msg="Bonjour")
    p.reload()
    p.wait_for_selector("#quote", state="attached")
    assert p.input_value("#f-nom") == "Karim" and p.input_value("#f-msg") == "Bonjour"


# ------------------------------------------------------------------ estimateur
def test_estimator_matches_formula(make_page, site):
    content = site.content()
    E = content["estimateur"]
    hd = contact_page(make_page, site)
    p = hd.page
    assert p.inner_text("#estN").strip() == "—"
    combos = [([0], 0, 0), ([2], 1, 0), ([3], 2, 1), ([0, 2, 4], 1, 1), ([5], 0, len(E["etats"]) - 1)]
    for idx, size, etat in combos:
        p.evaluate("[...document.querySelectorAll('#est input[name=svc]:checked')].forEach(e=>e.click())")
        p.evaluate(f"document.querySelector('#est input[name=taille][value=\"{size}\"]').click()")
        p.evaluate(f"document.querySelector('#est input[name=etat][value=\"{etat}\"]').click()")
        for i in idx:
            p.evaluate(f"document.querySelector('#est input[name=svc][value=\"{i}\"]').click()")
        want = expected(content, idx, size, etat)
        wait_for(lambda: int(re.sub(r"\D", "", p.inner_text("#estN")) or -1) == want, msg=f"estimation attendue {want} pour {idx}/{size}/{etat}")
        assert str(want)[0] in p.inner_text("#estN")
    assert "indicative" in p.inner_text("#estD").lower() or E["note"][:12] in p.inner_text("#estD")


def test_estimator_unknown_price_and_empty_selection(make_page, site):
    def unknown(c):
        c["services"][0]["prix"] = "sur devis"
        return c
    hd = contact_page(make_page, site, content_fn=unknown)
    p = hd.page
    p.evaluate("document.querySelector('#est input[name=svc][value=\"0\"]').click()")
    wait_for(lambda: "devis" in p.inner_text("#estN").lower())
    p.evaluate("document.querySelector('#est input[name=svc][value=\"0\"]').click()")
    wait_for(lambda: p.inner_text("#estN").strip() == "—")
    assert "Choisissez" in p.inner_text("#estD")


def test_estimator_disabled_falls_back_to_a_select(make_page, site):
    def off(c):
        c["estimateur"]["actif"] = False
        return c
    hd = contact_page(make_page, site, content_fn=off)
    p = hd.page
    assert p.locator("#est").count() == 0 and p.locator("#f-presta").count() == 1
    title = site.content()["services"][1]["titre"]
    p.select_option("#f-presta", title)
    fill(p, nom="Karim", veh="BMW", tel="0768706996")
    send(p)
    assert title in last_send(p)["message"]


def test_estimator_is_included_in_message_with_labels(make_page, site):
    content = site.content()
    hd = contact_page(make_page, site)
    p = hd.page
    p.evaluate("document.querySelector('#est input[name=svc][value=\"2\"]').click()")
    p.evaluate("document.querySelector('#est input[name=taille][value=\"2\"]').click()")
    fill(p, nom="Karim", veh="BMW", tel="0768706996")
    send(p)
    msg = last_send(p)["message"]
    assert content["estimateur"]["tailles"][2]["label"] in msg
    assert str(expected(content, [2], 2, 0)) in msg


# ------------------------------------------------------------------ envoi direct (POST)
def endpoint_content(c):
    c["contact"]["formEndpoint"] = "https://forms.test/submit"
    return c


def test_direct_send_success(make_page, site):
    seen = {}

    def ok(route):
        seen["body"] = route.request.post_data or ""
        seen["method"] = route.request.method
        route.fulfill(status=200, body="{}", content_type="application/json")
    hd = contact_page(make_page, site, content_fn=endpoint_content, extra_routes=[("forms.test", ok)])
    p = hd.page
    assert p.locator('#quote button[type=submit]').count() == 1
    fill(p, nom="Karim", veh="BMW M2", tel="0768706996", msg="Bonjour")
    p.click("#quote button[type=submit]")
    wait_for(lambda: "Demande envoyée" in p.inner_text("#formOk"))
    assert seen["method"] == "POST" and "recapitulatif" in seen["body"] and "Karim" in seen["body"]
    assert p.input_value("#f-nom") == "", "le formulaire doit se vider après l'envoi"
    assert not p.is_disabled("#quote button[type=submit]")


def test_direct_send_failure_keeps_data(make_page, site):
    hd = contact_page(make_page, site, content_fn=endpoint_content, extra_routes=[("forms.test", lambda r: r.fulfill(status=500, body="boom"))])
    p = hd.page
    fill(p, nom="Karim", veh="BMW M2", tel="0768706996", msg="Bonjour")
    p.click("#quote button[type=submit]")
    wait_for(lambda: "échoué" in p.inner_text("#formOk"))
    assert p.input_value("#f-nom") == "Karim" and p.input_value("#f-msg") == "Bonjour", "les données saisies ne doivent pas être perdues"
    assert not p.is_disabled("#quote button[type=submit]"), "le bouton doit se réactiver pour réessayer"


def test_direct_send_validates_first(make_page, site):
    calls = []
    hd = contact_page(make_page, site, content_fn=endpoint_content, extra_routes=[("forms.test", lambda r: (calls.append(1), r.fulfill(status=200, body="{}"))[1])])
    p = hd.page
    p.click("#quote button[type=submit]")
    assert errors(p) and not calls


# ------------------------------------------------------------------ canaux de contact
@pytest.mark.parametrize("variant", ["both", "email_only", "wa_only", "none"])
def test_available_send_buttons_follow_contact_data(make_page, site, variant):
    def change(c):
        ct = c["contact"]
        if variant == "email_only":
            ct["telephone"] = ""
        elif variant == "wa_only":
            ct["email"] = ""
        elif variant == "none":
            ct["telephone"] = ct["email"] = ct["whatsapp"] = ""
        return c
    hd = contact_page(make_page, site, content_fn=change)
    p = hd.page
    wa, mail = p.locator('[data-send="wa"]').count(), p.locator('[data-send="mail"]').count()
    assert (wa, mail) == {"both": (1, 1), "email_only": (0, 1), "wa_only": (1, 0), "none": (0, 0)}[variant]
    assert not hd.errors


def test_contact_links_are_correct(make_page, site):
    def socials(c):
        c["contact"].update({"instagram": "https://www.instagram.com/pitlanelab", "facebook": "", "tiktok": ""})
        return c
    hd = contact_page(make_page, site, content_fn=socials)
    p = hd.page
    hrefs = p.evaluate("[...document.querySelectorAll('#contact .ch, #contact .socials a')].map(a=>a.getAttribute('href')).filter(Boolean)")
    assert "tel:+33768706996" in hrefs and "https://wa.me/33768706996" in hrefs and "mailto:contact@pitlanelab.fr" in hrefs
    assert p.locator("#contact .socials a").count() == 1 and "instagram" in hrefs[-1]
    for a in p.locator("#contact a[target=_blank]").all():
        assert "noopener" in (a.get_attribute("rel") or ""), "lien externe sans rel=noopener"


def test_date_field_blocks_past_dates(make_page, site):
    hd = contact_page(make_page, site)
    mn = hd.page.get_attribute("#f-date", "min")
    import datetime
    assert mn == (datetime.date.today() + datetime.timedelta(days=1)).isoformat() or mn == (datetime.datetime.utcnow().date() + datetime.timedelta(days=1)).isoformat()
