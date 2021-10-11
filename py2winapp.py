#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import requests
from genexe.generate_exe import generate_exe

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

DEFAULT_PYTHON_DIST_DIR_NAME = "python"


@dataclass
class App:
    path: Path
    exe_file_path: Path
    source_dir_path: Path
    pydist_dir_path: Path
    requirements_file_path: Union[Path, None]


def execute_os_command(command: str, cwd: str = None) -> None:
    """Execute terminal command"""

    print("Running command: ", command)
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.getcwd() if cwd is None else cwd,
    )

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
        return output
    else:
        raise Exception(command, exit_code, output)


def copy_source_files(
    input_dir_path: Path,
    source_dir_path: Path,
    ignore_patterns: list[str] = None,
) -> None:
    """Copy .py files and others to build folder"""
    ignore_patterns = ignore_patterns or []
    ignore_patterns += [
        "__pycache__",
        "*.pyc",
    ]
    if not source_dir_path.is_dir():
        source_dir_path.mkdir()
    print(f"Copying files from `{input_dir_path}` to `{source_dir_path}`!")
    shutil.copytree(
        src=input_dir_path,
        dst=source_dir_path,
        ignore=shutil.ignore_patterns(*ignore_patterns),
        dirs_exist_ok=True,
    )
    print("Files copied!")


def unzip(zip_file_path: Path, destination_dir_path: Path) -> None:
    zip = zipfile.ZipFile(zip_file_path, "r")
    zip.extractall(destination_dir_path)
    zip.close()


def extract_embeded_zip_file_to_pydist_dir(
    embedded_file_path: Path, pydist_dir_path: Path
) -> None:
    """Copy embeded python zip file to build folder"""

    print(f"Extracting `{embedded_file_path}` to `{pydist_dir_path}`")
    unzip(
        zip_file_path=embedded_file_path, destination_dir_path=pydist_dir_path
    )
    print("Zip file extracted!")


def copy_getpippy_to_pydist_dir(
    getpippy_file_path: Path, pydist_dir_path: Path
) -> None:
    """Copy embeded python and get-pip file to build folder"""

    shutil.copy2(getpippy_file_path, pydist_dir_path)
    print(f"File `{getpippy_file_path}` file copied to `{pydist_dir_path}`")


def prepare_for_pip_install(
    python_version: str,
    build_dir_path: Path,
    pydist_dir_path: Path,
) -> None:
    """
    Prepare the extracted embedded python version for pip installation
    - Uncomment 'import site' line from pythonXX._pth file
    - Extract pythonXX.zip zip file to pythonXX.zip folder
      and delete pythonXX.zip zip file
    """

    short_python_version = "".join(
        python_version.split(".")[:2]
    )  # 3.9.7 -> 39
    pth_file_name = f"python{short_python_version}._pth"  # python39._pth
    pythonzip_file_name = f"python{short_python_version}.zip"  # python39.zip

    pth_file_path = pydist_dir_path / pth_file_name
    pythonzip_file_path = pydist_dir_path / pythonzip_file_name

    relative_path_to_source = (
        "." if pydist_dir_path == build_dir_path else ".."
    )  # TODO: remove + build_source_dir_path.name

    pth_file_content = (
        f"{pythonzip_file_name}\n"
        + f"{relative_path_to_source}\n\n"
        + "# Uncomment to run site.main() automatically\n"
        + "import site\n"
    )
    pth_file_path.write_text(pth_file_content, encoding="utf8")
    print(
        f"File `{pth_file_path}` with uncommented `import site` line generated"
    )

    print(f"Extracting `{pythonzip_file_path}`")
    pythonzip_dir_path = Path(pythonzip_file_path)
    pythonzip_file_path = pythonzip_file_path.rename(
        pythonzip_file_path.with_suffix(".temp_zip")
    )
    unzip(pythonzip_file_path, pythonzip_dir_path)
    pythonzip_file_path.unlink()
    print(f"`{pythonzip_dir_path}` created")


