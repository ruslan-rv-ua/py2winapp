"""py2winapp.py

This script is used to create a Windows executable from a Python script.

TODO:
- fix: can't install requirement like `requests==2.31.0 ; python_version >= "3.11" and python_version < "4.0"`
- use pythonw.exe to hide console
- add support for pyproject.toml
- add logging
- add app_name and app_version to BuildData
- add requirements installation from requirements.txt

"""
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Union

import requests
from genexe.generate_exe import generate_exe

from py2winapp.downloader import Dwwnloader

######################################################################
# constants
######################################################################

# python_version can be anything of the form:
# `x.x.x` where any x may be set to a positive integer.
PYTHON_VERSION_REGEX = re.compile(r"^(\d+|x)\.(\d+|x)\.(\d+|x)$")

GETPIPPY_URL = "https://bootstrap.pypa.io/get-pip.py"
GETPIPPY_FILE = "get-pip.py"
PYTHON_URL = "https://www.python.org/ftp/python"

HEADER_NO_CONSOLE = """import sys, os
if sys.executable.endswith('pythonw.exe'):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = (Path(__file__).parent / 'stderr').open('w')

"""
DEFAULT_IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "py2winapp.py",
    "build.py",
]

DEFAULT_DIST_DIR = "dist"
DEFAULT_PYDIST_DIR = "pydist"
DEFAULT_DOWNLOAD_DIR = "downloads"  # ensure this is in .gitignore


######################################################################
# Build data
######################################################################


@dataclass
class BuildData:
    python_version: str
    project_path: Path
    input_source_dir: str
    input_source_dir_path: Path
    main_file: str
    main_file_path: Path
    app_dir: str
    app_dir_path: Path
    show_console: bool
    requirements_file: str
    requirements_file_path: Path
    extra_pip_install_args: Iterable[str]
    python_subdir: str
    python_subdir_path: Path
    source_subdir: str
    source_subdir_path: Path
    exe_file_without_extension: str
    exe_file_path: Path
    icon_file_path: Union[Path, None]
    zip_file_path: Union[Path, None]
    download_dir_path: Path


def make_build_data(
    python_version: str,
    input_source_dir: str,
    main_file: str,
    ignore_input: Iterable[str],
    app_dir: Union[str, None],
    show_console: bool,
    requirements_file: str,
    extra_pip_install_args: Iterable[str],
    python_subdir: str,
    source_subdir: str,
    exe_file_without_extension: Union[str, None],
    icon_file: Union[str, Path, None],
    make_zip: bool,
) -> BuildData:
    if not is_valid_python_version(python_version):
        raise ValueError(
            f"Specified python version `{python_version}` "
            "does not have the correct format, "
            "it should be of format: `x.x.x` where `x` is a positive number."
        )
    project_path = Path.cwd()  #! TODO: make this a parameter
    if not project_path.exists() or not project_path.is_dir():
        raise ValueError(f"Project path `{project_path}` does not exist.")

    input_source_dir_path = project_path / input_source_dir
    if not input_source_dir_path.exists() or not input_source_dir_path.is_dir():
        raise ValueError(f"Input directory `{input_source_dir_path}` does not exist.")

    main_file_path = input_source_dir_path / main_file
    if not main_file_path.exists() or not main_file_path.is_file():
        raise ValueError(f"Main file `{main_file_path}` does not exist.")

    if app_dir is None:
        app_dir = project_path.name
    app_dir_path = project_path / DEFAULT_DIST_DIR / app_dir  # e.g. dist\app_dir

    requirements_file_path = project_path / requirements_file
    if not requirements_file_path.exists():
        raise ValueError(
            f"Requirements file `{requirements_file_path}` does not exist."
        )

    python_subdir_path = app_dir_path / python_subdir
    source_subdir_path = app_dir_path / source_subdir

    if icon_file is not None:
        icon_file_path = Path(icon_file)
        if not icon_file_path.is_absolute():
            icon_file_path = project_path / icon_file
        if not icon_file_path.exists():
            raise ValueError(f"Icon file `{icon_file_path}` does not exist.")
    else:
        icon_file_path = None

    download_dir_path = project_path / DEFAULT_DOWNLOAD_DIR
    download_dir_path.mkdir(exist_ok=True)

    if exe_file_without_extension is None:
        exe_file_without_extension = main_file_path.stem
    exe_file_path = app_dir_path / f"{exe_file_without_extension}.exe"

    zip_file_path = (
        app_dir_path / f"{exe_file_without_extension}.zip" if make_zip else None
    )

    return BuildData(
        python_version=python_version,
        project_path=project_path,
        input_source_dir=input_source_dir,
        input_source_dir_path=input_source_dir_path,
        main_file=main_file,
        main_file_path=main_file_path,
        app_dir=app_dir,
        app_dir_path=app_dir_path,
        show_console=show_console,
        requirements_file=requirements_file,
        requirements_file_path=requirements_file_path,
        extra_pip_install_args=extra_pip_install_args,
        python_subdir=python_subdir,
        python_subdir_path=python_subdir_path,
        source_subdir=source_subdir,
        source_subdir_path=source_subdir_path,
        exe_file_without_extension=exe_file_without_extension,
        exe_file_path=exe_file_path,
        icon_file_path=icon_file_path,
        zip_file_path=zip_file_path,
        download_dir_path=download_dir_path,
    )


