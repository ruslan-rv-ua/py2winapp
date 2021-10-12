# py2winapp

## Make runnable apps from your python scripts!

TODO: description

## Usage

1. Install dev dependencies:

    `pip install gen-exe requests`

    Using `poetry`:

    `poetry add gen-exe requests --dev`

1. Make file with requirements:

    `pip freeze > prod_requirements.txt`

    then edit it to leave production requirements only. 

    Using `poetry`: 

    `poetry export -f requirements.txt -o requirements.txt --without-hashes`

1. Download [py2winapp.py](https://raw.githubusercontent.com/ruslan-rv-ua/py2winapp/master/py2winapp.py) and copy it to the root of your project.

1. Make `build.py` with following content:

    ```python
    import py2winapp

    app = py2winapp.build(
        main_file_name="main.py",
        python_version="3.9.7",
    )    
    ```

1. Add other build commands to `build.py` if needed, for ex:

    ```python
    exe = app.exe_file_path
    exe = exe.rename(exe.with_name('run.exe'))
    py2winapp.zip(app.app_path, app.project_path / 'program.zip')
    ```

1. Run `build.py`:

    `python build.py`

## `build()`

### Parameters

|parameter|type|default value|description|
|-|-|-|-|
|`python_version`|`str`|***required***|Embedded python version|
|`input_dir`|`str`|`''`|The directory to get the `main_file_name` file from. If `None` then use project's root|
|`main_file_name`|`str`|***required***|The entry point of the application|
|`ignore_input`|`Iterable[str]`|`()`|Patterns to ignore files/directories when coping source directory.|
|`show_console`|`bool`|`False`|Show console window or not|
|`requirements_file`|`str`|`'requirements.txt'`|Name of requirements file.|
|`build_dir`|`str`|`'dist'`|The directory in which the stand-alone distribution will be created.|
|`build_pydist_dir`|`str`|`'pydist'`|A sub directory relative to `build_dir` where the stand-alone python app will be installed.|
|`build_source_dir`|`str`|`''`|A sub directory relative to `build_dir` where to execute python files will be installed.|
|`extra_pip_install_args`|`Iterable[str]`|`()`|arguments to be appended to the `pip install` command during installation of the stand-alone app.|
|`icon_file`|`str`&#124;`Path`&#124;`None`|`None`|Path to icon file to use for your app executable. Don't use one if `None` by default.|
|`download_dir`|`str`&#124;`Path`&#124;`None`|`None`|Direcotry where to download files. `Users\<username>\Downloads\` if `None`.|


### Returns

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

## Credits

- inspired by [ClimenteA/pyvan](https://github.com/ClimenteA/pyvan#readme)
- some examples got from [ClimenteA/flaskwebgui](https://github.com/ClimenteA/flaskwebgui)