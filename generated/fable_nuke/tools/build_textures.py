# Original procedural 512x512 palette for fable_nuke (no external art).
from PIL import Image, ImageDraw
import os, random
out = os.path.join(os.path.dirname(__file__), "..", "main", "textures", "fable_nuke")
random.seed(41)
def noise(img, amt):
    px = img.load()
    for y in range(512):
        for x in range(512):
            n = random.randint(-amt, amt)
            r, g, b = px[x, y][:3]
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n))) + px[x, y][3:]
def save(img, name):
    img.save(os.path.join(out, name + ".tga"))
def flat(rgb, amt=6):
    img = Image.new("RGB", (512, 512), rgb); noise(img, amt); return img
def vstripe(base, stripe, period, width):
    img = Image.new("RGB", (512, 512), base); d = ImageDraw.Draw(img)
    for x in range(0, 512, period): d.rectangle([x, 0, x + width, 511], fill=stripe)
    noise(img, 4); return img
save(flat((168, 166, 160)), "concrete_wall")
save(flat((196, 196, 190)), "painted_wall")
save(flat((138, 138, 134), 8), "concrete_floor")
save(flat((120, 120, 118)), "concrete_trim")
save(vstripe((150, 155, 160), (135, 141, 148), 16, 7), "corrugated")
save(flat((105, 108, 112)), "metal_trim")
save(flat((88, 88, 90), 9), "asphalt")
save(flat((124, 116, 100), 12), "gravel")
save(flat((96, 118, 70), 10), "grass")
g = Image.new("RGBA", (512, 512), (0, 0, 0, 0)); d = ImageDraw.Draw(g)
for i in range(-512, 512, 32):
    d.line([(i, 0), (i + 512, 512)], fill=(150, 152, 155, 255), width=3)
    d.line([(i + 512, 0), (i, 512)], fill=(150, 152, 155, 255), width=3)
save(g, "chainlink")
gl = Image.new("RGBA", (512, 512), (170, 190, 205, 90)); save(gl, "glass")
print("wrote", len(os.listdir(out)), "textures")
