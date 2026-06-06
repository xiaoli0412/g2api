"""Generate extension icons."""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """Create a simple icon."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle
    margin = size // 8
    draw.ellipse([margin, margin, size - margin, size - margin], fill='#6366f1')
    
    # Letter G
    try:
        font_size = size // 2
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    text = "G"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - bbox[1]
    draw.text((x, y), text, fill='white', font=font)
    
    img.save(output_path)

# Create icons directory
os.makedirs('extension/icons', exist_ok=True)

# Generate icons
for size in [16, 32, 48, 128]:
    create_icon(size, f'extension/icons/icon{size}.png')
    print(f'Created icon{size}.png')

print('Done!')
