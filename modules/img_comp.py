from PIL import Image
import sys
import os

def compress_image(input_path):
    try:
        # Open the image
        with Image.open(input_path) as img:
            # Convert to RGB if it has alpha (for better JPG compatibility)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Resize to half the dimensions (maintains aspect ratio)
            original_width, original_height = img.size
            new_width = original_width // 2
            new_height = original_height // 2
            
            # Use high-quality downsampling
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Output path: original_name_compressed.ext
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_compressed{ext}"
            
            # Save with format-specific optimization
            if ext.lower() in (".jpg", ".jpeg"):
                img.save(output_path, "JPEG", quality=85, optimize=True, progressive=True)
            elif ext.lower() == ".png":
                img.save(output_path, "PNG", optimize=True, compress_level=9)
            else:
                # For other formats (WEBP, etc.)
                img.save(output_path, optimize=True)
            
            original_size = os.path.getsize(input_path) / 1024
            new_size = os.path.getsize(output_path) / 1024
            print(f"✅ Compressed: {input_path}")
            print(f"   Original: {original_size:.1f} KB → New: {new_size:.1f} KB")
            print(f"   Saved as: {output_path}\n")
    
    except Exception as e:
        print(f"❌ Error processing {input_path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: Drag and drop image(s) onto this script, or run with file path.")
        input("Press Enter to exit...")
        sys.exit(1)
    
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            compress_image(arg)
        else:
            print(f"Skipping (not a file): {arg}")
    sys.exit(1)