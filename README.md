# py2winapp

## Make runnable apps from your python scripts!

TODO: description

## Usage

1. Install dev dependencies:

    `pip install gen-exe requests`

    Using `poetry`:

    `poetry add gen-exe requests --dev`

1. Make file with requirements:

    `pip freeze > requirements.txt`

    then edit it to leave production requirements only. 

    Using `poetry`: 

    `poetry export -f requirements.txt -o requirements.txt --without-hashes`

1. Download [py2winapp.py](https://raw.githubusercontent.com/ruslan-rv-ua/py2winapp/master/py2winapp.py) and copy it to the root of your project.

1. Make `build.py` with following content:

    ```python
    import py2winapp

    build = py2winapp.build(
        main_file_name="main.py",
        python_version="3.9.7",
    )    
    ```

1. Add other build commands to `build.py` if needed, for ex:

    ```python
    APP_NAME = 'cool-app'

    build.rename_exe_file(APP_NAME)  # main.exe -> cool-app.exe
    build.make_zip(APP_NAME)
    build.remove_build_dir()
    ```

1. Run `build.py`:

    `python build.py`

## `build()`

Parameters are:

|parameter|type|default value|description|
|-|-|-|-|
|`python_version`|`str`|***required***|Embedded python version|
|`input_dir`|`str`|***required***|The directory to get the `main_file_name` file from. Use `''` for project's root|
|`main_file_name`|`str`|***required***|The entry point of the application|
|`ignore_input`|`Iterable[str]`|`()`|Patterns to ignore files/directories when coping source directory.|
|`show_console`|`bool`|`False`|Show console window or not|
|`requirements_file`|`str`|`'requirements.txt'`|Name of requirements file.|
|`app_dir`|`str`|`'dist'`|The directory in which the stand-alone distribution will be created.|
|`python_subdir`|`str`|`'pydist'`|A sub directory relative to `app_dir` where the stand-alone python app will be installed.|
|`source_subdir`|`str`|`''`|A sub directory relative to `app_dir` where to execute python files will be installed.|
|`extra_pip_install_args`|`Iterable[str]`|`()`|arguments to be appended to the `pip install` command during installation of the stand-alone app.|
|`icon_file`|`str`&#124;`Path`&#124;`None`|`None`|Path to icon file to use for your app executable. Don't use one if `None` by default.|
|`download_dir`|`str`&#124;`Path`&#124;`None`|`None`|Direcotry where to download files. `Users\<username>\Downloads\` if `None`.|

If you specify `source_subdir` add following at the beginnig of your `main_file`:

```python
import os
os.chdir(os.path.dirname(__file__))
```

### Returns

`Build` object.

TODO

## Examples

1. Clone this repo:

    `git clone https://github.com/ruslan-rv-ua/py2winapp`

1. Install dependencies:

    `pip install gen-exe requests`

1. Execute any of `example_build_*.py`:

    ```
    cd py2winapp
    python example_build_flask-desktop.py
    ```

    `flask-desktop` directory 
    with ready-to-run app 
    and `flask-desktop.zip` 
    with zipped app 
    will be created.
	
More examples:

- [telecode](https://github.com/ruslan-rv-ua/telecode) — desktop wxPython application

## Credits

- inspired by [ClimenteA/pyvan](https://github.com/ClimenteA/pyvan#readme)
- some examples got from [ClimenteA/flaskwebgui](https://github.com/ClimenteA/flaskwebgui)