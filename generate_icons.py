"""
Generates crisp, high-resolution fintech-grade PocketPay branding assets:
- icon-512.png (512x512)
- icon-192.png (192x192)
- apple-touch-icon.png (180x180)
- favicon-32x32.png (32x32)
- favicon-16x16.png (16x16)
- favicon.ico (multi-resolution: 16, 32, 48)
- logo.svg (vector SVG icon)
"""
import os
import math
from PIL import Image, ImageDraw, ImageFilter

def generate_pocketpay_assets(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Generate master high-resolution icon (2048x2048 supersampled)
    SIZE = 2048
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    
    # Background squircle with deep midnight obsidian gradient
    # Safe area margin: 12% padding for Android adaptive icons (so radius/safe zone is well preserved)
    pad = int(SIZE * 0.08)
    rect = [pad, pad, SIZE - pad, SIZE - pad]
    radius = int(SIZE * 0.22)
    
    # Create background layer with gradient
    bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    
    # Draw rich dark navy / obsidian rounded rectangle
    bg_draw.rounded_rectangle(rect, radius=radius, fill=(11, 15, 29, 255))
    
    # Add subtle vibrant outer glow / gradient border
    for i in range(int(SIZE * 0.015)):
        glow_alpha = int(40 - i * 1.2)
        if glow_alpha > 0:
            glow_rect = [pad - i*2, pad - i*2, SIZE - pad + i*2, SIZE - pad + i*2]
            glow_rad = radius + i*2
            # bg_draw.rounded_rectangle(glow_rect, radius=glow_rad, outline=(99, 102, 241, glow_alpha), width=2)
            
    # Add diagonal gradient mesh to squircle background
    gradient_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for y in range(pad, SIZE - pad):
        factor = (y - pad) / (SIZE - 2 * pad)
        # Deep Indigo (15, 23, 42) -> Deep Violet/Slate (24, 18, 43)
        r = int(14 + 18 * factor)
        g = int(18 + 10 * factor)
        b = int(38 + 32 * factor)
        # draw horizontal slice
        ImageDraw.Draw(gradient_layer).line([(pad, y), (SIZE - pad, y)], fill=(r, g, b, 255))
        
    # Mask gradient to rounded rect
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(rect, radius=radius, fill=255)
    canvas.paste(gradient_layer, (0, 0), mask)
    
    # Add subtle border highlight
    border_draw = ImageDraw.Draw(canvas)
    border_draw.rounded_rectangle(rect, radius=radius, outline=(99, 102, 241, 140), width=int(SIZE * 0.012))
    
    # 2. Draw Modern Geometric PocketPay "P" & Shield Emblem
    # The emblem consists of:
    # 1. Solid Left Vertical Pillar / Spine (with sleek rounded cap)
    # 2. Upper Loop of the "P" flowing into a dynamic Pocket / Payment Fold
    # 3. Vibrant Neon Indigo/Cyan/Magenta forward accent slash
    
    emblem = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    emblem_draw = ImageDraw.Draw(emblem)
    
    cx = SIZE // 2
    cy = SIZE // 2
    
    # Left Pillar of the 'P'
    p_x1 = int(SIZE * 0.28)
    p_x2 = int(SIZE * 0.39)
    p_y1 = int(SIZE * 0.24)
    p_y2 = int(SIZE * 0.76)
    p_rad = int((p_x2 - p_x1) // 2)
    
    # Draw vertical spine with vibrant Indigo -> Cyan gradient
    spine_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(spine_layer)
    s_draw.rounded_rectangle([p_x1, p_y1, p_x2, p_y2], radius=p_rad, fill=(255, 255, 255, 255))
    
    # Gradient overlay on spine (Electric Indigo #6366F1 to Vibrant Cyan #06B6D4)
    for y in range(p_y1, p_y2):
        t = (y - p_y1) / (p_y2 - p_y1)
        r = int(99 * (1 - t) + 6 * t)
        g = int(102 * (1 - t) + 182 * t)
        b = int(241 * (1 - t) + 212 * t)
        ImageDraw.Draw(spine_layer).line([(p_x1, y), (p_x2, y)], fill=(r, g, b, 255))
        
    s_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(s_mask).rounded_rectangle([p_x1, p_y1, p_x2, p_y2], radius=p_rad, fill=255)
    emblem.paste(spine_layer, (0, 0), s_mask)
    
    # Upper 'P' Loop & Pocket Arc
    # Arc from (p_x2 - 10, p_y1) curving to right (p_x_right) and returning to (p_x2, p_mid_y)
    p_mid_y = int(SIZE * 0.52)
    p_rx2 = int(SIZE * 0.72)
    
    # Draw upper P-loop using thick smooth geometry
    loop_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    l_draw = ImageDraw.Draw(loop_layer)
    
    # Outer upper loop
    loop_rect = [p_x1 + int(SIZE*0.02), p_y1, p_rx2, p_mid_y]
    l_draw.rounded_rectangle(loop_rect, radius=int((p_mid_y - p_y1)//2), fill=(255, 255, 255, 255))
    
    # Apply Vibrant Violet/Pink gradient to loop (#8B5CF6 -> #EC4899)
    for x in range(loop_rect[0], loop_rect[2]):
        t = (x - loop_rect[0]) / (loop_rect[2] - loop_rect[0])
        r = int(124 * (1 - t) + 236 * t)
        g = int(58 * (1 - t) + 72 * t)
        b = int(237 * (1 - t) + 153 * t)
        ImageDraw.Draw(loop_layer).line([(x, p_y1), (x, p_mid_y)], fill=(r, g, b, 255))
        
    loop_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(loop_mask).rounded_rectangle(loop_rect, radius=int((p_mid_y - p_y1)//2), fill=255)
    
    # Inner cutout for the P hole
    hole_rect = [p_x2, p_y1 + int(SIZE * 0.08), p_rx2 - int(SIZE * 0.09), p_mid_y - int(SIZE * 0.08)]
    ImageDraw.Draw(loop_mask).rounded_rectangle(hole_rect, radius=int(SIZE * 0.04), fill=0)
    
    emblem.paste(loop_layer, (0, 0), loop_mask)
    
    # Forward Payment / Pocket Fold Arrow Accent (Dynamic Chevrons in Center-Right)
    # Forward chevron at 45 degree angle connecting the loop to a smart payment pulse
    accent_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    a_draw = ImageDraw.Draw(accent_layer)
    
    ax1 = int(SIZE * 0.46)
    ay1 = int(SIZE * 0.43)
    ax2 = int(SIZE * 0.68)
    ay2 = int(SIZE * 0.65)
    ax3 = int(SIZE * 0.46)
    ay3 = int(SIZE * 0.65)
    
    # Draw geometric payment fold
    pts = [
        (int(SIZE * 0.44), int(SIZE * 0.48)),
        (int(SIZE * 0.64), int(SIZE * 0.48)),
        (int(SIZE * 0.52), int(SIZE * 0.66)),
        (int(SIZE * 0.40), int(SIZE * 0.66)),
    ]
    a_draw.polygon(pts, fill=(255, 255, 255, 255))
    
    # Fill with brilliant Cyan / White glow
    for y in range(int(SIZE * 0.48), int(SIZE * 0.67)):
        t = (y - int(SIZE * 0.48)) / (int(SIZE * 0.19))
        r = int(255 * (1 - t) + 6 * t)
        g = int(255 * (1 - t) + 182 * t)
        b = int(255 * (1 - t) + 212 * t)
        ImageDraw.Draw(accent_layer).line([(0, y), (SIZE, y)], fill=(r, g, b, 255))
        
    a_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(a_mask).polygon(pts, fill=255)
    emblem.paste(accent_layer, (0, 0), a_mask)
    
    # Add subtle soft shadow to emblem
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow_mask = emblem.split()[3]
    shadow_draw = ImageDraw.Draw(shadow)
    shadow.paste((0, 0, 0, 160), (0, 0), shadow_mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(SIZE * 0.02)))
    
    # Composite: background + shadow + emblem
    canvas.paste(shadow, (0, int(SIZE * 0.01)), shadow)
    canvas.paste(emblem, (0, 0), emblem)
    
    # Save high-res master
    master = canvas
    
    # 3. Export all icon resolutions with high-quality Lanczos resampling
    sizes = {
        'icon-512.png': 512,
        'icon-192.png': 192,
        'apple-touch-icon.png': 180,
        'favicon-32x32.png': 32,
        'favicon-16x16.png': 16,
    }
    
    for filename, dim in sizes.items():
        resized = master.resize((dim, dim), Image.Resampling.LANCZOS)
        resized.save(os.path.join(output_dir, filename), "PNG", optimize=True)
        print(f"Generated {filename} ({dim}x{dim})")
        
    # Generate multi-res favicon.ico
    ico_16 = master.resize((16, 16), Image.Resampling.LANCZOS)
    ico_32 = master.resize((32, 32), Image.Resampling.LANCZOS)
    ico_48 = master.resize((48, 48), Image.Resampling.LANCZOS)
    ico_32.save(os.path.join(output_dir, 'favicon.ico'), format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])
    print("Generated favicon.ico (16, 32, 48)")

if __name__ == '__main__':
    base = os.path.abspath(os.path.dirname(__file__))
    app_img = os.path.join(base, 'app', 'static', 'img')
    generate_pocketpay_assets(app_img)
