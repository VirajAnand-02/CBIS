from PIL import Image
from PIL.ExifTags import TAGS

def get_exif_data(image_path):
    """
    Extracts and returns EXIF data from an image.
    """
    try:
        image = Image.open(image_path)
        exifdata = image.getexif()

        if exifdata is None:
            return "No EXIF data found in this image."

        exif_dict = {}
        for tag_id, value in exifdata.items():
            # Get the tag name instead of the tag ID
            tag_name = TAGS.get(tag_id, tag_id)
            exif_dict[tag_name] = value
        return exif_dict
    except FileNotFoundError:
        return "Error: Image file not found."
    except Exception as e:
        return f"An error occurred: {e}"

# Example usage:
image_file = "cal.png"  # Replace with your image file path
exif_info = get_exif_data(image_file)

if isinstance(exif_info, dict):
    print(f"EXIF data for {image_file}:")
    for key, value in exif_info.items():
        print(f"  {key}: {value}")
else :
    print(exif_info)