######################################################################
# build
######################################################################


def build(
    python_version: str,  # python version to use
    input_source_dir: str,  # where the source code is
    main_file: str,  # main file, e.g. `main.py`
    ignore_input: Iterable[str] = (),  # patterns to ignore in input_dir
    app_dir: Union[
        str, None
    ] = None,  # where to put the app under `dist` directory (relative to project_dir)
    show_console: bool = False,  # show console or not when running the app
    requirements_file: str = "requirements.txt",
    extra_pip_install_args: Iterable[str] = (),  # extra arguments to pip install
    python_subdir: str = DEFAULT_PYDIST_DIR,  # where to put python distribution files (relative to app_dir)
    source_subdir: str = "",  # where to put source files (relative to app_dir)
    exe_file_without_extension: Union[
        str, None
    ] = None,  # name of the exe file without extension. If None, use the name of the main file #! TODO: or use the name of the app_dir
    icon_file: Union[str, Path, None] = None,  # icon file to use for the app
    make_zip: bool = False,  # make a zip file of the app
) -> BuildData:
    build_data = make_build_data(
        python_version=python_version,
        input_source_dir=input_source_dir,
        main_file=main_file,
        ignore_input=ignore_input,
        app_dir=app_dir,
        show_console=show_console,
        requirements_file=requirements_file,
        extra_pip_install_args=extra_pip_install_args,
        python_subdir=python_subdir,
        source_subdir=source_subdir,
        exe_file_without_extension=exe_file_without_extension,
        icon_file=icon_file,
        make_zip=make_zip,
    )

    # create or clean app directory
    make_app_dir(app_dir_path=build_data.app_dir_path)

    # copy source files
    copy_source_files(
        input_source_dir_path=build_data.input_source_dir_path,
        source_dir_path=build_data.source_subdir_path,
        build_dir_name=build_data.app_dir_path.name,
        ignore_patterns=list(ignore_input),
    )

    # download python embedded distribution file and extract it to build directory
    python_zip_path = get_python_dist(build_data=build_data)

    # download `get_pip.py` and copy it to build directory
    getpippy_file_path = get_getpippy(build_data=build_data)

    # prepare for pip install
    prepare_for_pip_install(
        python_version=python_version,
        app_dir_path=build_data.app_dir_path,
        pydist_dir_path=build_data.python_subdir_path,
        build_source_dir_path=build_data.source_subdir_path,
    )

    # install pip
    install_pip(pydist_dir_path=build_data.python_subdir_path)

    # delete `get_pip.py` from build directory cause it waists more than 2.5MB
    # getpippy_file_path.unlink() #! TODO: chore - romove this line
    (build_data.python_subdir_path / GETPIPPY_FILE).unlink()

    # install requirements
    install_requirements_from_file(build_data=build_data)

    # generate exe
    exe_file_path = make_startup_exe(
        main_file=build_data.main_file,
        exe_file_without_extension=build_data.exe_file_without_extension,
        show_console=build_data.show_console,
        app_dir_path=build_data.app_dir_path,
        pydist_dir_path=build_data.python_subdir_path,
        build_source_dir_path=build_data.source_subdir_path,
        icon_file_path=build_data.icon_file_path,
    )

    # make zip file
    if make_zip:
        make_zip_file(
            file_name=build_data.app_dir,
            destination_dir=build_data.app_dir_path.parent,
            project_path=build_data.project_path,
            app_path=build_data.app_dir_path,
        )

    print(
        f"\nBuild done! Folder `{build_data.app_dir_path}` "
        "contains your runnable application!\n"
    )

    return build_data


