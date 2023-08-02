"""py2winapp.py

This script is used to create a Windows executable from a Python script.

TODO:
- make app_dir and exe file name patterns configurable
- add ignore input patterns
- fix: can't install requirement like `requests==2.31.0 ; python_version >= "3.11" and python_version < "4.0"`
- add support for pyproject.toml

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

from genexe.generate_exe import generate_exe
from loguru import logger
from slugify import slugify

from py2winapp.downloader import Dwwnloader

######################################################################
# constants
######################################################################


GETPIPPY_URL = "https://bootstrap.pypa.io/get-pip.py"
GETPIPPY_FILE = "get-pip.py"
PYTHON_URL = "https://www.python.org/ftp/python"

HEADER_NO_CONSOLE = """import sys, os, pathlib
if sys.executable.endswith('pythonw.exe'):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = (pathlib.Path(__file__).parent / 'stderr').open('w')

"""
DEFAULT_IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "py2winapp.py",
    "build.py",
]

DEFAULT_DIST_DIR = "dist3"  #! debug only

DEFAULT_PYDIST_DIR = "python"
DEFAULT_DOWNLOAD_DIR = "downloads"  # ensure this is in .gitignore


######################################################################
# Logging
######################################################################


def setup_logger(log_dir_path: Path) -> None:
    """
    Setup the logger to log to a file and to the console.

    Args:
        log_dir_path (Path): The directory to save the log file to.
    """
    log_file_path = log_dir_path / "py2winapp.log"
    logger.remove(0)
    logger.add(log_file_path, format="{level:10} {message}", level="DEBUG")
    logger.add(
        sys.stderr,
        format="<level>{level:10}: {message}</level>",
        level="INFO",
        colorize=True,
    )


######################################################################
# Build data
######################################################################


@dataclass
class BuildData:
    python_version: str
    project_path: Path
    app_name: str
    app_name_slug: str
    dist_dir_path: Path
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
    python_dir: str
    python_dir_path: Path
    source_dir: str
    source_dir_path: Path
    exe_file_without_extension: str
    exe_file_path: Path
    icon_file_path: Union[Path, None]
    zip_file_path: Union[Path, None]
    download_dir_path: Path


def check_build_data(build_data: BuildData) -> None:
    logger.info("Checking build data")

    errors_count = 0

    # python_version can be anything of the form:
    # `x.x.x` where any x may be set to a positive integer.
    python_version_regex = re.compile(r"^(\d+|x)\.(\d+|x)\.(\d+|x)$")
    if re.match(python_version_regex, build_data.python_version) is None:
        errors_count += 1
        logger.error(
            f"Specified python version `{build_data.python_version}` "
            "does not have the correct format, "
            "it should be of format: `x.x.x` where `x` is a positive number."
        )

    # check project path
    if not build_data.project_path.exists():
        errors_count += 1
        logger.error(f"Project path `{build_data.project_path}` does not exist.")
    elif not build_data.project_path.is_dir():
        errors_count += 1
        logger.error(f"Project path `{build_data.project_path}` is not a directory.")

    # check input source dir
    if not build_data.input_source_dir_path.exists():
        errors_count += 1
        logger.error(
            f"Input source dir `{build_data.input_source_dir_path}` does not exist."
        )
    elif not build_data.input_source_dir_path.is_dir():
        errors_count += 1
        logger.error(
            f"Input source dir `{build_data.input_source_dir_path}` is not a directory."
        )

    # check main file
    if not build_data.main_file_path.exists():
        errors_count += 1
        logger.error(f"Main file `{build_data.main_file_path}` does not exist.")
    elif not build_data.main_file_path.is_file():
        errors_count += 1
        logger.error(f"Main file `{build_data.main_file_path}` is not a file.")
    elif build_data.main_file_path.suffix != ".py":
        errors_count += 1
        logger.error(
            f"Main file `{build_data.main_file_path}` does not have the `.py` extension."
        )

    # check requirements file
    if not build_data.requirements_file_path.exists():
        errors_count += 1
        logger.error(
            f"Requirements file `{build_data.requirements_file_path}` does not exist."
        )
    elif not build_data.requirements_file_path.is_file():
        errors_count += 1
        logger.error(
            f"Requirements file `{build_data.requirements_file_path}` is not a file."
        )

    # check icon file
    if build_data.icon_file_path is not None:
        if not build_data.icon_file_path.exists():
            errors_count += 1
            logger.error(f"Icon file `{build_data.icon_file_path}` does not exist.")
        elif not build_data.icon_file_path.is_file():
            errors_count += 1
            logger.error(f"Icon file `{build_data.icon_file_path}` is not a file.")

    # check download dir
    if not build_data.download_dir_path.exists():
        # make it
        logger.info(f"Creating download dir `{build_data.download_dir_path}`.")
        build_data.download_dir_path.mkdir(parents=True)
    elif not build_data.download_dir_path.is_dir():
        errors_count += 1
        logger.error(
            f"Download dir `{build_data.download_dir_path}` is not a directory."
        )

    # summary
    if errors_count > 0:
        logger.error(
            f"Found {errors_count} error(s) in build data, "
            "please fix them and try again."
        )
        raise ValueError("Found errors in build data.")


def make_build_data(
    python_version: str,
    app_name: Union[str, None],
    input_source_dir: str,
    main_file: str,
    ignore_input: Iterable[str],  #! TODO: add this
    app_dir: Union[str, None],
    show_console: bool,
    requirements_file: str,
    extra_pip_install_args: Iterable[str],
    python_dir: str,
    source_dir: str,
    exe_file: Union[str, None],
    icon_file: Union[str, Path, None],
    make_zip: bool,
) -> BuildData:
    project_path = Path.cwd()  #! TODO: make this a parameter

    if app_name is None:
        app_name = project_path.name
    app_name_slug = slugify(app_name, decimal=False)

    dist_dir_path = project_path / DEFAULT_DIST_DIR

    if app_dir is None:
        app_dir = app_name_slug
    app_dir_path = dist_dir_path / app_dir

    input_source_dir_path = project_path / input_source_dir

    main_file_path = input_source_dir_path / main_file

    requirements_file_path = project_path / requirements_file

    python_dir_path = app_dir_path / python_dir
    source_dir_path = app_dir_path / source_dir

    if icon_file is not None:
        icon_file_path = Path(icon_file)
        if not icon_file_path.is_absolute():
            icon_file_path = project_path / icon_file
    else:
        icon_file_path = None

    download_dir_path = project_path / DEFAULT_DOWNLOAD_DIR
    download_dir_path.mkdir(exist_ok=True)

    if exe_file is None:
        exe_file = app_name_slug
    exe_file = exe_file.strip().lower()
    if not exe_file.endswith(".exe"):
        exe_file += ".exe"
    exe_file_path = app_dir_path / exe_file

    zip_file_path = app_dir_path / f"{exe_file}.zip" if make_zip else None

    return BuildData(
        python_version=python_version,
        project_path=project_path,
        app_name=app_name,
        app_name_slug=app_name_slug,
        dist_dir_path=dist_dir_path,
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
        python_dir=python_dir,
        python_dir_path=python_dir_path,
        source_dir=source_dir,
        source_dir_path=source_dir_path,
        exe_file_without_extension=exe_file,
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
    main_file: str,  # relative to input_source_dir, the main file to run, e.g. `main.py`
    app_name: Union[
        str, None
    ] = None,  # name of the app. If None, use project's directory name
    ignore_input: Iterable[str] = (),  # patterns to ignore in input_dir
    app_dir: Union[
        str, None
    ] = None,  # where to put the app under `dist` directory (relative to project_dir)
    show_console: bool = False,  # show console or not when running the app
    requirements_file: str = "requirements.txt",
    extra_pip_install_args: Iterable[str] = (),  # extra arguments to pip install
    python_dir: str = DEFAULT_PYDIST_DIR,  # where to put python distribution files (relative to app_dir)
    source_dir: str = "",  # where to put source files (relative to app_dir)
    exe_file: Union[
        str, None
    ] = None,  # name of the exe file. If None, use app_name_slug
    icon_file: Union[str, Path, None] = None,  # icon file to use for the app
    make_zip: bool = False,  # make a zip file of the app
) -> BuildData:
    build_data = make_build_data(
        python_version=python_version,
        input_source_dir=input_source_dir,
        main_file=main_file,
        app_name=app_name,
        ignore_input=ignore_input,
        app_dir=app_dir,
        show_console=show_console,
        requirements_file=requirements_file,
        extra_pip_install_args=extra_pip_install_args,
        python_dir=python_dir,
        source_dir=source_dir,
        exe_file=exe_file,
        icon_file=icon_file,
        make_zip=make_zip,
    )

    # setup logging
    setup_logger(log_dir_path=build_data.project_path)

    # check build data
    check_build_data(build_data=build_data)

    # create or clean app directory
    make_app_dir(build_data=build_data)

    # copy source files
    copy_source_files(
        input_source_dir_path=build_data.input_source_dir_path,
        source_dir_path=build_data.source_dir_path,
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
        pydist_dir_path=build_data.python_dir_path,
        build_source_dir_path=build_data.source_dir_path,
    )

    # install pip
    install_pip(pydist_dir_path=build_data.python_dir_path)

    # delete `get_pip.py` from build directory cause it waists more than 2.5MB
    # getpippy_file_path.unlink() #! TODO: chore - romove this line
    (build_data.python_dir_path / GETPIPPY_FILE).unlink()

    # install requirements
    install_requirements_from_file(build_data=build_data)

    # generate exe
    exe_file_path = make_startup_exe(build_data=build_data)

    # make zip file
    if make_zip:
        make_zip_file(build_data=build_data)

    logger.success(f"Done building `{build_data.app_dir_path}`")

    return build_data


######################################################################
# Functions
######################################################################


def make_app_dir(build_data: BuildData) -> None:
    logger.info(f"Creating app directory")
    if build_data.dist_dir_path.is_dir():
        logger.debug(f"Deleting existing dist directory `{build_data.dist_dir_path}`!")
        shutil.rmtree(build_data.dist_dir_path)
    logger.debug(f"Creating app directory `{build_data.app_dir_path}`!")
    build_data.dist_dir_path.mkdir()
    build_data.app_dir_path.mkdir()


def copy_source_files(
    input_source_dir_path: Path,
    source_dir_path: Path,
    build_dir_name: str,
    ignore_patterns: list[str] = [],
) -> None:
    """Copy .py files and others to build folder"""
    logger.info(f"Copying source files")
    ignore_patterns = ignore_patterns or []
    ignore_patterns.append(build_dir_name)
    ignore_patterns += DEFAULT_IGNORE_PATTERNS
    if not source_dir_path.is_dir():
        source_dir_path.mkdir()
    logger.debug(
        f"Copying files from `{input_source_dir_path}` to `{source_dir_path}`!"
    )
    shutil.copytree(
        src=input_source_dir_path,
        dst=source_dir_path,
        ignore=shutil.ignore_patterns(*ignore_patterns),
        dirs_exist_ok=True,
    )


def get_python_dist(build_data: BuildData) -> Path:
    logger.info(f"Downloading python distribution")
    downloader = Dwwnloader(build_data.download_dir_path)
    python_file_name = f"python-{build_data.python_version}-embed-amd64.zip"  # e.g. python-3.9.6-embed-amd64.zip
    downloaded_python_zip_path = downloader.download(
        url=f"{PYTHON_URL}/{build_data.python_version}/{python_file_name}",
        file=python_file_name,
    )
    # extract python zip file to build folder
    logger.debug(
        f"Extracting `{downloaded_python_zip_path}` to `{build_data.python_dir_path}`"
    )
    unzip(
        zip_file_path=downloaded_python_zip_path,
        destination_dir_path=build_data.python_dir_path,
    )
    return downloaded_python_zip_path


def get_getpippy(build_data: BuildData) -> Path:
    logger.info(f"Downloading `get-pip.py`")
    downloader = Dwwnloader(build_data.download_dir_path)
    getpippy_file_path = downloader.download(file=GETPIPPY_FILE, url=GETPIPPY_URL)
    shutil.copy2(getpippy_file_path, build_data.python_dir_path)
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
    logger.info(f"Preparing python distribution for pip installation")

    short_python_version = "".join(python_version.split(".")[:2])  # 3.9.7 -> 39
    pth_file_name = f"python{short_python_version}._pth"  # python39._pth
    pythonzip_file_name = f"python{short_python_version}.zip"  # python39.zip

    pth_file_path = pydist_dir_path / pth_file_name
    pythonzip_file_path = pydist_dir_path / pythonzip_file_name

    logger.debug(f"Generating `{pth_file_path}` with uncommented `import site` line")

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

    pythonzip_dir_path = Path(pythonzip_file_path)
    logger.debug(f"Extracting `{pythonzip_file_path}` to `{pythonzip_dir_path}`")
    pythonzip_file_path = pythonzip_file_path.rename(
        pythonzip_file_path.with_suffix(".temp_zip")
    )
    unzip(pythonzip_file_path, pythonzip_dir_path)
    pythonzip_file_path.unlink()


def install_pip(pydist_dir_path: Path) -> None:
    logger.info(f"Installing `pip`")

    execute_os_command(
        command="python.exe get-pip.py --no-warn-script-location",
        cwd=str(pydist_dir_path),
    )
    if not (pydist_dir_path / "Scripts").exists():
        raise RuntimeError("Can not install `pip` with `get-pip.py`!")


def install_requirements_from_file(build_data: BuildData) -> None:
    """
    Install the modules from requirements.txt file
    - extra_pip_install_args (optional `List[str]`) :
    pass these additional arguments to the pip install command
    """
    logger.info(f"Installing requirements")
    logger.debug(f"Requirements file path: `{build_data.requirements_file_path}`")

    if build_data.extra_pip_install_args:
        extra_args_str = extra_args_str = " " + " ".join(
            build_data.extra_pip_install_args
        )
    else:
        extra_args_str = ""
    scripts_dir_path = build_data.python_dir_path / "Scripts"
    command = (
        "pip3.exe install --no-cache-dir --no-warn-script-location "
        f"-r {str(build_data.requirements_file_path)}{extra_args_str}"
    )
    try:
        execute_os_command(command=command, cwd=str(scripts_dir_path))
        return
    except Exception as e:
        pass
    logger.error(
        f"Failed to install modules from `{build_data.requirements_file_path}`"
    )
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
    logger.info(f"Installing requirements one by one")
    if build_data.extra_pip_install_args:
        extra_args_str = extra_args_str = " " + " ".join(
            build_data.extra_pip_install_args
        )
    else:
        extra_args_str = ""
    scripts_dir_path = build_data.python_dir_path / "Scripts"
    failed_to_install_modules = []
    for module in reqauirements:
        logger.info(f"Installing {module} ...")
        command = (
            "pip3.exe install --no-cache-dir --no-warn-script-location "
            f"{module}{extra_args_str}"
        )
        try:
            execute_os_command(command=command, cwd=str(scripts_dir_path))
        except Exception:
            logger.error(f"FAILED TO INSTALL {module}")
            failed_to_install_modules.append(module)

    if failed_to_install_modules:
        (build_data.app_dir_path / "FAILED_TO_INSTALL_MODULES.txt").write_text(
            "\n".join(failed_to_install_modules), encoding="utf8"
        )
        logger.error(f"Failed to install {len(failed_to_install_modules)} modules")
        logger.error("See FAILED_TO_INSTALL_MODULES.txt for more info")


def make_startup_exe(build_data: BuildData) -> None:
    """Make the startup exe file needed to run the script"""
    logger.info(f"Making startup exe file")

    relative_pydist_dir = build_data.python_dir_path.relative_to(
        build_data.app_dir_path
    )
    relative_source_dir = build_data.source_dir_path.relative_to(
        build_data.app_dir_path
    )
    python_entrypoint = "python.exe" if build_data.show_console else "pythonw.exe"
    logger.debug(f"Python entrypoint: `{python_entrypoint}`")
    command_str = (
        f"{{EXE_DIR}}\\{relative_pydist_dir}\\{python_entrypoint} "
        + f"{{EXE_DIR}}\\{relative_source_dir}\\{build_data.main_file}"
    )
    logger.debug(f"Making startup exe file `{build_data.exe_file_path}`")
    generate_exe(
        target=build_data.exe_file_path,
        command=command_str,
        icon_file=build_data.icon_file_path,
        show_console=build_data.show_console,
    )

    if not build_data.show_console:
        main_file_path = build_data.main_file_path
        main_file_content = main_file_path.read_text(
            encoding="utf8", errors="surrogateescape"
        )
        if HEADER_NO_CONSOLE not in main_file_content:
            main_file_path.write_text(
                str(HEADER_NO_CONSOLE + main_file_content),
                encoding="utf8",
                errors="surrogateescape",
            )


def make_zip_file(build_data: BuildData) -> Path:
    logger.info(f"Making zip archive of the app")

    destination_dir = build_data.dist_dir_path
    zip_file_path = Path(destination_dir) / build_data.app_dir_path.name
    root_dir = build_data.dist_dir_path
    logger.debug(f"Making zip file `{zip_file_path}`")
    shutil.make_archive(
        base_name=str(zip_file_path),
        format="zip",
        root_dir=str(root_dir),
        base_dir=str(build_data.app_dir_path.relative_to(root_dir)),
    )
    return zip_file_path


######################################################################
# utils
######################################################################


def unzip(zip_file_path: Path, destination_dir_path: Path) -> None:
    """
    Extract all files from a zip archive to a destination directory.

    Args:
        zip_file_path (Path): The path to the zip archive to extract.
        destination_dir_path (Path): The path to the directory to extract the files to.
    """
    logger.debug(f"Unzipping {zip_file_path} to {destination_dir_path}...")

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
    logger.debug(f"Executing command {command!r}...")
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
        if nextline:
            # sys.stdout.write(nextline)
            # sys.stdout.flush()
            logger.debug(nextline)

    output = process.communicate()[0].decode("UTF-8")
    exit_code = process.returncode

    if exit_code == 0:
        logger.debug(output)
        return output
    else:
        raise Exception(command, exit_code, output)