def install_pip(pydist_dir_path: Path) -> None:
    print("Installing `pip`")
    execute_os_command(
        command="python.exe get-pip.py --no-warn-script-location",
        cwd=str(pydist_dir_path),
    )
    if not (pydist_dir_path / "Scripts").exists():
        raise RuntimeError("Can not install `pip` with `get-pip.py`!")
    print("`pip` installed")


def install_requirements(
    pydist_dir_path: Path,
    build_dir_path: Path,
    requirements_file_path: Path,
    extra_pip_install_args: list[str] = None,
):
    """
    Install the modules from requirements.txt file
    - extra_pip_install_args (optional `List[str]`) :
    pass these additional arguments to the pip install command
    """

    scripts_dir_path = pydist_dir_path / "Scripts"

    if extra_pip_install_args is not None:
        extra_args_str = " " + " ".join(extra_pip_install_args)
    else:
        extra_args_str = ""

    try:
        cmd = "pip3.exe install --no-cache-dir --no-warn-script-location "
        f"-r {str(requirements_file_path)}{extra_args_str}"
        execute_os_command(command=cmd, cwd=str(scripts_dir_path))
    except Exception:
        print("Installing modules one by one")
        modules = requirements_file_path.read_text().splitlines()
        for module in modules:
            try:
                cmd = "pip3.exe install --no-cache-dir "
                f"--no-warn-script-location {module}{extra_args_str}"
                execute_os_command(command=cmd, cwd=str(scripts_dir_path))
            except Exception:
                print("FAILED TO INSTALL ", module)
                with (build_dir_path / "FAILED_TO_INSTALL_MODULES.txt").open(
                    mode="a"
                ) as f:
                    f.write(module + "\n")


def make_startup_exe(
    main_file_name: str,
    show_console: bool,
    build_dir_path: Path,
    pydist_dir_path: Path,
    build_source_dir_path: Path,
    icon_file_path: Union[Path, None],
) -> Path:
    """Make the startup exe file needed to run the script"""
    print("Making startup exe file")

    relative_pydist_dir = pydist_dir_path.relative_to(build_dir_path)
    relative_source_dir = build_source_dir_path.relative_to(build_dir_path)
    exe_file_path = build_dir_path / Path(main_file_name).with_suffix(".exe")
    python_entrypoint = "python.exe"
    command_str = (
        f"{{EXE_DIR}}\\{relative_pydist_dir}\\{python_entrypoint} "
        + f"{{EXE_DIR}}\\{relative_source_dir}\\{main_file_name}"
    )
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

    print("Exe file generated")

    return exe_file_path


def download_file(
    url: str, local_file_path: Path, chunk_size: int = 128
) -> None:
    """Download streaming a file url to `local_file_path`"""

    r = requests.get(url, stream=True)
    with open(local_file_path, "wb") as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)


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
    else:
        print(f"`get-pip.py` found in `{download_dir_path}`")

    return getpippy_file_path


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
                f"Could not find {embedded_file_name}, "
                "and the download failed"
            )
    else:
        print(f"`{embedded_file_name}` found in `{download_dir_path}`")

    return embedded_file_path


def make_empty_build_dir(build_dir_path: Path) -> None:
    # Delete build folder if it exists
    if build_dir_path.is_dir():
        print(
            f"Existing build directory found, "
            f"removing contents from `{build_dir_path}`"
        )
        shutil.rmtree(build_dir_path)
    build_dir_path.mkdir()


def copy_requirements_file(
    requirements_file_path: Path,
    build_dir_path: Path,
) -> Path:
    build_requirements_file_path = build_dir_path / "requirements.txt"
    if not requirements_file_path.exists():
        raise FileNotFoundError(
            f"No requirements file was found: {requirements_file_path}"
        )
    print(f"Using requirements: `{requirements_file_path}`")
    shutil.copy(src=requirements_file_path, dst=build_requirements_file_path)
    return build_requirements_file_path


