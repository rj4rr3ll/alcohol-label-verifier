from PIL import Image, ImageDraw, ImageFont
import textwrap
from pathlib import Path

output_dir = Path("sample_data/labels")
output_dir.mkdir(parents=True, exist_ok=True)

image = Image.new("RGB", (1800, 1200), "white")
draw = ImageDraw.Draw(image)

try:
    title_font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 72)
    main_font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 48)
    warning_font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 38)
except:
    title_font = ImageFont.load_default()
    main_font = ImageFont.load_default()
    warning_font = ImageFont.load_default()

y = 80

draw.text((100, y), "OLD TOM DISTILLERY", fill="black", font=title_font)
y += 130

draw.text((100, y), "Kentucky Straight Bourbon Whiskey", fill="black", font=main_font)
y += 90

draw.text((100, y), "45% Alc./Vol. (90 Proof)", fill="black", font=main_font)
y += 80

draw.text((100, y), "750 mL", fill="black", font=main_font)
y += 110

warning = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

wrapped_warning = textwrap.wrap(warning, width=72)

for line in wrapped_warning:
    draw.text((100, y), line, fill="black", font=warning_font)
    y += 55

output_path = output_dir / "old_tom_test_label.png"
image.save(output_path)

print(f"Created sample label: {output_path}")