######################################################################
# Functions
######################################################################


def make_app_dir(app_dir_path: Path) -> None:
    print(">>> app_path:", app_dir_path)
    dist_dir_path = app_dir_path.parent
    assert dist_dir_path.name == DEFAULT_DIST_DIR, f'Expected "{dist_dir_path}"'
    if dist_dir_path.is_dir():
        print(
            f"Existing dist directory found, removing contents from `{dist_dir_path}`"
        )
        shutil.rmtree(dist_dir_path)
        print("Done!\n")
    dist_dir_path.mkdir()
    app_dir_path.mkdir()


def copy_source_files(
    input_source_dir_path: Path,
    source_dir_path: Path,
    build_dir_name: str,
    ignore_patterns: list[str] = [],
) -> None:
    """Copy .py files and others to build folder"""
    ignore_patterns = ignore_patterns or []
    ignore_patterns.append(build_dir_name)
    ignore_patterns += DEFAULT_IGNORE_PATTERNS
    if not source_dir_path.is_dir():
        source_dir_path.mkdir()
    print(f"Copying files from `{input_source_dir_path}` to `{source_dir_path}`!")
    shutil.copytree(
        src=input_source_dir_path,
        dst=source_dir_path,
        ignore=shutil.ignore_patterns(*ignore_patterns),
        dirs_exist_ok=True,
    )
    print("Done!\n")


def get_python_dist(build_data: BuildData) -> Path:
    downloader = Dwwnloader(build_data.download_dir_path)
    python_file_name = f"python-{build_data.python_version}-embed-amd64.zip"  # e.g. python-3.9.6-embed-amd64.zip
    downloaded_python_zip_path = downloader.download(
        url=f"{PYTHON_URL}/{build_data.python_version}/{python_file_name}",
        file=python_file_name,
    )
    # extract python zip file to build folder
    print(
        f"Extracting `{downloaded_python_zip_path}` to `{build_data.python_subdir_path}`"
    )
    unzip(
        zip_file_path=downloaded_python_zip_path,
        destination_dir_path=build_data.python_subdir_path,
    )
    print("Done!\n")
    return downloaded_python_zip_path


def get_getpippy(build_data: BuildData) -> Path:
    downloader = Dwwnloader(build_data.download_dir_path)
    getpippy_file_path = downloader.download(file=GETPIPPY_FILE, url=GETPIPPY_URL)
    shutil.copy2(getpippy_file_path, build_data.python_subdir_path)
    return getpippy_file_path


#! remove
# def copy_getpippy_to_pydist_dir(
#     getpippy_file_path: Path, pydist_dir_path: Path
# ) -> None:
#     """Copy `get-pip.py` file to build folder"""
#     print(f"Coping `{getpippy_file_path}` file to `{pydist_dir_path}`")
#     print("Done!\n")


