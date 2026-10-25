import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W, H = 1280, 720
def F(sz, bold=True):
    for p in (["C:/Windows/Fonts/segoeuib.ttf"] if bold else ["C:/Windows/Fonts/segoeui.ttf"]) + ["C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()
NAVY, GOLD, WHITE = (15, 22, 36), (245, 197, 66), (238, 242, 248)

def gradient():
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; d.line([(0, y), (W, y)], fill=(int(15 + 14 * t), int(22 + 30 * t), int(36 + 50 * t)))
    return im

def shadow_paste(base, shot, xy, size, angle=0):
    shot = shot.resize(size, Image.LANCZOS).convert("RGB")
    mask = Image.new("L", size, 255); d = ImageDraw.Draw(mask); d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], 24, fill=255)
    sh = Image.new("RGBA", (size[0] + 60, size[1] + 60), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([30, 30, size[0] + 30, size[1] + 30], 24, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(18)); base.paste(sh, (xy[0] - 30, xy[1] - 20), sh)
    base.paste(shot, xy, mask)

def text_outline(d, xy, t, font, fill, ow=4):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow: d.text((x + dx, y + dy), t, font=font, fill=(0, 0, 0))
    d.text(xy, t, font=font, fill=fill)

# --- A: big text + app screenshot
a = gradient(); d = ImageDraw.Draw(a)
shot = Image.open("thumbs/_shot_demo.png")
shadow_paste(a, shot, (620, 190), (620, 349))
text_outline(d, (50, 70), "Freelance", F(104), WHITE); text_outline(d, (50, 180), "Ledger", F(104), GOLD)
text_outline(d, (56, 330), "PayPal + AI", F(60), WHITE); d.text((58, 410), "USD to INR, GST limit,", font=F(40, False), fill=(200, 212, 230)); d.text((58, 460), "e-FIRA tracking", font=F(40, False), fill=(200, 212, 230))
d.rounded_rectangle([50, 610, 470, 675], 14, fill=GOLD); d.text((78, 618), "PayPal AI Hackathon", font=F(38), fill=NAVY)
a.save("thumbs/thumb_A.png")

# --- B: the problem / number focus
b = gradient(); d = ImageDraw.Draw(b)
text_outline(d, (60, 50), "PAID IN USD?", F(112), WHITE)
text_outline(d, (60, 180), "Track it in", F(88), WHITE); text_outline(d, (60, 290), "INR", F(190), GOLD)
d.rounded_rectangle([60, 560, 620, 600], 20, fill=(39, 52, 79)); d.rounded_rectangle([60, 560, 60 + int(560 * 0.206), 600], 20, fill=(46, 139, 87))
d.text((60, 612), "GST threshold: 20.6% of Rs 20 lakh", font=F(34, False), fill=(200, 212, 230))
shadow_paste(b, Image.open("thumbs/_shot_demo.png"), (690, 300), (540, 304))
b.save("thumbs/thumb_B.png")

# --- C: clean typographic
c = gradient(); d = ImageDraw.Draw(c)
d.rectangle([0, 0, 24, H], fill=GOLD)
text_outline(d, (90, 120), "The freelancer's", F(88), WHITE); text_outline(d, (90, 225), "paperwork,", F(88), WHITE); text_outline(d, (90, 330), "solved.", F(150), GOLD)
d.text((94, 540), "PayPal sandbox  |  Gemini AI  |  AG Grid", font=F(40, False), fill=(200, 212, 230))
d.text((94, 600), "FreelanceLedger  -  open source", font=F(34, False), fill=(150, 166, 190))
c.save("thumbs/thumb_C.png")
for n in "ABC": print(n, os.path.getsize(f"thumbs/thumb_{n}.png") // 1024, "KB")
