import os
import math
from PIL import Image, ImageDraw

def create_radar_image(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Base rounded dark square (macOS squircle style)
    pad = int(size * 0.08)
    corner = int(size * 0.22)
    # Background gradient or dark slate color #0f172a
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=corner, fill=(15, 23, 42, 255), outline=(51, 65, 85, 255), width=int(size * 0.015))

    cx, cy = size // 2, size // 2
    r_max = int(size * 0.36)

    # Concentric rings
    ring_color = (16, 185, 129, 90) # Emerald/teal with alpha
    ring_thick = max(2, int(size * 0.012))
    for step in [0.25, 0.5, 0.75, 1.0]:
        r = int(r_max * step)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(16, 185, 129, int(70 + step * 80)), width=ring_thick)

    # Crosshairs
    draw.line([cx - r_max, cy, cx + r_max, cy], fill=(16, 185, 129, 120), width=ring_thick)
    draw.line([cx, cy - r_max, cx, cy + r_max], fill=(16, 185, 129, 120), width=ring_thick)

    # Radar sweep slice
    # Draw arc wedges simulating a rotating sweep
    for deg in range(0, 55):
        alpha = int(140 * (1.0 - (deg / 55.0)))
        draw.arc([cx - r_max, cy - r_max, cx + r_max, cy + r_max], start=210 - deg, end=212 - deg, fill=(52, 211, 153, alpha), width=int(r_max))

    # Center target blip
    center_r = int(size * 0.035)
    draw.ellipse([cx - center_r, cy - center_r, cx + center_r, cy + center_r], fill=(16, 185, 129, 255))
    
    # Target blips (representing high-fit jobs detected)
    blips = [
        (cx + int(r_max * 0.55), cy - int(r_max * 0.45), (56, 189, 248, 255)), # Sky blue
        (cx - int(r_max * 0.40), cy - int(r_max * 0.50), (251, 191, 36, 255)), # Amber (FAANG)
        (cx + int(r_max * 0.60), cy + int(r_max * 0.35), (168, 85, 247, 255)), # Purple
    ]
    for bx, by, color in blips:
        br = int(size * 0.028)
        # Pulse halo
        draw.ellipse([bx - br*2, by - br*2, bx + br*2, by + br*2], fill=(color[0], color[1], color[2], 60))
        draw.ellipse([bx - br, by - br, bx + br, by + br], fill=color)

    return img

os.makedirs("radar.iconset", exist_ok=True)
base_img = create_radar_image(1024)

icon_specs = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

for dim, filename in icon_specs:
    resized = base_img.resize((dim, dim), Image.Resampling.LANCZOS)
    resized.save(os.path.join("radar.iconset", filename))

print("Created radar.iconset files successfully")

