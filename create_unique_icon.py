import os
import math
import shutil
from PIL import Image, ImageDraw

def create_unique_app_icon(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = int(size * 0.08)
    corner = int(size * 0.22)
    
    # 1. Base squircle with rich midnight violet gradient background
    # Drawing concentric layers for subtle border glow
    draw.rounded_rectangle([pad - 4, pad - 4, size - pad + 4, size - pad + 4], radius=corner + 4, fill=(124, 58, 237, 80)) # Violet glow
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=corner, fill=(15, 10, 30, 255), outline=(139, 92, 246, 220), width=int(size * 0.015))

    cx, cy = size // 2, size // 2
    r_outer = int(size * 0.36)

    # 2. Outer segmented tech dial with ticks
    dial_color = (139, 92, 246, 180) # Neon violet
    cyan_color = (6, 182, 212, 255)  # Electric cyan
    coral_color = (244, 63, 94, 255) # Hot coral
    gold_color = (251, 191, 36, 255) # Amber gold

    # Circular segmented track
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], outline=(124, 58, 237, 100), width=max(2, int(size * 0.008)))
    
    # 24 radial calibration ticks
    for i in range(24):
        angle = (i * 15) * math.pi / 180.0
        tick_len = int(size * 0.035) if (i % 3 == 0) else int(size * 0.018)
        color = cyan_color if (i % 6 == 0) else (147, 197, 253, 140)
        thick = max(2, int(size * 0.008)) if (i % 6 == 0) else max(1, int(size * 0.004))
        
        x1 = cx + int((r_outer - tick_len) * math.cos(angle))
        y1 = cy + int((r_outer - tick_len) * math.sin(angle))
        x2 = cx + int(r_outer * math.cos(angle))
        y2 = cy + int(r_outer * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=color, width=thick)

    # 3. Inner high-precision cyan targeting ring
    r_mid = int(r_outer * 0.68)
    draw.ellipse([cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid], outline=(6, 182, 212, 160), width=max(2, int(size * 0.010)))

    # 4. Angled telemetry crosshair brackets (4 corner brackets)
    bracket_r = int(r_mid * 1.12)
    b_len = int(size * 0.05)
    for angle_deg in [45, 135, 225, 315]:
        rad = angle_deg * math.pi / 180.0
        bx = cx + int(bracket_r * math.cos(rad))
        by = cy + int(bracket_r * math.sin(rad))
        # Draw small reticle corner
        draw.line([bx - b_len, by, bx + b_len, by], fill=coral_color, width=max(2, int(size * 0.006)))
        draw.line([bx, by - b_len, bx, by + b_len], fill=coral_color, width=max(2, int(size * 0.006)))

    # 5. Central glowing optical diamond / beacon core
    d_size = int(size * 0.12)
    diamond_poly = [
        (cx, cy - d_size),
        (cx + d_size, cy),
        (cx, cy + d_size),
        (cx - d_size, cy)
    ]
    # Outer glow of diamond
    draw.polygon(diamond_poly, fill=(244, 63, 94, 210), outline=(255, 255, 255, 255))
    
    # Inner nested diamond
    d_inner = int(d_size * 0.55)
    diamond_inner = [
        (cx, cy - d_inner),
        (cx + d_inner, cy),
        (cx, cy + d_inner),
        (cx - d_inner, cy)
    ]
    draw.polygon(diamond_inner, fill=(251, 191, 36, 255))

    # Center pulse pinpoint
    center_p = max(3, int(size * 0.02))
    draw.ellipse([cx - center_p, cy - center_p, cx + center_p, cy + center_p], fill=(255, 255, 255, 255))

    # 6. High-value target telemetry satellites (Hot Coral & Electric Cyan)
    satellites = [
        (cx + int(r_outer * 0.50), cy - int(r_outer * 0.55), cyan_color, "L6"),
        (cx - int(r_outer * 0.45), cy + int(r_outer * 0.40), gold_color, "FAANG"),
        (cx + int(r_outer * 0.35), cy + int(r_outer * 0.50), coral_color, "100"),
    ]
    for sx, sy, col, label in satellites:
        sr = int(size * 0.032)
        # Glow halo
        draw.ellipse([sx - sr*2, sy - sr*2, sx + sr*2, sy + sr*2], fill=(col[0], col[1], col[2], 60))
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=col, outline=(255, 255, 255, 220), width=max(1, int(size * 0.004)))

    return img

iconset_dir = "career_radar_v4.iconset"
if os.path.exists(iconset_dir):
    shutil.rmtree(iconset_dir)
os.makedirs(iconset_dir, exist_ok=True)

base_img = create_unique_app_icon(1024)

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
    resized.save(os.path.join(iconset_dir, filename))

print("Created new unique iconset successfully")

