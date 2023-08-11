# py2winapp

Make runnable apps from your python scripts!

## Description

### How it works

This script performs the following actions:

- Copies your source files to the build folder
- Downloads Python interpreter to the build folder
- Installs `pip`
- Installs your project's requirements
- Makes an executable startup file wich runs your main script

You'll get a portable Windows application!

### Requirements and limitations

- Python 3.9+
- Tested on Windows 10 only
- Now only `x64` architecture is supported.



## Installation

With `pip`:

```sh
pip install py2winapp
```

With `poetry`:

```sh
poetry add --group build py2winapp
```

## Usage

In project's root create `build.py`:

```python
# build.py

import py2winapp

def make_build():
    py2winapp.build(
        python_version="3.11.3",
        input_source_dir="directory-where-your-source-files-are",
        main_file="main.py",  # your app's entry point
        show_console=True,  # or False if your app is GUI only
    )

if __name__ == '__main__':
    make_build()

```

Run command:

```bash
python build.py
```

You can find build and distribution in `build` and `dist` folders now.

#### Poetry

Add to `pyproject.toml`:

```toml
[tool.poetry.scripts]
build = "build:make_build"

```

Now you can run building with:

```bash
poetry run build
```


See [documentation](https://ruslan-rv-ua.github.io/py2winapp/) for more.

## License

MIT

## Credits

- inspired by [ClimenteA/pyvan](https://github.com/ClimenteA/pyvan#readme)
- used code from [silvandeleemput/gen-exe](https://github.com/silvandeleemput/gen-exe)
