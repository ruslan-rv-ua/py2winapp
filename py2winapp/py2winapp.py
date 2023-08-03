"""py2winapp.py

This script is used to create a Windows executable from a Python script.

TODO:
- separate build and dist dirs
- make build file structure
- make project path as parameter
- test if source dir is not a app dir
- chore:
    - add docstrings
    - README.md
- add support for pyproject.toml
- make app_dir and exe file name patterns configurable
- add default icon
- suppress `get-exe` output
- x86 Python support
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Union

from genexe.generate_exe import generate_exe
from loguru import logger
from pip_requirements_parser import RequirementsFile
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

DEFAULT_BUILD_DIR = "build"  # ensure this is in .gitignore
DEFAULT_DIST_DIR = "dist"  # ensure this is in .gitignore
DEFAULT_DIST_DIR = "dist3"  #! debug only
DEFAULT_DOWNLOAD_DIR = "downloads"  # ensure this is in .gitignore
DEFAULT_LOG_FILE = "py2winapp.log"

DEFAULT_PYDIST_DIR = "python"


######################################################################
# Logging
######################################################################


def setup_logger() -> int:
    log_file_path = Path.cwd() / DEFAULT_LOG_FILE
    if log_file_path.exists():
        log_file_path.unlink()
    logger.remove(0)
    logger.add(
        log_file_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:10} | {message}",
        level="DEBUG",
        enqueue=True,
    )
    logger.add(
        sys.stderr,
        format="<level>{level:10}: {message}</level>",
        level="INFO",
        colorize=True,
    )
    return 0


######################################################################
# Build data
######################################################################


@dataclass
class BuildData:
    python_version: str
    project_path: Path
    app_name: str
    app_name_slug: str
    input_source_dir: str
    input_source_dir_path: Path
    ignore_input_patterns: List[str]
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
    exe_file: str
    exe_file_path: Path
    icon_file_path: Union[Path, None]
    zip_file_path: Union[Path, None]
    build_dir_path: Path
    dist_dir_path: Path
    download_dir_path: Path


def check_build_data(build_data: BuildData) -> int:
    errors_count = 0

    # python_version can be anything of the form:
    # `x.x.x` where any x may be set to a positive integer.
    python_version_regex = re.compile(r"^(\d+|x)\.(\d+|x)\.(\d+|x)$")
    if re.match(python_version_regex, build_data.python_version) is None:
        errors_count += 1
        logger.error(
            f"Specified python version {build_data.python_version!r} "
            "does not have the correct format, "
            'it should be of format: "x.x.x" where "x" is a positive number.'
        )

    # check project path
    if not build_data.project_path.exists():
        errors_count += 1
        logger.error(f"Project path {build_data.project_path!r} does not exist.")
    elif not build_data.project_path.is_dir():
        errors_count += 1
        logger.error(f"Project path {build_data.project_path!r} is not a directory.")

    # check input source dir
    if not build_data.input_source_dir_path.exists():
        errors_count += 1
        logger.error(
            f"Input source dir {build_data.input_source_dir_path!r} does not exist."
        )
    elif not build_data.input_source_dir_path.is_dir():
        errors_count += 1
        logger.error(
            f"Input source dir {build_data.input_source_dir_path!r} is not a directory."
        )

    # check main file
    if not build_data.main_file_path.exists():
        errors_count += 1
        logger.error(f"Main file {build_data.main_file_path!r} does not exist.")
    elif not build_data.main_file_path.is_file():
        errors_count += 1
        logger.error(f"Main file {build_data.main_file_path!r} is not a file.")
    elif build_data.main_file_path.suffix != ".py":
        errors_count += 1
        logger.error(
            f"Main file {build_data.main_file_path!r} does not have the `.py` extension."
        )

    # check requirements file
    if not build_data.requirements_file_path.exists():
        errors_count += 1
        logger.error(
            f"Requirements file {build_data.requirements_file_path!r} does not exist."
        )
    elif not build_data.requirements_file_path.is_file():
        errors_count += 1
        logger.error(
            f"Requirements file {build_data.requirements_file_path!r} is not a file."
        )
    else:
        req_checker = RequirementsFile.from_file(str(build_data.requirements_file_path))
        if req_checker.invalid_lines:
            for line in req_checker.invalid_lines:
                errors_count += 1
                logger.error(
                    f"Error in requirements file: {line.filename}:{line.line_number}"
                )
                logger.error(line.error_message)

    # check icon file
    if build_data.icon_file_path is not None:
        if not build_data.icon_file_path.exists():
            errors_count += 1
            logger.error(f"Icon file {build_data.icon_file_path!r} does not exist.")
        elif not build_data.icon_file_path.is_file():
            errors_count += 1
            logger.error(f"Icon file {build_data.icon_file_path!r} is not a file.")

    return errors_count


def log_build_data(build_data: BuildData) -> None:
    # debug build data, all attributes of build data are sorted alphabetically
    data_str = "\n".join(
        f"{attr:>22}: {value!r}" for attr, value in sorted(vars(build_data).items())
    )
    logger.debug(f"Build data:\n{data_str}")


def make_build_data(
    python_version: Union[str, None],
    app_name: Union[str, None],
    input_source_dir: str,
    main_file: str,
    ignore_input_patterns: List[str],
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
    # Python version
    if python_version is None:
        # user current interpreter's version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        logger.info(
            f"Python version not specified, using current interpreter's version: {python_version!r}"
        )

    project_path = Path.cwd()

    build_dir_path = project_path / DEFAULT_BUILD_DIR
    dist_dir_path = project_path / DEFAULT_DIST_DIR
    download_dir_path = project_path / DEFAULT_DOWNLOAD_DIR

    if app_name is None:
        app_name = project_path.name
        logger.info(f"App name not specified, using project name: `{app_name}`.")
    app_name_slug = slugify(app_name)

    if app_dir is None:
        app_dir = app_name_slug
        logger.debug(f"App dir not specified, using app name slug: {app_dir!r} ")
    app_dir_path = build_dir_path / app_dir

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

    if exe_file is None:
        exe_file = f"{app_name_slug}.exe"
        logger.info(
            f"Executable file name not specified, using app name slug: {exe_file!r}."
        )
    else:
        exe_file = exe_file.strip().lower()
        if not exe_file.endswith(".exe"):
            exe_file += ".exe"
    exe_file_path = app_dir_path / exe_file

    zip_file_path = dist_dir_path / f"{app_dir}" if make_zip else None

    return BuildData(
        python_version=python_version,
        project_path=project_path,
        app_name=app_name,
        app_name_slug=app_name_slug,
        input_source_dir=input_source_dir,
        input_source_dir_path=input_source_dir_path,
        ignore_input_patterns=list(ignore_input_patterns),
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
        exe_file=exe_file,
        exe_file_path=exe_file_path,
        icon_file_path=icon_file_path,
        zip_file_path=zip_file_path,
        build_dir_path=build_dir_path,
        dist_dir_path=dist_dir_path,
        download_dir_path=download_dir_path,
    )


######################################################################
# build
######################################################################


def build(
    input_source_dir: str,  # where the source code is
    main_file: str,  # relative to input_source_dir, the main file to run, e.g. `main.py`
    python_version: Union[
        str, None
    ] = None,  # python version to use. If None, use current interpreter's version
    app_name: Union[
        str, None
    ] = None,  # name of the app. If None, use project's directory name
    ignore_input_patterns: Iterable[str] = [],  # patterns to ignore in input_dir
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
    logger.info("Gethering build data...")
    build_data = make_build_data(
        python_version=python_version,
        input_source_dir=input_source_dir,
        main_file=main_file,
        app_name=app_name,
        ignore_input_patterns=list(ignore_input_patterns),
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
    log_build_data(build_data=build_data)

    errors_count = 0

    logger.info("Checking build data...")
    errors_count += check_build_data(build_data=build_data)

    logger.info("Creating app directory...")
    create_files_infrastructure(build_data=build_data)

    logger.info("Copying source files...")
    copy_source_files(build_data=build_data)

    logger.info("Getting python distribution...")
    get_python_dist(build_data=build_data)

    logger.info("Getting pip...")
    get_getpippy(build_data=build_data)

    logger.info("Installing pip...")
    prepare_for_pip_install(build_data=build_data)
    install_pip(pydist_dir_path=build_data.python_dir_path)

    # delete `get_pip.py` from build directory cause it waists more than 2.5MB
    (build_data.python_dir_path / GETPIPPY_FILE).unlink()

    logger.info("Installing requirements...")
    errors_count += install_requirements_txt_file(build_data=build_data)

    logger.info("Generating startup executable...")
    make_startup_exe(build_data=build_data)

    if make_zip:
        logger.info("Making zip file...")
        make_zip_file(build_data=build_data)

    if errors_count > 0:
        logger.critical(f"Build failed with {errors_count} errors!")
        logger.critical("Fix the errors and try again.")
        logger.critical(f"Check the log {DEFAULT_LOG_FILE!r} for more details.")
        sys.exit(1)
    else:
        logger.success(f"Build succeeded!")

    return build_data


######################################################################
# Functions
######################################################################


def create_files_infrastructure(build_data: BuildData) -> None:
    build_data.build_dir_path.mkdir(exist_ok=True)
    build_data.dist_dir_path.mkdir(exist_ok=True)
    build_data.download_dir_path.mkdir(exist_ok=True)

    logger.debug(f"Creating app directory {build_data.app_dir_path!r}")
    build_data.app_dir_path.mkdir(exist_ok=True)
    # clean app directory
    for file_path in build_data.app_dir_path.iterdir():
        if file_path.is_file():
            file_path.unlink()
        elif file_path.is_dir():
            shutil.rmtree(file_path)


def copy_source_files(build_data: BuildData) -> None:
    ignore_patterns = build_data.ignore_input_patterns
    ignore_patterns.append(build_data.app_dir)
    ignore_patterns += DEFAULT_IGNORE_PATTERNS
    if not build_data.source_dir_path.is_dir():
        build_data.source_dir_path.mkdir()
    logger.debug(
        f"Copying files from {build_data.input_source_dir_path!r} to {build_data.source_dir_path!r}"
    )
    shutil.copytree(
        src=build_data.input_source_dir_path,
        dst=build_data.source_dir_path,
        ignore=shutil.ignore_patterns(*ignore_patterns),
        dirs_exist_ok=True,
    )


def get_python_dist(build_data: BuildData) -> None:
    # download python zip file
    downloader = Dwwnloader(build_data.download_dir_path)
    python_file_name = f"python-{build_data.python_version}-embed-amd64.zip"  # e.g. python-3.9.6-embed-amd64.zip
    downloaded_python_zip_path = downloader.download(
        url=f"{PYTHON_URL}/{build_data.python_version}/{python_file_name}",
        file=python_file_name,
    )

    # extract python zip file to build folder
    logger.debug(
        f"Extracting {downloaded_python_zip_path!r} to {build_data.python_dir_path!r}"
    )
    unzip(
        zip_file_path=downloaded_python_zip_path,
        destination_dir_path=build_data.python_dir_path,
    )


def get_getpippy(build_data: BuildData) -> None:
    """
    Downloads `get-pip.py` and copies it to the python distribution directory.

    Args:
        build_data (BuildData): The build data object.

    Returns:
        Path: The path to the `get-pip.py` file.
    """
    # download `get-pip.py`
    downloader = Dwwnloader(build_data.download_dir_path)
    getpippy_file_path = downloader.download(file=GETPIPPY_FILE, url=GETPIPPY_URL)

    # copy `get-pip.py` to python distribution directory
    shutil.copy2(getpippy_file_path, build_data.python_dir_path)


def prepare_for_pip_install(build_data: BuildData) -> None:
    """
    Prepare the extracted embedded python version for pip installation:
    - Uncomment `import site` line from `pythonXX._pth` file
    - Extract `pythonXX.zip` zip file to `pythonXX.zip` folder
    - delete `pythonXX.zip` zip file

    Args:
        build_data (BuildData): The build data object.

    Returns:
        None
    """
    short_python_version = "".join(
        build_data.python_version.split(".")[:2]
    )  # "3.9.7" -> "39"
    pth_file = f"python{short_python_version}._pth"  # python39._pth
    pythonzip_file = f"python{short_python_version}.zip"  # python39.zip

    pth_file_path = build_data.python_dir_path / pth_file
    pythonzip_file_path = build_data.python_dir_path / pythonzip_file

    logger.debug(f"Generating {pth_file_path!r} with uncommented `import site` line")

    if build_data.python_dir_path == build_data.app_dir_path:
        relative_path_to_source = "."
    else:
        relative_path_to_source = ".."
    relative_path_to_source += f"\\{build_data.source_dir_path.name}"

    pth_file_content = (
        f"{pythonzip_file}\n"
        + f"{relative_path_to_source}\n\n"
        + "# Uncomment to run site.main() automatically\n"
        + "import site\n"
    )
    pth_file_path.write_text(pth_file_content, encoding="utf8")

    pythonzip_dir_path = Path(pythonzip_file_path)
    logger.debug(f"Extracting {pythonzip_file_path!r} to {pythonzip_dir_path!r}")
    pythonzip_file_path = pythonzip_file_path.rename(
        pythonzip_file_path.with_suffix(".temp_zip")
    )
    unzip(pythonzip_file_path, pythonzip_dir_path)
    pythonzip_file_path.unlink()


def install_pip(pydist_dir_path: Path) -> None:
    execute_os_command(
        command="python.exe get-pip.py --no-warn-script-location",
        cwd=str(pydist_dir_path),
    )
    if not (pydist_dir_path / "Scripts").exists():
        raise RuntimeError("Can not install `pip` with `get-pip.py`!")


def install_requirements_txt_file(build_data: BuildData) -> int:
    logger.debug(f"Requirements file path: {build_data.requirements_file_path!r}")

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
        return 0
    except Exception as e:
        pass
    logger.warning(
        f"Failed to install requirements from {build_data.requirements_file_path!r}. "
        "Trying to install requirements one by one ..."
    )
    return install_requirements_txt_1by1(build_data)


def install_requirements_txt_1by1(build_data: BuildData) -> int:
    requirements = build_data.requirements_file_path.read_text().splitlines()
    if build_data.extra_pip_install_args:
        extra_args_str = extra_args_str = " " + " ".join(
            build_data.extra_pip_install_args
        )
    else:
        extra_args_str = ""
    scripts_dir_path = build_data.python_dir_path / "Scripts"
    failed_to_install_modules = []
    for line in requirements:
        module = line.strip()
        if not module or module.startswith("#"):
            continue
        command = (
            "pip3.exe install --no-cache-dir --no-warn-script-location "
            f"{module}{extra_args_str}"
        )
        try:
            execute_os_command(command=command, cwd=str(scripts_dir_path))
        except Exception:
            logger.error(f"FAILED TO INSTALL {module!r}")
            failed_to_install_modules.append(module)

    if failed_to_install_modules:
        (build_data.app_dir_path / "FAILED_TO_INSTALL_MODULES.txt").write_text(
            "\n".join(failed_to_install_modules), encoding="utf8"
        )
        logger.error(f"Failed to install {len(failed_to_install_modules)} modules")
        logger.error("See FAILED_TO_INSTALL_MODULES.txt for more info")
        return len(failed_to_install_modules)
    return 0


def make_startup_exe(build_data: BuildData) -> None:
    relative_pydist_dir = build_data.python_dir_path.relative_to(
        build_data.app_dir_path
    )
    relative_source_dir = build_data.source_dir_path.relative_to(
        build_data.app_dir_path
    )
    python_entrypoint = "python.exe" if build_data.show_console else "pythonw.exe"
    logger.debug(f"Python entrypoint: {python_entrypoint!r}")
    command_str = (
        f"{{EXE_DIR}}\\{relative_pydist_dir}\\{python_entrypoint} "
        + f"{{EXE_DIR}}\\{relative_source_dir}\\{build_data.main_file}"
    )
    logger.debug(f"Making startup exe file {build_data.exe_file_path!r}")
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


def make_zip_file(build_data: BuildData) -> None:
    logger.debug(f"Making zip file {build_data.zip_file_path!r}")
    root_dir = build_data.build_dir_path
    shutil.make_archive(
        base_name=str(build_data.zip_file_path),
        format="zip",
        root_dir=str(root_dir),
        base_dir=str(build_data.app_dir_path.relative_to(root_dir)),
    )


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
    logger.debug(f"Unzipping {zip_file_path!r} to {destination_dir_path!r}...")

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
            logger.debug(nextline.strip())

    output = process.communicate()[0].decode("UTF-8")
    exit_code = process.returncode

    if exit_code == 0:
        logger.debug(output)
        return output
    else:
        raise Exception(command, exit_code, output)


setup_logger()
