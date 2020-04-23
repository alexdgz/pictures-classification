import os
import re
import os.path
import hashlib
import json

#IMG_DIR = "/Volumes/photo"
IMG_DIR = "/Volumes/photo"
FILE_EXTS = ['.JPG', '.jpg', '.RW2', '.AVI', '.tif', '.CR2', '.MOV', '.BMP', '.mp4', '.MPG', '.jpeg', '.png', '.avi', '.tiff', '.gif']
OUT_DIR = "/Volumes/photo/lib"
LOG_DIR = "log"
DIGESTS = "hashfiles.json"
IMG_LISTING = "img_files_listing.txt"

'''
Produce a secure hash (digest) from a file and the secure blake2b (vs. SHA and MD5) algorithm,
to be able to find duplicates
'''
def hash_file(path: str, blocksize: int = 65536) -> str:
    hashcode = hashlib.blake2b(digest_size=32)      # limit digest size to 32 bytes (default/max= 64).
    with open(path, "rb") as f:
        chunk = f.read(blocksize)
        while chunk:
            hashcode.update(chunk)
            chunk = f.read(blocksize)
    return hashcode.hexdigest()


'''
check for duplicates from a hashmap of digests
side effect: update the hashmap if the file is not a duplicate
'''
def is_duplicate(path: str, digests: dict) -> bool:
    duplicate: bool = False
    hashcode: str = hash_file(path)
    if hashcode in digests:  # found a duplicate file
        duplicate = True
        digests[hashcode] += [path]
    else:   # add the new file digest to the index (don't care so much about the value True/False)
        digests[hashcode] = [path]
    return duplicate


'''
move the image file from its input location to the output dir.
perform a bunch of tests and updates before proceeding. 
'''
def move_file(root: str, filename: str, year: str, month: str) -> None:
    path: str = os.path.join(root, filename)
    new_root: str = os.path.join(OUT_DIR, year, month)
    new_path: str = os.path.join(new_root, filename)
    basename, ext = os.path.splitext(filename)

    # check for already existing filename and rename the current one if necessary
    n: int = 1
    while os.path.exists(new_path):
        new_path = os.path.join(new_root, basename + '(' + n + ')'+ ext)
        n += 1

    # then we use the auto-magic os.renames(src, dst) function that do :
    #  - check or create the OUT_DIR/YYYY/MM dirs at once
    #  - move the file to OUT_DIR/YYYY/MM/
    #  - safely delete the input dirs (recursively) when empty!
    os.renames(path, new_path)


'''
initialize the digest index for duplicate elimination, from the existing output files.
/!\ It is required that the output dir is exclusively dedicated to the organized picture files
'''
def load_digests() -> dict:
    d: dict = {}
    hasfile_path: str = os.path.join(LOG_DIR, DIGESTS)
    if os.path.exists(hasfile_path):
        with open(hasfile_path, 'r') as f:
            d = json.load(f)
    '''
    # recursively traverse all the output file tree
    if os.path.isdir(OUT_DIR):
        for root, _, files in os.walk(OUT_DIR):
            for filename in files:
                is_duplicate(os.path(root, filename), d)
    '''
    return d


'''
save secure hashes of image files to be used later on
'''
def save_digests(d: dict) -> None:
    # create log/ dir if it doesn't already exist (otherwise, silently pass)
    os.makedirs(LOG_DIR, exist_ok=True)
    hasfile_path: str = os.path.join(LOG_DIR, DIGESTS)
    
    with open(hashfile_path, 'w') as f:
        json.dump(d, f)


def main() -> None:
    # declare and initialize an index of file digests to test for duplicates
    digests: dict = load_digests()
    # cook regex
    expr = re.compile('([12][09][0129][0-9])-([01][0-9])-[0123][0-9]')

    # create OUT_DIR & all intermediate directories if don't exists
    try:
        os.makedirs(OUT_DIR)    
        print("Directory {} Created".format(OUT_DIR))
    except FileExistsError:
        # silently observe already existing directory
        pass

    # recursively traverse all the file tree
    for root, _, files in os.walk(IMG_DIR):
        for filename in files:
            # rebuild the entire path to the file
            path = os.path.join(root, filename)
            print(path)

            # split filename into basename and extension
            basename, ext = os.path.splitext(filename)

            # match regex to basename
            m = re.match(expr, basename)

            # move the file on condition
#            if m and ext in FILE_EXTS and not is_duplicate(path, digests):
            if m and ext in FILE_EXTS:      # forget about duplicates: to be handled later on, in each dir (separately, then much faster).
                # the file is actually a new image with the expected filename pattern
                move_file(root, filename, m.group(1), m.group(2))
    
    save_digests(digests)


def list_all_files():
    exts: dict = {}
    # create log/ dir if it doesn't already exist (otherwise, silently pass)
    os.makedirs(LOG_DIR, exist_ok=True)
    listingfile_path: str = os.path.join(LOG_DIR, IMG_LISTING)

    # recursively traverse all the file tree
    with open(listingfile_path, "w") as out:
        for root, _, files in os.walk(IMG_DIR):
            print(root)
            for filename in files:
                out.write("{}\n".format(os.path.join(root, filename)))
                _, ext = os.path.splitext(filename)
                if ext in exts:
                    exts[ext] +=1
                else:
                    exts[ext] = 1

        out.write("=== {} files in the collection ===\n".format(sum(exts.values())))
        out.write("--- Ordered list of file extensions ---\n")
        for k in sorted(exts, key=exts.get, reverse=True):
            out.write("{:<8}: {}\n".format(k, exts[k]))
    return exts


if __name__ == '__main__':
    list_all_files()
#    main()
