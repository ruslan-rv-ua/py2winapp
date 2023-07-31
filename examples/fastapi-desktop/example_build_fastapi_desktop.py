import py2winapp

APP_NAME = "fastapi-desktop"

build = py2winapp.build(
    python_version="3.9.7",
    input_dir=f"examples/{APP_NAME}",
    main_file_name="main.py",
    app_dir=APP_NAME,
    source_subdir=APP_NAME,
    requirements_file=f"{APP_NAME}/requirements.txt",
    exe_file_name_without_extension=APP_NAME,
)
