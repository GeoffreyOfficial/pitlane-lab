"""Régénère les fichiers d'exemple de tests/fixtures (nécessite Pillow et pillow-heif).
Usage : python tests/make_fixtures.py
"""
import os
import pathlib
import random

from PIL import Image, ImageDraw
import pillow_heif

pillow_heif.register_heif_opener()
random.seed(5)
OUT = pathlib.Path(__file__).parent / "fixtures"
OUT.mkdir(exist_ok=True)
os.chdir(OUT)


def scene(w, h, alpha=False):
    im = Image.new("RGBA" if alpha else "RGB", (w, h), (0, 0, 0, 0) if alpha else (30, 40, 60))
    d = ImageDraw.Draw(im)
    for i in range(0, w, max(1, w // 20)):
        d.rectangle((i, 0, i + w // 40, h), fill=(200 - i % 150, 60 + i % 100, 90, 255))
    d.ellipse((w * .3, h * .3, w * .7, h * .8), fill=(240, 20, 40, 255))
    return im


im = scene(1200, 800); ex = im.getexif(); ex[0x0112] = 6; im.save("exif_rot6.jpg", quality=90, exif=ex)   # photo « prise en travers »
scene(1600, 1067).save("photo.jpg", quality=85); scene(900, 600, True).save("alpha.png"); scene(1000, 700).save("photo.webp", quality=80)
scene(400, 300).save("static.gif")
fr = [scene(200, 150).convert("P") for _ in range(3)]
for k, f in enumerate(fr):
    ImageDraw.Draw(f).rectangle((k * 40, 0, k * 40 + 30, 30), fill=1)
fr[0].save("animated.gif", save_all=True, append_images=fr[1:], duration=200, loop=0)
scene(500, 350).save("photo.bmp"); scene(480, 360).save("photo.tif", compression="tiff_deflate"); scene(800, 600).save("photo.avif", quality=60)
scene(1200, 900).save("photo.heic", quality=75); scene(128, 128, True).save("icon.ico", sizes=[(64, 64), (128, 128)])
open("vector.svg", "w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><script>alert(1)</script><rect width="400" height="300" fill="#222" onclick="alert(2)"/><circle cx="200" cy="150" r="90" fill="#e10a1e"/></svg>')
open("corrupt.jpg", "wb").write(open("photo.jpg", "rb").read()[:3000] + os.urandom(1500))
open("fake.jpg", "w").write("ceci est du texte, pas une image"); open("empty.png", "wb").close(); open("document.pdf", "wb").write(b"%PDF-1.4\n%fake\n")
q = Image.new("RGB", (400, 200)); d = ImageDraw.Draw(q)
d.rectangle((0, 0, 199, 99), fill=(255, 0, 0)); d.rectangle((200, 0, 399, 99), fill=(0, 255, 0)); d.rectangle((0, 100, 199, 199), fill=(0, 0, 255)); d.rectangle((200, 100, 399, 199), fill=(255, 255, 0))
q.save("quad.png")   # quatre quadrants de couleurs : sert à vérifier rotation, miroir et recadrage au pixel près
e = q.copy(); ex = e.getexif(); ex[0x010F] = "Marque"; ex[0x0110] = "Modele"; e.save("quad_exif.jpg", quality=95, exif=ex)
lg = Image.new("RGB", (800, 300), (255, 255, 255)); d = ImageDraw.Draw(lg); d.rectangle((100, 60, 700, 240), fill=(200, 20, 40)); d.rectangle((300, 110, 420, 190), fill=(255, 255, 255)); lg.save("logo_fond_blanc.jpg", quality=95)
sb = Image.new("RGBA", (1000, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(sb); d.ellipse((50, 40, 950, 170), outline=(0, 0, 0, 255), width=10); sb.save("silhouette_noire.png")
ic = Image.new("RGBA", (300, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(ic); d.ellipse((60, 60, 240, 240), fill=(255, 255, 255, 255)); ic.save("icone_transparente.png")
print("fichiers d'exemple régénérés dans", OUT)
