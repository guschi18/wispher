"""Zeichnet das Wispher-Icon (warmer Verlauf, Mikrofon) -> assets/icon.png + icon.ico."""
from PIL import Image, ImageDraw

S = 1024
grad = Image.composite(Image.new("RGB", (S, S), (255, 106, 61)), Image.new("RGB", (S, S), (255, 188, 99)),
                       Image.linear_gradient("L").resize((S, S)).rotate(45, expand=False))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((90, 90, 934, 934), 220, fill=255)
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
im.paste(grad, mask=mask)
d, C, w = ImageDraw.Draw(im), (255, 246, 234), 44
d.rounded_rectangle((392, 220, 632, 560), 120, fill=C)                 # Kapsel
d.arc((312, 340, 712, 700), 0, 180, fill=C, width=w)                    # Bügel
d.line((512, 700, 512, 790), fill=C, width=w)
d.rounded_rectangle((402, 770, 622, 814), 22, fill=C)                   # Fuß
im.save("assets/icon.png")
im.save("assets/icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