def prepare_for_pip_install(
    python_version: str,
    app_dir_path: Path,
    pydist_dir_path: Path,
    build_source_dir_path: Path,
) -> None:
    """
    Prepare the extracted embedded python version for pip installation
    - Uncomment 'import site' line from pythonXX._pth file
    - Extract pythonXX.zip zip file to pythonXX.zip folder
      and delete pythonXX.zip zip file
    """

    short_python_version = "".join(python_version.split(".")[:2])  # 3.9.7 -> 39
    pth_file_name = f"python{short_python_version}._pth"  # python39._pth
    pythonzip_file_name = f"python{short_python_version}.zip"  # python39.zip

    pth_file_path = pydist_dir_path / pth_file_name
    pythonzip_file_path = pydist_dir_path / pythonzip_file_name

    print(f"Generating `{pth_file_path}` with uncommented `import site` line")

    if pydist_dir_path == app_dir_path:
        relative_path_to_source = "."
    else:
        relative_path_to_source = ".."
    relative_path_to_source += f"\\{build_source_dir_path.name}"

    pth_file_content = (
        f"{pythonzip_file_name}\n"
        + f"{relative_path_to_source}\n\n"
        + "# Uncomment to run site.main() automatically\n"
        + "import site\n"
    )
    pth_file_path.write_text(pth_file_content, encoding="utf8")
    print("Done!\n")

    pythonzip_dir_path = Path(pythonzip_file_path)
    print(f"Extracting `{pythonzip_file_path}` to `{pythonzip_dir_path}`")
    pythonzip_file_path = pythonzip_file_path.rename(
        pythonzip_file_path.with_suffix(".temp_zip")
    )
    unzip(pythonzip_file_path, pythonzip_dir_path)
    pythonzip_file_path.unlink()
    print("Done!\n")


def install_pip(pydist_dir_path: Path) -> None:
    print("Installing `pip`")
    execute_os_command(
        command="python.exe get-pip.py --no-warn-script-location",
        cwd=str(pydist_dir_path),
    )
    if not (pydist_dir_path / "Scripts").exists():
        raise RuntimeError("Can not install `pip` with `get-pip.py`!")

    print("Done!\n")


def install_requirements_from_file(build_data: BuildData) -> None:
    """
    Install the modules from requirements.txt file
    - extra_pip_install_args (optional `List[str]`) :
    pass these additional arguments to the pip install command
    """

    print(f"Installing requirements from `{build_data.requirements_file_path}`")

    if build_data.extra_pip_install_args:
        extra_args_str = extra_args_str = " " + " ".join(
            build_data.extra_pip_install_args
        )
    else:
        extra_args_str = ""
    scripts_dir_path = build_data.python_subdir_path / "Scripts"
    command = (
        "pip3.exe install --no-cache-dir --no-warn-script-location "
        f"-r {str(build_data.requirements_file_path)}{extra_args_str}"
    )
    try:
        execute_os_command(command=command, cwd=str(scripts_dir_path))
        return
    except Exception as e:
        print(f"Error: {e}")
    print(f"Failed to install modules from `{build_data.requirements_file_path}`")
    print("Trying to install modules one by one")
    modules = build_data.requirements_file_path.read_text().splitlines()
    install_requirements_one_by_one(modules, build_data)


def install_requirements_one_by_one(
    reqauirements: list[str], build_data: BuildData
) -> None:
    """Install the modules from requirements.txt file

    - extra_pip_install_args (optional `List[str]`) :
    pass these additional arguments to the pip install command

    Each module is installed one by one.
    If any module fails to install, it is added to FAILED_TO_INSTALL_MODULES.txt file

    Module example: `requests==2.31.0`
    """
    if build_data.extra_pip_install_args:
        extra_args_str = extra_args_str = " " + " ".join(
            build_data.extra_pip_install_args
        )
    else:
        extra_args_str = ""
    scripts_dir_path = build_data.python_subdir_path / "Scripts"
    failed_to_install_modules = []
    for module in reqauirements:
        try:
            print(f"Installing {module} ...")
            command = (
                "pip3.exe install --no-cache-dir --no-warn-script-location "
                f"{module}{extra_args_str}"
            )
            execute_os_command(command=command, cwd=str(scripts_dir_path))
        except Exception:
            print("FAILED TO INSTALL ", module)
            failed_to_install_modules.append(module)

    if failed_to_install_modules:
        (build_data.app_dir_path / "FAILED_TO_INSTALL_MODULES.txt").write_text(
            "\n".join(failed_to_install_modules), encoding="utf8"
        )
        print(f"Failed to install {len(failed_to_install_modules)} modules")
        print("See FAILED_TO_INSTALL_MODULES.txt for more info")
    else:
        print("Done!\n")


