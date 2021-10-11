# py2winapp

## Make runnable apps from your python scripts!

TODO: description

## Usage

1. install dev dependencies:

    `pip install gen-exe requests`

    or using `poetry`:

    `poetry add gen-exe requests --dev`

1. Make file with requirements

    `pip freeze > prod_requirements.txt`

    then edit it to leave production requirements only. 

    Using `poetry`: 

    `poetry export -f requirements.txt -o requirements.txt --without-hashes`

1. Download [py2winapp.py](https://raw.githubusercontent.com/ruslan-rv-ua/py2winapp/master/py2winapp.py) and copy it to the root of your project.

1. Make `build.py` with following content:

    ```python
    import py2winapp

    app = py2winapp.build(
        main_file_name="main.py",  # your app's main py-file
        python_version="3.9.7",  # python version
    )    
    ```

1. Add other build commands to `build.py` if needed, for ex:

    ```python
    exe = app.exe_file_path
    exe = exe.rename(exe.with_name('run.exe'))
    from py2winapp import zip
    zip(app.app_path, app.project_path / 'program.zip')
    ```

1. Run `build.py`:

    `python build.py`

