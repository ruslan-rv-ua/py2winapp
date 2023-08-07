"""Convert a Python script into a Windows application.

Usage:
    To use this module, simply import the `build` function from the `py2winapp` module
    and call it with the appropriate arguments.

Example:
    ```
    from py2winapp import build
    build(
        python_version="3.8.5",
        source_dir="src",
        requirements_file="requirements_prod.txt"
    )
    ```
"""
from .py2winapp import build  # noqa

__app_name__ = "py2winapp"
__version__ = "0.1.0"
__description__ = "Make runnable apps from your python scripts!"
__author__ = "Ruslan Iskov"