def make_startup_exe(
    main_file: str,
    exe_file_without_extension: str,
    show_console: bool,
    app_dir_path: Path,
    pydist_dir_path: Path,
    build_source_dir_path: Path,
    icon_file_path: Union[Path, None],
) -> Path:
    """Make the startup exe file needed to run the script"""

    relative_pydist_dir = pydist_dir_path.relative_to(app_dir_path)
    relative_source_dir = build_source_dir_path.relative_to(app_dir_path)
    exe_file_path = app_dir_path / Path(exe_file_without_extension).with_suffix(".exe")
    python_entrypoint = "python.exe"
    command_str = (
        f"{{EXE_DIR}}\\{relative_pydist_dir}\\{python_entrypoint} "
        + f"{{EXE_DIR}}\\{relative_source_dir}\\{main_file}"
    )
    print(">>> command_str =", command_str, "\n")
    print(f"Making startup exe file `{exe_file_path}`")
    generate_exe(
        target=exe_file_path,
        command=command_str,
        icon_file=icon_file_path,
        show_console=show_console,
    )

    if not show_console:
        main_file_path = build_source_dir_path / exe_file_without_extension
        main_file_content = main_file_path.read_text(
            encoding="utf8", errors="surrogateescape"
        )
        if HEADER_NO_CONSOLE not in main_file_content:
            main_file_path.write_text(
                str(HEADER_NO_CONSOLE + main_file_content),
                encoding="utf8",
                errors="surrogateescape",
            )

    return exe_file_path


def make_zip_file(
    file_name: str,
    destination_dir: Union[str, Path],
    project_path: Path,
    app_path: Path,
) -> Path:
    zip_file_name = Path(destination_dir) / file_name
    root_dir = project_path / DEFAULT_DIST_DIR
    print(f"Making zip archive {zip_file_name}")
    shutil.make_archive(
        base_name=str(zip_file_name),
        format="zip",
        root_dir=str(root_dir),
        base_dir=str(app_path.relative_to(root_dir)),
    )
    print("Done.\n")
    return zip_file_name


######################################################################
# utils
######################################################################


def is_valid_python_version(python_version: str) -> bool:
    """
    Check if the given string is a valid Python version string.

    python_version can be anything of the form:
    `x.x.x` where any x may be set to a positive integer.

    Args:
        python_version (str): The string to check.

    Returns:
        bool: True if the string is a valid Python version string, False otherwise.
    """
    #! TODO: remove this function
    return re.match(PYTHON_VERSION_REGEX, python_version) is not None


def unzip(zip_file_path: Path, destination_dir_path: Path) -> None:
    """
    Extract all files from a zip archive to a destination directory.

    Args:
        zip_file_path (Path): The path to the zip archive to extract.
        destination_dir_path (Path): The path to the directory to extract the files to.
    """
    with zipfile.ZipFile(zip_file_path, "r") as zip_file:
        zip_file.extractall(destination_dir_path)


def execute_os_command(command: str, cwd: Union[str, None] = None) -> str:
    """Execute terminal command.

    Args:
        command (str): The command to execute.
        cwd (Union[str, None], optional): The current working directory to execute the command in. Defaults to None.

    Raises:
        RuntimeError: If the command failed to execute.
        Exception: If the command failed to execute.

    Returns:
        str: The output of the command.
    """

    print(f"Executing command {command!r}...")
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.getcwd() if cwd is None else cwd,
    )
    if process.stdout is None:
        raise RuntimeError("Failed to execute command: ", command)

    # Poll process for new output until finished
    while True:
        nextline = process.stdout.readline().decode("UTF-8")
        if nextline == "" and process.poll() is not None:
            break
        sys.stdout.write(nextline)
        sys.stdout.flush()

    output = process.communicate()[0]
    exit_code = process.returncode

    if exit_code == 0:
        print(output)
        print("Done!\n")
        return output.decode("UTF-8")
    else:
        raise Exception(command, exit_code, output)
