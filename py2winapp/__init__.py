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

######################################################################
# metadata
######################################################################

__app_name__ = "py2winapp"
__version__ = "0.1.0"
__description__ = "Python to Windows Application"
__author__ = "Ruslan Iskov"


######################################################################
# constants
######################################################################

# python_version can be anything of the form:
# `x.x.x` where any x may be set to a positive integer.
PYTHON_VERSION_REGEX = re.compile(r"^(\d+|x)\.(\d+|x)\.(\d+|x)$")

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
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

DEFAULT_BUILD_DIR = "dist"
DEFAULT_PYDIST_DIR: str = "pydist"


######################################################################
# Build data
######################################################################


@dataclass
class BuildData:
    project_path: Path
    build_path: Path
    exe_path: Path
    source_path: Path
    python_path: Path
    requirements_path: Path


######################################################################
# build
######################################################################


def build(
    input_dir: str,  # where the source code is
    python_version: str,  # python version to use
    main_file_name: str,  # main file name
    ignore_input: Iterable[str] = (),  # patterns to ignore in input_dir
    show_console: bool = False,  # show console or not when running the app
    requirements_file: str = "requirements.txt",  # requirements.txt or pyproject.toml
    app_dir: str = "dist",  # where to put the app
    python_subdir: str = DEFAULT_PYDIST_DIR,  # where to put python distribution files (relative to app_dir)
    source_subdir: str = "",  # where to put source files (relative to app_dir)
    exe_file_name_without_extension: Union[
        str, None
    ] = None,  # name of the exe file without extension. If None, use the name of the main file
    icon_file: Union[str, Path, None] = None,  # icon file to use for the app
    make_zip: bool = False,  # make a zip file of the app
    download_dir: Union[
        str, Path, None
    ] = None,  # where to download python distribution files. If None, use `downloads` in the user's home directory
    extra_pip_install_args: Iterable[str] = (),  # extra arguments to pip install
) -> BuildData:
    # process parameters
    if not re.match(PYTHON_VERSION_REGEX, python_version):
        raise ValueError(
            f"Specified python version `{python_version}` "
            "does not have the correct format, "
            "it should be of format: `x.x.x` where `x` is a positive number."
        )
    project_path = Path(__file__).parent
    input_dir_path = project_path / input_dir
    requirements_file_path = project_path / requirements_file
    app_dir_path = project_path / app_dir
    python_subdir_path = app_dir_path / python_subdir
    source_subdir_path = app_dir_path / source_subdir
    if icon_file is None:
        icon_file_path = None
    else:
        icon_file_path = Path(icon_file).resolve().absolute()
    if download_dir is None:
        download_dir_path = Path.home() / "Downloads"
    else:
        download_dir_path = Path(download_dir).resolve().absolute()

    # all magic happens here...

    # create or clean build directory
    make_empty_build_dir(build_dir_path=app_dir_path)

    # copy source files
    copy_source_files(
        input_dir_path=input_dir_path,
        source_dir_path=source_subdir_path,
        build_dir_name=app_dir_path.name,
        ignore_patterns=list(ignore_input),
    )

    # download python embedded distribution files and extract them to the build directory
    embedded_python_zip_file_path = download_python_dist(
        download_dir_path=download_dir_path, python_version=python_version
    )
    extract_python_dist(
        embedded_python_zip_file_path=embedded_python_zip_file_path,
        pydist_dir_path=python_subdir_path,
    )

    # download `get_pip.py` and copy it to build directory
    getpippy_file_path = download_getpippy(download_dir_path=download_dir_path)
    copy_getpippy_to_pydist_dir(
        getpippy_file_path=getpippy_file_path,
        pydist_dir_path=python_subdir_path,
    )

    # prepare for pip install
    prepare_for_pip_install(
        python_version=python_version,
        build_dir_path=app_dir_path,
        pydist_dir_path=python_subdir_path,
        build_source_dir_path=source_subdir_path,
    )

    # install pip
    install_pip(pydist_dir_path=python_subdir_path)

    # install requirements
    install_requirements(
        build_dir_path=app_dir_path,
        pydist_dir_path=python_subdir_path,
        requirements_file_path=requirements_file_path,
        extra_pip_install_args=list(extra_pip_install_args),
    )

    # generate exe
    exe_file_path = make_startup_exe(
        main_file_name=main_file_name,
        show_console=show_console,
        build_dir_path=app_dir_path,
        pydist_dir_path=python_subdir_path,
        build_source_dir_path=source_subdir_path,
        icon_file_path=icon_file_path,
    )

    # make zip file
    # file_name: str, destination_dir: Union[str, Path, None] = None
    if make_zip:
        make_zip_file(
            file_name=app_dir_path.name,
            destination_dir=app_dir_path.parent,
            project_path=project_path,
            build_path=app_dir_path,
        )

    print(
        f"\nBuild done! Folder `{app_dir_path}` "
        "contains your runnable application!\n"
    )

    # return build data
    return BuildData(
        project_path=project_path,
        build_path=app_dir_path,
        exe_path=exe_file_path,
        source_path=source_subdir_path,
        python_path=python_subdir_path,
        requirements_path=requirements_file_path,
    )


