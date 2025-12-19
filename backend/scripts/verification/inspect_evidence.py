from pathlib import Path
from PIL import Image
import numpy as np
import sys

evidence_dir = Path("/home/fengning/.gemini/antigravity/brain/9112de99-6087-4677-88e8-ddcb9dc376f2/evidence")

print(f"{'Filename':<30} | {'Size(KB)':<10} | {'Mean Brightness':<15} | {'Unique Colors':<15}")
print("-" * 80)

for img_path in sorted(evidence_dir.glob("*.png")):
    try:
        img = Image.open(img_path)
        data = np.array(img)
        mean_brightness = np.mean(data)
        unique_colors = len(np.unique(data.reshape(-1, data.shape[2]), axis=0))
        
        print(f"{img_path.name:<30} | {img_path.stat().st_size/1024:<10.2f} | {mean_brightness:<15.2f} | {unique_colors:<15}")
    except Exception as e:
        print(f"{img_path.name:<30} | Error: {e}")
