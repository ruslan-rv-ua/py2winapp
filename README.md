<!--
    """Build a Windows executable from a Python project.

    Args:
        python_version (Union[str, None], optional): Python version to use.
            If None, use current interpreter's version. Defaults to None.
        project_path (Union[str, Path, None], optional): Project's directory.
            If None, use current working directory. Defaults to None.
        input_source_dir (Union[str, None], optional): Where the source code is.
            If None, use project's directory. Defaults to None.
        main_file (Union[str, None], optional): Relative to input_source_dir,
            the main file to run. If None, use "main.py". Defaults to None.
        app_name (Union[str, None], optional): Name of the app.
            If None, use project's directory name. Defaults to None.
        ignore_input_patterns (Iterable[str], optional): Patterns to ignore in
            input_dir. Defaults to [].
        app_dir (Union[str, None], optional):
            Where to put the app under `dist` directory (relative to project_dir).
            Defaults to None.
        show_console (bool, optional): Show console or not when running the app.
            Defaults to False.
        requirements_file (str, optional): Name of the requirements file.
            Defaults to "requirements.txt".
        extra_pip_install_args (List[str], optional): Extra args to pass for
            "pip install" command. Defaults to [].
        python_dir (str, optional): Where to put python distribution
            files (relative to app_dir). Defaults to DEFAULT_PYDIST_DIR.
        source_dir (str, optional): Where to put source files (relative to app_dir).
            Defaults to "".
        exe_file (Union[str, None], optional): Name of the exe file.
            If None, use app_name_slug. Defaults to None.
        icon_file (Union[str, Path, None], optional): Icon file to use for the app.
            If None, use default icon. Defaults to None.
        make_dist (bool, optional): Make a zip file of the app under `dist` directory
            or not. Defaults to True.

    Returns:
        BuildData: A data object containing information about the build process.

-->
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

Do not forget to add `build`, `dist` and `downloads` folders to `.gitignore`.

##### `build()`

| parameter              | type                             | default            | description                                                                                     |
| ---------------------- | -------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------- |
| python_version         | Union[str, None], optional       | None               | Python version to use. If None, use current interpreter's version.                              |
| project_path           | Union[str, Path, None], optional | None               | Project's root path. If None, use current working directory.                                    |
| input_source_dir       | Union[str, None], optional       | None               | Directory where the source code is, relative to project root. If None, use project's directory. |
| main_file              | Union[str, None], optional       | None               | Relative to input_source_dir, the main file to run. If None, use "main.py".                     |
| app_name               | Union[str, None], optional       | None               | Name of the app. If None, use project's directory name.                                         |
| ignore_input_patterns  | Iterable[str], optional          | []                 | Patterns to ignore in input_dir.                                                                |
| app_dir                | Union[str, None], optional       | None               | Where to put the app under `dist` directory (relative to project_dir).                          |
| show_console           | bool, optional                   | False              | Show console or not when running the app.                                                       |
| requirements_file      | str, optional                    | "requirements.txt" | Name of the requirements file.                                                                  |
| extra_pip_install_args | List[str], optional              | []                 | Extra args to pass for "pip install" command.                                                   |
| python_dir             | str, optional                    | DEFAULT_PYDIST_DIR | Where to put python distribution files (relative to app_dir).                                   |
| source_dir             | str, optional                    | ""                 | Where to put source files (relative to app_dir).                                                |
| exe_file               | Union[str, None], optional       | None               | Name of the exe file. If None, use app_name_slug.                                               |
| icon_file              | Union[str, Path, None], optional | None               | Icon file to use for the app. If None, use default icon.                                        |
| make_dist              | bool, optional                   | True               | Make a zip file of the app under `dist` directory or not.                                       |

##### `BuildData`

`build()` returns a `BuildData` object:

```python
@dataclass
class BuildData:
    python_version: str
    project_path: Path
    build_dir_path: Path
    dist_dir_path: Path
    download_dir_path: Path
    app_name: str
    app_name_slug: str
    input_source_dir: str
    input_source_dir_path: Path
    ignore_input_patterns: List[str]
    main_file: str
    main_file_path: Path
    app_dir: str
    app_dir_path: Path
    python_dir: str
    python_dir_path: Path
    source_dir: str
    source_dir_path: Path
    requirements_file: str
    requirements_file_path: Path
    extra_pip_install_args: List[str]
    exe_file: str
    exe_file_path: Path
    icon_file_path: Union[Path, None]
    python_version: str
    project_path: Path
    build_dir_path: Path
    dist_dir_path: Path
    download_dir_path: Path
    app_name: str
    app_name_slug: str
    input_source_dir: str
    input_source_dir_path: Path
    ignore_input_patterns: List[str]
    main_file: str
    main_file_path: Path
    app_dir: str
    app_dir_path: Path
    python_dir: str
    python_dir_path: Path
    source_dir: str
    source_dir_path: Path
    requirements_file: str
    requirements_file_path: Path
    extra_pip_install_args: List[str]
    exe_file: str
    exe_file_path: Path
    icon_file_path: Union[Path, None]
    show_console: bool
    zip_file_path: Union[Path, None]

```

### Build from `pyproject.toml`

> Not implemented yet, TODO...

## License

MIT

## Credits

- inspired by [ClimenteA/pyvan](https://github.com/ClimenteA/pyvan#readme)
- some examples got from [ClimenteA/flaskwebgui](https://github.com/ClimenteA/flaskwebgui)
