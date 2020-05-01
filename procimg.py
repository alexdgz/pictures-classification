#!/usr/bin/env python3

import os
import re
import hashlib
import datetime
from tqdm import tqdm
import csv
import shutil       # to prevent os.rename OSError: Cross-device link /!\

# the suiss knife of image proc : exiftool
# to batch rename the all videos :
# $ exiftool '-filename<CreateDate' -d VID_%Y-%m-%d_%H%M%S%%-c.%%le -r -ext avi -ext MPG -ext mp4 -ext MOV -ext AVI /path/to/vids


# handle arguments in command line
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("img_dir", help="the image root directory")
parser.add_argument("-f", "--function", choices=['move', 'list', 'dedup', 'split'],
                    help="choose the action (default=list)")
parser.add_argument("-o", "--out",
                    help="the output directory (default=./out)")
parser.add_argument("-l", "--log",
                    help="the log directory (default=./log)")

args = parser.parse_args()
#print(args)


FUNC = args.function or 'list'
IMG_DIR = args.img_dir
OUT_DIR = args.out or "out"
LOG_DIR = args.log or "log"

IMG_LISTING = "files_listing"

FILE_EXTS = ['.JPG', '.jpg', '.RW2', '.AVI', '.tif', '.CR2', '.MOV', '.BMP', '.mp4', '.MPG', '.jpeg', '.png', '.avi', '.tiff', '.gif']
#FILE_EXTS = ['.jpg', '.mp4']
#PATTERN = '(?P<year>[12][09][0129][0-9])-(?P<month>[01][0-9])-[0123][0-9]'
PATTERN = '(IMG|VID)_(?P<year>[12][09][0129][0-9])-(?P<month>[01][0-9])-(?P<day>[0123][0-9])_[0-9]{6}'


# Warning: the disgests file name has not to interfere with any other file name (overwrite otherwise!) 
DIGESTS_FILE = ".secure_hashes"


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


def add_digest(root: str, filename: str, digests: dict) -> None:
    '''
    add a secure hash to the index
    '''
    path = os.path.join(root, filename)
    size: int = os.path.getsize(path)
    lastupdate: float = os.path.getmtime(path)

    if filename not in digests or digests[filename][1] != size or digests[filename][2] != lastupdate:
        hashcode: str = hash_file(path)
        digests[filename] = (hashcode, size, lastupdate)


def move_file(root: str, filename: str, year: str, month: str, day: str) -> None:
    '''
    move the image file from its input location to the output dir.
    perform a bunch of tests and updates before proceeding. 
    '''
    
    path: str = os.path.join(root, filename)
    new_root: str = os.path.join(OUT_DIR, year, year + '-' + month + '-' + day)
    new_path: str = os.path.join(new_root, filename)
    basename, ext = os.path.splitext(filename)

    # check for already existing filename and rename the current one if necessary
    n: int = 1
    while os.path.exists(new_path):
        new_path = os.path.join(new_root, basename + '-' + str(n) + ext)
        n += 1

    # DEADEND: then we use the auto-magic os.renames(src, dst) function that :
    #  - checks or creates the OUT_DIR/YYYY/MM dirs at once
    #  - moves the file to OUT_DIR/YYYY/MM/
    #  - safely deletes the input dirs (recursively) when empty!
#    os.renames(path, new_path)

    # create target dir with intermediate dirs as well if don't exist
    try:
        os.makedirs(new_root)
        print("Directory {} Created".format(new_root))
    except FileExistsError:
        # silently observe already existing directory
        pass
    # move the file, possibly from one partition to another one...
    shutil.move(path, new_path)




