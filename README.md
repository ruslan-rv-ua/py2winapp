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


`py2winapp` can be used in two ways:

- as a Command Line Interface (CLI)
- as a Python script

### CLI

> Not implemented yet, TODO...


### Python API

Say you have your project structure:

```bash
dev
└───fastapi-desktop
    │   requirements.txt
    │
    └───fastapi_desktop
        │   main.py
        │
        └───dist
            │   index.html
            │   some_page.html
            │
            ├───css
            │       metro-all.min.css
            │       styles.css
            │
            ├───img
            │       some_images
            │
            └───js
                    jquery-3.4.1.min.js
                    metro.min.js
```

Here we have:

- `fastapi-desktop`: project root folder
- `fastapi_desktop`: folder with source files
- `main.py`: entry point

`requirements.txt` contains all dependencies, including dependencies for development (mypy, flake8, black, ...).
So lets create `requirements-prod.txt` with only production dependencies:

```requirements
# requirements-prod.txt
fastapi
jinja2
uvicorn
flaskwebgui
```

In project root folder create `build.py`:

```python
from py2winapp import build

build(
    python_version='3.11.3',
    input_source_dir='fastapi-desktop',
    main_file='main.py',
    requirements_file = 'requirements-prod.txt',
)
```

Run the script:

```bash
python build.py
```


In the project root, we have the following new folders:

- `downloads`: where downloaded files are cached
- `build`: where your runnable application is located:
    ```
    └───fastapi-desktop
        │   fastapi-desktop.exe
        │   main.py
        │
        ├───dist
        │   │   index.html
        │  ...
        └───python
            │   python.exe
            │   python311._pth
            │   pythonw.exe
            │   ...
            ├───Lib
            │   └───site-packages
            ├───python311.zip
            └───Scripts
           ...
    ```
- `dist`: where your zipped application is located:
    ```
    └─── fastapi-desktop.zip
    ```

Do not forget to add `build`, `dist` and `downloads` folders to `.gitignore``.

## License

MIT

## Credits

- inspired by [ClimenteA/pyvan](https://github.com/ClimenteA/pyvan#readme)
- some examples got from [ClimenteA/flaskwebgui](https://github.com/ClimenteA/flaskwebgui)