def build(
    main_file_name: str,
    python_version: str,
    show_console: bool = False,
    input_dir: Union[str, Path] = None,
    ignore_patterns: list[str] = None,
    requirements_file: Union[str, Path] = None,
    copy_requirements: bool = False,
    build_dir: Union[str, Path] = None,
    icon_file: Union[str, Path] = None,
    download_dir: Union[str, Path] = None,
    pydist_sub_dir_name: str = DEFAULT_PYTHON_DIST_DIR_NAME,
    build_source_sub_dir_name: str = None,
    extra_pip_install_args: list[str] = None,
):
    # process parameters
    if not re.match(PYTHON_VERSION_REGEX, python_version):
        raise ValueError(
            f"Specified python version `{python_version}` "
            "does not have the correct format, "
            "it should be of format: `x.x.x` where `x` is a positive number."
        )

    if input_dir is None:
        input_dir_path = Path.cwd()
    else:
        input_dir_path = Path(input_dir).resolve().absolute()

    if requirements_file is None:
        requirements_file_path = Path.cwd() / "requirements.txt"
    else:
        requirements_file_path = Path(requirements_file).resolve().absolute()

    if build_dir is None:
        build_dir_path = Path.cwd() / "dist"
    else:
        build_dir_path = Path(build_dir).resolve().absolute()

    if icon_file is None:
        icon_file_path = None
    else:
        icon_file_path = Path(icon_file).resolve().absolute()

    if download_dir is None:
        download_dir_path = Path.home() / "Downloads"
    else:
        download_dir_path = Path(download_dir).resolve().absolute()

    if pydist_sub_dir_name is None:
        pydist_dir_path = build_dir_path
    else:
        pydist_dir_path = build_dir_path / pydist_sub_dir_name

    if build_source_sub_dir_name is None:
        build_source_dir_path = build_dir_path
    else:
        build_source_dir_path = build_dir_path / build_source_sub_dir_name

    # all magic goes here
    make_empty_build_dir(build_dir_path=build_dir_path)

    copy_source_files(
        input_dir_path=input_dir_path,
        source_dir_path=build_source_dir_path,
        ignore_patterns=ignore_patterns,
    )

    getpippy_file_path = download_getpippy(download_dir_path=download_dir_path)
    embeded_file_path = download_python_dist(
        download_dir_path=download_dir_path, python_version=python_version
    )
    extract_embeded_zip_file_to_pydist_dir(
        embedded_file_path=embeded_file_path, pydist_dir_path=pydist_dir_path
    )
    copy_getpippy_to_pydist_dir(
        getpippy_file_path=getpippy_file_path, pydist_dir_path=pydist_dir_path
    )

    prepare_for_pip_install(
        python_version=python_version,
        build_dir_path=build_dir_path,
        pydist_dir_path=pydist_dir_path,
    )

    install_pip(pydist_dir_path=pydist_dir_path)

    if copy_requirements:
        copied_requirements_file_path = requirements_file_path
        requirements_file_path = copy_requirements_file(
            requirements_file_path=requirements_file_path,
            build_dir_path=build_dir_path,
        )
    else:
        copied_requirements_file_path = None
    install_requirements(
        build_dir_path=build_dir_path,
        pydist_dir_path=pydist_dir_path,
        requirements_file_path=requirements_file_path,
        extra_pip_install_args=extra_pip_install_args,
    )

    exe_file_path = make_startup_exe(
        main_file_name=main_file_name,
        show_console=show_console,
        build_dir_path=build_dir_path,
        pydist_dir_path=pydist_dir_path,
        build_source_dir_path=build_source_dir_path,
        icon_file_path=icon_file_path,
    )

    print(
        f"\n\nFinished! Folder `{build_dir_path}` "
        "contains your runnable application!\n\n"
    )

    return App(
        path=build_dir_path,
        exe_file_path=exe_file_path,
        source_dir_path=build_source_dir_path,
        pydist_dir_path=pydist_dir_path,
        requirements_file_path=copied_requirements_file_path,
    )