def load_digests(dir: str, files: list) -> dict:
    '''
    initialize the digest index for duplicate elimination,
    from an existing CSV serialization of previous hashs
    Format of a row: filename,hashcode,size,lastupdate (epoc time float)
    Format of return dict : { filename: (hashcode, size, lastupdate) }
    '''
    d: dict = {}
    hash_path: str = os.path.join(dir, DIGESTS_FILE)

    if os.path.exists(hash_path):
        with open(hash_path, 'r') as csvfile:
            data = csv.reader(csvfile, delimiter=',', quotechar='"')
            try:
                # keep only up-to-date hashcodes
                for row in data:
                    path = os.path.join(dir, row[0])
                    # check existing filename and size and last update time ! 
                    if row[0] in files and int(row[2]) == os.path.getsize(path) and float(row[3]) == os.path.getmtime(path):
                        d[row[0]] = (row[1], int(row[2]), float(row[3]))
            except csv.Error as e:
                sys.exit('file {}, line {}: {}'.format(hash_path, data.line_num, e))
    return d


def save_digests(d: dict, dir: str) -> None:
    '''
    save secure hashes of all files in dir into DIGESTS_FILE (must be reserved filename!)

    '''
    
    hash_path: str = os.path.join(dir, DIGESTS_FILE)
    if d:    
        # overwrite existing hash file (refresh with new values)
        with open(hash_path, 'w') as csvfile:
            hashwriter = csv.writer(csvfile, delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_MINIMAL)
            hashwriter.writerows([(f, info[0], info[1], info[2]) for f, info in d.items()])
    else:
        if os.path.isfile(hash_path):
            os.remove(hash_path)


def move_all_files() -> None:
    # cook regex
    expr = re.compile(PATTERN)

    # create OUT_DIR & all intermediate directories if don't exist
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
                move_file(root, filename, mdict['year'], mdict['month'], mdict['day'])


def list_all_files():
    exts: dict = {}
    # create log/ dir if it doesn't already exist (otherwise, silently pass)
    os.makedirs(LOG_DIR, exist_ok=True)
    listingfile_path: str = os.path.join(LOG_DIR, IMG_LISTING + "-" + datetime.datetime.now().isoformat() + ".txt")

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
        # initialize digests from previously stored file
        digests: dict = load_digests(root, files)
        # populate digests from files in the subdir
        for f in tqdm(files):
            if f != DIGESTS_FILE:   # skip digests file itself...
                add_digest(root, f, digests)

        ## check for duplicates from the digests dict
        # create hashcode index : { hash: [path1, path2, ...] }
        hash_idx: dict = {}
        for filename, info in digests.items():
            if info[0] in hash_idx:
                hash_idx[info[0]] += [filename]
            else:
                hash_idx[info[0]] = [filename]
        # actually remove the duplicate files!
        for h, fnames in hash_idx.items():
            for f in sorted(fnames)[1:]:     # if there are 2 files or more with the same hash code, then delete all but the first one
                if os.path.isfile(os.path.join(root,f)):   # double check
                    print("DELETE DUPLICATE {}".format(f))
                    os.remove(os.path.join(root,f))
                    del digests[f]

        # don't forget to update the digest file of the current subdir
        save_digests(digests, root)


def split_dirs(max_size: int=500) -> None:
    # recursively traverse all the file tree
    for root, _, files in os.walk(IMG_DIR):
        print(root)
        if len(files) > max_size:
            basedir = os.path.basename(root)
            files.sort()
            dirnum: int = 0
            dirname: str
            for i in range(len(files)):
                if i == dirnum*max_size:
                    dirnum += 1
                    dirname = os.path.join(root, basedir + " #" + str(dirnum))
                    os.mkdir(dirname)
                os.rename(os.path.join(root, files[i]), os.path.join(root, dirname, files[i]))          


# map of available actions-to-functions in the script 
FUNC_MAP = {'list': list_all_files, 
            'move': move_all_files, 
            'dedup': deduplicate_all_files,
            'split': split_dirs,
            }


FUNC_MAP[FUNC]()

#    list_all_files()           # step 1
#    move_all_files()           # step 2
#    deduplicate_all_files()    # step 3
#    split_dirs()                # step 4
#   list_all_files()            # step 5
