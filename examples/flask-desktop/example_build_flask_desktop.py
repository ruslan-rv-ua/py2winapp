import py2winapp

APP_NAME = "flask-desktop"

build = py2winapp.build(
    python_version="3.9.7",
    input_dir=f"examples/{APP_NAME}",
    main_file_name="main.py",
    app_dir=APP_NAME,
    source_subdir=APP_NAME,
    requirements_file=f"examples/{APP_NAME}/requirements.txt",
)

build.rename_exe_file(APP_NAME)
build.make_zip(APP_NAME)
