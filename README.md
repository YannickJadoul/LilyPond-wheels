# LilyPond wheels

## What's this?

[*GNU LilyPond*](https://lilypond.org) is a text-based music typesetter.
*Wheels* are the standard binary distribution format for Python packages.  This
repository contains a script that is being used to package LilyPond in wheel
format. The resulting wheels are uploaded on PyPI (see the
[lilypond](https://pypi.org/project/lilypond) project page). The goal is to make
it easy to use LilyPond from Python code, installing LilyPond as if it were a
normal Python package — which allows to include it in your dependencies, pin it,
makes tools like `tox` able to install it, and generally makes all the tooling
around standard Python packages just work.

## Usage

If you want to have the LilyPond wrapper package available in your Python
environment, you can install it using

```
pip install lilypond
```

As always, consider installing packages in a [virtual
environment](https://docs.python.org/3/tutorial/venv.html) instead of globally.

You can of course use it in all the other normal ways a package on PyPI can be
used: `pyproject.toml` `project.dependencies` list, dependencies in `tox.ini`,
`requirements.txt` files, etc.

`pip install lilypond` does **NOT** make `lilypond` available as a command —
this is normal! This wrapper is specifically intended for using LilyPond from
Python code, not for installing LilyPond in general. In order to use the bundled
LilyPond, you should do:

```
import subprocess

import lilypond

subprocess.run([lilypond.executable(), "file.ly"])
```

That is, import the `lilypond` module, and use the `executable()` function to
get the full path to the bundled `lilypond` executable, as a `pathlib.Path`
object, then use the `subprocess` module to execute it.

Scripts shipped with LilyPond are also available; use the optional argument to
`executable()`, e.g., `executable("convert-ly")`, to access them.

## Maintenance

When a new LilyPond release is out, run

```
tox -- <version> 0
```

This leaves wheels of LilyPond `<version>` in `build/`. If they look good (use a
venv to check), upload them with

```
python -m twine upload build/*.whl
```

The `0` in the `tox` command is the build number. In case something goes wrong
in published wheels, fixed wheels should be uploaded with a build number of `1`
(then `2`, etc.).