######################################################################
# Functions
######################################################################


def make_empty_build_dir(build_dir_path: Path) -> None:
    """Create or clean build directory."""
    if build_dir_path.is_dir():
        print(
            f"Existing build directory found, "
            f"removing contents from `{build_dir_path}`"
        )
        shutil.rmtree(build_dir_path)
        print("Done!\n")
    build_dir_path.mkdir()


def copy_source_files(
    input_dir_path: Path,
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
    print(f"Copying files from `{input_dir_path}` to `{source_dir_path}`!")
    shutil.copytree(
        src=input_dir_path,
        dst=source_dir_path,
        ignore=shutil.ignore_patterns(*ignore_patterns),
        dirs_exist_ok=True,
    )
    print("Done!\n")


def download_python_dist(download_dir_path: Path, python_version: str):
    embedded_file_name = f"python-{python_version}-embed-amd64.zip"
    embedded_file_path = download_dir_path / embedded_file_name
    if not embedded_file_path.is_file():
        print(
            f"`{embedded_file_name}` not found in `{download_dir_path}`, "
            "attempting to download it."
        )
        download_file(
            url=f"{PYTHON_URL}/{python_version}/{embedded_file_name}",
            local_file_path=embedded_file_path,
        )
        if not embedded_file_path.is_file():
            raise RuntimeError(
                f"Could not find {embedded_file_name}, " "and the download failed"
            )
        print("Done!\n")
    else:
        print(f"`{embedded_file_name}` found in `{download_dir_path}`")

    return embedded_file_path


def extract_python_dist(
    embedded_python_zip_file_path: Path, pydist_dir_path: Path
) -> None:
    """Extract embedded python zip file to build folder"""
    print(f"Extracting `{embedded_python_zip_file_path}` to `{pydist_dir_path}`")
    unzip(
        zip_file_path=embedded_python_zip_file_path,
        destination_dir_path=pydist_dir_path,
    )
    print("Done!\n")


def download_getpippy(download_dir_path: Path) -> Path:
    getpippy_file_path = download_dir_path / "get-pip.py"
    if not getpippy_file_path.exists():
        print(
            f"`get-pip.py` not found in `{download_dir_path}`, "
            "attempting to download it"
        )
        download_file(url=GET_PIP_URL, local_file_path=getpippy_file_path)
        if not getpippy_file_path.exists():
            raise RuntimeError(
                f"Could not find `get-pip.py` in {download_dir_path} "
                "and the download failed"
            )
        print("Done!\n")
    else:
        print(f"`get-pip.py` found in `{download_dir_path}`\n")

    return getpippy_file_path


def copy_getpippy_to_pydist_dir(
    getpippy_file_path: Path, pydist_dir_path: Path
) -> None:
    """Copy `get-pip.py` file to build folder"""
    print(f"Coping `{getpippy_file_path}` file to `{pydist_dir_path}`")
    shutil.copy2(getpippy_file_path, pydist_dir_path)
    print("Done!\n")


def prepare_for_pip_install(
    python_version: str,
    build_dir_path: Path,
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

    if pydist_dir_path == build_dir_path:
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


def install_requirements(
    pydist_dir_path: Path,
    build_dir_path: Path,
    requirements_file_path: Path,
    extra_pip_install_args: list[str],
):
    """
    Install the modules from requirements.txt file
    - extra_pip_install_args (optional `List[str]`) :
    pass these additional arguments to the pip install command
    """

    print("Installing requirements")

    scripts_dir_path = pydist_dir_path / "Scripts"

    if extra_pip_install_args:
        extra_args_str = " " + " ".join(extra_pip_install_args)
    else:
        extra_args_str = ""

    try:
        cmd = (
            "pip3.exe install --no-cache-dir --no-warn-script-location "
            + f"-r {str(requirements_file_path)}{extra_args_str}"
        )
        execute_os_command(command=cmd, cwd=str(scripts_dir_path))
        print("Done!\n")
    except Exception:
        print("Installing modules one by one")
        modules = requirements_file_path.read_text().splitlines()
        for module in modules:
            try:
                print(f"Installing {module} ...", end="", flush=True)
                cmd = "pip3.exe install --no-cache-dir "
                f"--no-warn-script-location {module}{extra_args_str}"
                execute_os_command(command=cmd, cwd=str(scripts_dir_path))
                print("done")
            except Exception:
                print("FAILED TO INSTALL ", module)
                with (build_dir_path / "FAILED_TO_INSTALL_MODULES.txt").open(
                    mode="a"
                ) as f:
                    f.write(module + "\n")
            print("\n")


def make_startup_exe(
    main_file_name: str,
    show_console: bool,
    build_dir_path: Path,
    pydist_dir_path: Path,
    build_source_dir_path: Path,
    icon_file_path: Union[Path, None],
) -> Path:
    """Make the startup exe file needed to run the script"""

    relative_pydist_dir = pydist_dir_path.relative_to(build_dir_path)
    relative_source_dir = build_source_dir_path.relative_to(build_dir_path)
    exe_file_path = build_dir_path / Path(main_file_name).with_suffix(".exe")
    python_entrypoint = "python.exe"
    command_str = (
        f"{{EXE_DIR}}\\{relative_pydist_dir}\\{python_entrypoint} "
        + f"{{EXE_DIR}}\\{relative_source_dir}\\{main_file_name}"
    )
    print(f"Making startup exe file `{exe_file_path}`")
    generate_exe(
        target=exe_file_path,
        command=command_str,
        icon_file=icon_file_path,
        show_console=show_console,
    )

    if not show_console:
        main_file_path = build_source_dir_path / main_file_name
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
    build_path: Path,
) -> Path:
    zip_file_path = Path(destination_dir) / file_name
    print(f"Making zip archive {zip_file_path}")
    shutil.make_archive(
        base_name=str(zip_file_path),
        format="zip",
        root_dir=str(project_path),
        base_dir=str(build_path.relative_to(project_path)),
    )
    print("Done.\n")
    return zip_file_path


######################################################################
# utils
######################################################################


def download_file(url: str, local_file_path: Path, chunk_size: int = 128) -> None:
    """Download streaming a file url to `local_file_path`"""

    r = requests.get(url, stream=True)
    with open(local_file_path, "wb") as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)


def unzip(zip_file_path: Path, destination_dir_path: Path) -> None:
    with zipfile.ZipFile(zip_file_path, "r") as zip_file:
        zip_file.extractall(destination_dir_path)


def execute_os_command(command: str, cwd: Union[str, None] = None) -> str:
    """Execute terminal command"""

    print("Running command: ", command)
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
