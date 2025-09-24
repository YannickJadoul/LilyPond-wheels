"""Build wheels from LilyPond binaries.

This doesn't actually compile LilyPond, it just reuses the official
binaries, which, conveniently enough, are static and
self-contained. It merely adds a few files that are expected in
wheels. (I did not find a PEP 517 build backend that would do this
more easily than just hand-coding it, although a hatch plugin might be
workable.)

Wheel format specification:
https://packaging.python.org/en/latest/specifications/binary-distribution-format

Core metadata specification (for the METADATA file):
https://packaging.python.org/en/latest/specifications/core-metadata

"""

import argparse
import csv
import hashlib
import io
import os
import zipfile

from pathlib import Path
import requests
import shutil

p: argparse.ArgumentParser = argparse.ArgumentParser()
p.add_argument("version", help="version of LilyPond to package")
p.add_argument("build_number", type=int, help="build number for wheels")
args: argparse.Namespace = p.parse_args()

workdir: Path = Path("build")
print(f"Clearing build/ directory")
shutil.rmtree(workdir, ignore_errors=True)
workdir.mkdir()


def build(plat: str, archive: str, plat_tag: str):
    full_tag: str = f"py3-none-{plat_tag}"

    print(f"Downloading {archive}")
    download_dest: Path = workdir / archive
    url: str = f"https://gitlab.com/lilypond/lilypond/-/releases/v{args.version}/downloads/{archive}"
    response = requests.get(url)
    download_dest.write_bytes(response.content)

    print(f"Preparing wheel directory from {archive}")
    unpack_dest: Path = workdir / plat
    shutil.unpack_archive(download_dest, unpack_dest)
    # It's simpler for the lilypond.py script to be able to expect
    # always the same directory name.
    (unpack_dest / f"lilypond-{args.version}").rename(unpack_dest / "lilypond-binaries")

    if plat == "linux" or plat == "macos":
        # Work around the fact that wheels cannot include empty directories...
        lib_python_dirs = list((unpack_dest / "lilypond-binaries" / "lib").glob("python*"))
        assert len(lib_python_dirs) == 1
        empty = lib_python_dirs[0] / "lib-dynload"
        (empty / ".keep").touch()

    # Create the .dist-info directory
    dist_info_basename: Path = Path(f"lilypond-{args.version}.dist-info")
    dist_info: Path = unpack_dest / dist_info_basename
    dist_info.mkdir()

    # Populate standard metadata
    metadata: Path = dist_info / "METADATA"
    description: str = Path("README.md").read_text(encoding="utf-8")
    metadata_contents: str = f"""\
Metadata-Version: 2.1
Name: lilypond
Version: {args.version}
Home-page: https://gitlab.com/jeanas/lilypond-wheels.git
License: GPL-3.0-or-later
Summary: A redistribution of LilyPond to use it easily from Python code.
Description-Content-Type: text/markdown

{description}
"""
    metadata.write_text(metadata_contents, encoding="utf-8")

    # Populate the require WHEEL file
    wheel: Path = dist_info / "WHEEL"
    wheel_contents: str = f"""\
Wheel-Version: 1.0
Generator: lilypond_custom_generator
Root-Is-Purelib: false
Tag: {full_tag}
Build: {args.build_number}
"""
    wheel.write_text(wheel_contents, encoding="utf-8")

    # Write the wrapper module with the executable() function
    module: Path = unpack_dest / "lilypond.py"
    module_contents: str = """
from pathlib import Path

def executable(script="lilypond"):
    return Path(__file__).parent / "lilypond-binaries" / "bin" / script
"""
    module.write_text(module_contents, encoding="utf-8")

    # Get a list of all archive members. While doing this, also record
    # hashes and sizes for building the RECORD file.
    members: list[tuple[zipfile.ZipInfo, bytes]] = []
    record_tuples: list[tuple[str, str, str]] = []
    for (dirpath, dirnames, filenames) in os.walk(unpack_dest):
        for filename in filenames:
            path: Path = Path(dirpath) / filename
            relpath: Path = path.relative_to(unpack_dest)
            info: zipfile.ZipInfo = zipfile.ZipInfo.from_file(path, relpath)
            contents: bytes = path.read_bytes()
            members.append((info, contents))
            digest = "sha256=" + hashlib.sha256(contents).hexdigest()
            record_tuples.append((str(relpath), digest, str(info.file_size)))

    # Build RECORD. Each line contains the file name, a hash and the
    # file size in bytes.
    record: Path = dist_info / "RECORD"
    rel_record: Path = record.relative_to(unpack_dest)
    with record.open("w", newline="") as record_file:
        writer = csv.writer(record_file)
        for row in record_tuples:
            writer.writerow(row)

    # Add RECORD as an archive member too.
    members.append((zipfile.ZipInfo.from_file(record, rel_record), record.read_bytes()))

    # Sort alphabetically for determinism. In the next call to
    # .sort(), many elements will compare equal, so this is not enough
    # for reproducibility. On the other hand, .sort() is stable
    members.sort(key=lambda info_contents: info_contents[0].filename)

    # Reorder archive members to work around the fact that Guile looks
    # at the timestamps of the .go files, which must be newer than
    # those of the corresponding .scm files.  Also move the .dist-info
    # directory last, per recommendation of the wheel spec.
    def prio(info_contents: tuple[zipfile.ZipInfo, bytes]):
        info, _ = info_contents
        if Path(info.filename).is_relative_to(dist_info_basename):
            return 2
        elif Path(info.filename).is_relative_to("lilypond-binaries/lib/"):
            return 1
        else:
            return 0

    members.sort(key=prio)

    # Finally, output the wheel file
    wheel_file: Path = (
        workdir / f"lilypond-{args.version}-{args.build_number}-{full_tag}.whl"
    )
    print(f"Packing {wheel_file}")
    with zipfile.ZipFile(wheel_file, "w") as wheel_archive:
        for info, contents in members:
            wheel_archive.writestr(info, contents, zipfile.ZIP_DEFLATED)


build(
    plat="linux",
    archive=f"lilypond-{args.version}-linux-x86_64.tar.gz",
    # This tag stems from the fact that official LilyPond binaries for
    # Linux are currently built on CentOS 7, which also corresponds to
    # the manylinux2014 ABI.
    plat_tag="manylinux2014_x86_64",
)

build(
    plat="windows",
    archive=f"lilypond-{args.version}-mingw-x86_64.zip",
    plat_tag="win_amd64",
)
build(
    plat="macos",
    archive=f"lilypond-{args.version}-darwin-x86_64.tar.gz",
    # Official binaries for macOS are currently built on macOS 10.15.
    # (There aren't Apple Silicon builds yet.)
    plat_tag="macosx_10_15_x86_64",
)
