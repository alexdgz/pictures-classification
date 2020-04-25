import os
import re
import os.path
import hashlib
import json

IMG_DIR = "/Pictures/lib"
#FILE_EXTS = ['.JPG', '.jpg', '.RW2', '.AVI', '.tif', '.CR2', '.MOV', '.BMP', '.mp4', '.MPG', '.jpeg', '.png', '.avi', '.tiff', '.gif']
FILE_EXTS = ['.jpg', '.mp4']
OUT_DIR = "/Pictures/out"
LOG_DIR = "log"
DIGESTS = "hashfiles.json"
IMG_LISTING = "img_files_listing.txt"
#PATTERN = '(?P<year>[12][09][0129][0-9])-(?P<month>[01][0-9])-[0123][0-9]'
PATTERN = '(IMG|VID)_(?P<year>[12][09][0129][0-9])-(?P<month>[01][0-9])-[0123][0-9]_[0-9]{6}'


def hash_file(path: str, blocksize: int = 65536) -> str:
    '''
    Produce a secure hash (digest) from a file and the secure blake2b (vs. SHA and MD5) algorithm,
    to be able to find duplicates
    '''

    hashcode = hashlib.blake2b(digest_size=32)      # limit digest size to 32 bytes (default/max= 64).
    with open(path, "rb") as f:
        chunk = f.read(blocksize)
        while chunk:
            hashcode.update(chunk)
            chunk = f.read(blocksize)
    return hashcode.hexdigest()


def add_digest(path: str, digests: dict) -> None:
    '''
    add a secure hash to the index
    '''

    hashcode: str = hash_file(path)
    if hashcode in digests:  # found a duplicate file
        digests[hashcode] += [path]
    else:   # add the new file digest to the index (don't care so much about the value True/False)
        digests[hashcode] = [path]



def move_file(root: str, filename: str, year: str, month: str) -> None:
    '''
    move the image file from its input location to the output dir.
    perform a bunch of tests and updates before proceeding. 
    '''
    
    path: str = os.path.join(root, filename)
    new_root: str = os.path.join(OUT_DIR, year, month)
    new_path: str = os.path.join(new_root, filename)
    basename, ext = os.path.splitext(filename)

    # check for already existing filename and rename the current one if necessary
    n: int = 2
    while os.path.exists(new_path):
        new_path = os.path.join(new_root, basename + '-' + str(n) + ext)
        n += 1

    # then we use the auto-magic os.renames(src, dst) function that :
    #  - checks or creates the OUT_DIR/YYYY/MM dirs at once
    #  - moves the file to OUT_DIR/YYYY/MM/
    #  - safely deletes the input dirs (recursively) when empty!
    os.renames(path, new_path)



def load_digests() -> dict:
    '''
    initialize the digest index for duplicate elimination,
    from an existing json serialization of previous hashs
    '''
    
    d: dict = {}
    hasfile_path: str = os.path.join(LOG_DIR, DIGESTS)
    if os.path.exists(hasfile_path):
        with open(hasfile_path, 'r') as f:
            d = json.load(f)
    return d


def save_digests(d: dict) -> None:
    '''
    save secure hashes of image files to be used later on
    '''
    
    # create log/ dir if it doesn't already exist (otherwise, silently pass)
    os.makedirs(LOG_DIR, exist_ok=True)
    hashfile_path: str = os.path.join(LOG_DIR, DIGESTS)
    
    with open(hashfile_path, 'w') as f:
        json.dump(d, f)


def move_all_files() -> None:
    # cook regex
    expr = re.compile(PATTERN)

    # create OUT_DIR & all intermediate directories if don't exists
    try:
        os.makedirs(OUT_DIR)    
        print("Directory {} Created".format(OUT_DIR))
    except FileExistsError:
        # silently observe already existing directory
        pass

    # recursively traverse all the file tree
    for root, _, files in os.walk(IMG_DIR):
        print(root)
        for filename in files:

            # split filename into basename and extension
            basename, ext = os.path.splitext(filename)

            # match regex to basename
            m = re.match(expr, basename)
            mdict = m.groupdict() if m else None

            # move the file on condition
            if mdict and ext in FILE_EXTS:      # forget about duplicates: to be handled later on, in each dir (separately, then much faster).
                # the file is actually a new image with the expected filename pattern
                print("MOVE {}".format(filename))
                move_file(root, filename, mdict['year'], mdict['month'])


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


def deduplicate_all_files() -> None:

    # recursively traverse all the file tree
    for root, _, files in os.walk(IMG_DIR):
        print(root)
        if len(files) > 0:
            files.sort()
            basenames = [ os.path.splitext(f)[0] for f in files ]
            i: int = 0
            while i < len(files)-1:
                k: int = 1
                if basenames[i+1].startswith(basenames[i]):
                    # enter prepare-for-duplicate section
                    # declare an index of file digests to test for duplicates
                    digests: dict = {}

                    add_digest(os.path.join(root, files[i]), digests)
                    add_digest(os.path.join(root, files[i+1]), digests)
                    # check for the next filenames
                    k= 2
                    while i+k < len(files) and basenames[i+k].startswith(basenames[i]):
                        add_digest(os.path.join(root, files[i+k]), digests)
                        k += 1
                    # actually check for duplicates from the digests dict
                    for _, paths in digests.items():
                        for f in paths[1:]:     # if there are 2 files or more with the same hash code, then delete all but the first one
                            print("DELETE DUPLICATE {}".format(f))
                            os.remove(f)
                i += k
#    save_digests(digests)


if __name__ == '__main__':
    deduplicate_all_files()
#    list_all_files()
#    move_all_files()
