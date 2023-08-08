import struct
from pathlib import Path
from typing import Any, BinaryIO, List, Optional, Tuple

import win32api
from loguru import logger

###############################################################################
# generate exe
###############################################################################

SCRIPT_DIR = Path(__file__).parent.absolute().resolve()
EXE_TEMPLATE_FILE = SCRIPT_DIR / "genexe_template"
MAX_CMD_LENGTH = 259
REPLACE_SIGNATURE = (b"X" * MAX_CMD_LENGTH) + b"1"


def generate_exe(
    target: Path,
    command: str,
    icon_file: Optional[Path] = None,
    show_console: bool = True,
):
    target = target.absolute().resolve()
    if target == EXE_TEMPLATE_FILE:
        raise RuntimeError(
            "Cannot overwrite the source EXE_TEMPLATE_FILE file! "
            "Pick a different target executable name."
        )
    with open(EXE_TEMPLATE_FILE, "rb") as f:
        data = f.read()
    if len(command) > MAX_CMD_LENGTH:
        logger.warning(
            f"Length of command is {len(command)} "
            "and is longer than {MAX_CMD_LENGTH} characters. "
            f"Will be truncated."
        )
        command = command[:MAX_CMD_LENGTH]
        logger.debug(f"Truncated command: {command}")
    else:
        command = command + "\0" * (MAX_CMD_LENGTH - len(command))
    assert len(command) == MAX_CMD_LENGTH
    msg = command + ("1" if show_console else "0")
    byte_encoded_string = msg.encode("ascii")
    data = data.replace(REPLACE_SIGNATURE, byte_encoded_string)
    with open(target, "wb") as f:
        f.write(data)
    if icon_file is not None:
        icon_file = Path(icon_file).absolute().resolve()
        add_icon_to_exe(target_exe_file=target, source_icon_file=icon_file)


###############################################################################
# add icon to exe
###############################################################################

# Documentation on struct specifications and their use can be found here:
# https://web.archive.org/web/20160531004250/https://msdn.microsoft.com/en-us/library/ms997538.aspx
ICONDIRHEADER = (("idReserved", "idType", "idCount"), "hhh")
ICONDIRENTRY = (
    (
        "bWidth",
        "bHeight",
        "bColorCount",
        "bReserved",
        "wPlanes",
        "wBitCount",
        "dwBytesInRes",
        "dwImageOffset",
    ),
    "bbbbhhii",
)
GRPICONDIRENTRY = (
    (
        "bWidth",
        "bHeight",
        "bColorCount",
        "bReserved",
        "wPlanes",
        "wBitCount",
        "dwBytesInRes",
        "nID",
    ),
    "bbbbhhih",
)
RT_ICON = 3
RT_GROUP_ICON = 14


class DataStruct(object):
    """General class for handling data structures within a file"""

    def __init__(
        self,
        dtype: Tuple[Tuple[str, ...], str],
        input_stream: Optional[BinaryIO] = None,
    ):
        self.__dict__["_field_names"] = dtype[0]
        self._data_types = dtype[1]
        assert len(self._field_names) == len(self._data_types)
        self._indices = {}
        for i, name in enumerate(self._field_names):
            self._indices[name] = i
        self._size = struct.calcsize(self._data_types)
        self._data = list(
            struct.unpack(
                self._data_types,
                bytearray(self._size)
                if input_stream is None
                else input_stream.read(self._size),
            )
        )

    def __getattr__(self, name: str) -> Any:
        if name in self._field_names:
            return self._data[self._indices[name]]
        return self.__dict__[name]

    def __setattr__(self, name: str, value: Any):
        if name in self._field_names:
            self._data[self._indices[name]] = value
        else:
            self.__dict__[name] = value

    def get_data(self) -> bytes:
        return struct.pack(self._data_types, *self._data)

    def copy(self, data_struct: "DataStruct"):
        for field_name in data_struct._field_names:
            if field_name in self._field_names:
                setattr(self, field_name, getattr(data_struct, field_name))


class Icon(object):
    """Class to extract the relevant data from a .ico file"""

    def __init__(self, file_name: Path):
        with open(str(file_name), "rb") as f:
            self._header = DataStruct(dtype=ICONDIRHEADER, input_stream=f)
            self._dir_entries = [
                DataStruct(dtype=ICONDIRENTRY, input_stream=f)
                for _ in range(self._header.idCount)
            ]
            self._icon_data: List[bytes] = []
            for entry in self._dir_entries:
                f.seek(entry.dwImageOffset, 0)
                self._icon_data.append(f.read(entry.dwBytesInRes))

    def get_header_and_group_icon_dir_data(self) -> bytes:
        data = self._header.get_data()
        for i, dir_entry in enumerate(self._dir_entries):
            icon_dir_entry = DataStruct(dtype=GRPICONDIRENTRY)
            icon_dir_entry.copy(data_struct=dir_entry)
            icon_dir_entry.nID = i + 1
            data += icon_dir_entry.get_data()
        return data

    def get_icon_data(self) -> List[bytes]:
        return self._icon_data


def add_icon_to_exe(source_icon_file: Path, target_exe_file: Path):
    logger.debug(f"Adding icon to {target_exe_file!r}")
    logger.debug(f"Icon file: {source_icon_file!r}")
    target_exe_file = target_exe_file.absolute().resolve()
    if not target_exe_file.is_file():
        raise FileNotFoundError(
            "The target executable file could not be found or is not a valid file: "
            f"{target_exe_file}"
        )
    source_icon_file = source_icon_file.absolute().resolve()
    if not source_icon_file.is_file():
        raise FileNotFoundError(
            "The icon file could not be found or is not a valid file: "
            f"{source_icon_file}"
        )
    icon = Icon(file_name=source_icon_file)
    ur_handle = win32api.BeginUpdateResource(str(target_exe_file), 0)
    win32api.UpdateResource(
        ur_handle, RT_GROUP_ICON, 0, icon.get_header_and_group_icon_dir_data()
    )
    for i, icon_data in enumerate(icon.get_icon_data()):
        win32api.UpdateResource(ur_handle, RT_ICON, i + 1, icon_data)
    win32api.EndUpdateResource(ur_handle, 0)
