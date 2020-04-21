import os
import re
import os.path

IMG_DIR = "/home/alex/Images"
IMG_EXTS = ['.png', '.jpg', '.RAW2', '.JPG', '.PNG']
OUT_DIR = "/home/alex/Images/out"

# prepare regex
expr = re.compile('([12][0-9][0-9][0-9])-([01][0-9])-')

# recursively traverse all the file tree
for path, dirs, files in os.walk(IMG_DIR):
    for filename in files:
        # split filename into basename and extension
        basename, ext = os.path.splitext(filename)

        # match regex to basename
        m = re.match(expr, basename)

        if m and ext in IMG_EXTS:   # the file is an image with the expected filename pattern
           e = os.path.exists(OUT_DIR/m.group(1)
           if e
           os.rename(IMG_DIR/filename, OUT_DIR/m.group(1)/filename)
           

            
        
