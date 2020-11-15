import pickle
import json
from io import IOBase, SEEK_END
from pathlib import Path
from collections.abc import MutableMapping
from typing import Union, Optional
from enum import Enum, auto
from os import PathLike
from decimal import Decimal


__VERSION__ = "1.0"
# TODO: extension and check
# TODO: pickle user objects
# TODO: tests

IMMUTABLES = (int, str, float, bool, tuple, bytes, complex, frozenset, Decimal)
MUTABLES_WITH_EQ = (list, set, bytearray, dict)


class FileFormat(Enum):
    pickle_human = auto()  # Human readable pickle (v0)
    pickle_binary = auto()  # Binary pickle v4 (Python 3.4)
    json = auto()  # Json dump
    json_pretty = auto()  # Pretty Json dump
    # Add others also to _openflags


_openflags = {
    # r+w with creation and no truncation
    FileFormat.pickle_binary: "ab+",
    FileFormat.pickle_human: "ab+",
    FileFormat.json: "a+",
    FileFormat.json_pretty: "a+",
}


class Autodict(MutableMapping):
    """
    Persistent dict which syncs it's content automatically with a file.

    Nice for application settings with defaults etc.

    Pickle (default) and JSON support.
    JSON will alter keys to strings and may not support some data types or even alter them.

    Nested mutable elements as values are not recommended for track_changes.
    """

    VERSION = __VERSION__

    # General settings below.
    # Inherhit this class with other settings or just reassign them on class level before use.
    default_file_format = FileFormat.pickle_binary

    # Load after class instantiation
    auto_load = True

    # Call save() on destruction
    save_on_del = True

    # Track changes for physical save only if data has been changed.
    # May not be accurate on nested collections or mutables.
    track_changes = True

    # False: Use defaults only if persistent file not found on load
    # True:  Use defaults and update from persistent file if exists
    include_defaults = True

    # Default content
    default_content = {}

    def __init__(self, file: Union[PathLike, str, bytes] = None, file_format: FileFormat = None, **defaults):
        self._file: Optional[Path] = None

        # Keep an open handle on files.
        self._fhandle: Optional[IOBase] = None

        if file_format:
            self.default_file_format = file_format  # Set a local instance copy of desired format

        if file is not None:
            # File path given
            self.file = Path(file)

        # Create default values
        # Use defaults of class
        self.defaults = self.default_content.copy()

        # Update with defaults supplied by kwargs (if given)
        self.defaults.update(defaults)

        # Keep track if data has changed
        self.changed = False

        # Create internal data dict storage based on defaults
        self.data = dict()

        if self.auto_load:
            self.load()

    @property
    def file(self) -> Optional[Path]:
        return self._file

    @file.setter
    def file(self, newfile: Optional[Path]):
        if self._file is newfile:
            # No change
            return

        # Close current open handle
        if self._fhandle:
            self._fhandle.close()
            self._fhandle = None

        # Open file
        if newfile:
            # Check if we have the correct open mode for file type
            if self.default_file_format not in _openflags:
                raise TypeError(f"File mode not found for: {self.default_file_format!s}")

            filemode = _openflags[self.default_file_format]
            self._fhandle = open(newfile, mode=filemode, encoding=None if "b" in filemode else "utf8")

        self._file = newfile

    @property
    def has_mutables(self) -> bool:
        for value in self.data.values():
            # TODO: isinstance should work too.
            if type(value) not in IMMUTABLES:
                return True

        return False  # Found no mutables

    def __getitem__(self, key):
        return self.data[key]

    def __delitem__(self, key):
        del self.data[key]
        if self.track_changes:
            self.changed = True

    def __setitem__(self, key, value):
        if self.track_changes:
            # Do a deeper track for changes

            if key not in self.data:
                # Key-Value is new
                self.changed = True

            if not self.changed:
                # Possibly updated a key-value first time after save. Deep check for a change.
                existing_value = self.data[key]

                if existing_value is value:
                    # Assigned same object. Absolutely not a change.
                    return  # Speed up

                if isinstance(value, (IMMUTABLES, MUTABLES_WITH_EQ)):
                    # New identity of value.
                    # These types allow comparison.
                    self.changed = existing_value != value

                else:
                    # Other type. Comparison not possible.
                    # Just handle as changed data.
                    # TODO: check __eq__?
                    self.changed = True

        # Update internal dict when
        # - track_changes == False
        # - New key
        # - Same value but other value object identity (update reference to new value object)
        self.data[key] = value

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __del__(self):
        if self.save_on_del and self.file:
            self.save(force=True)

        # Close file
        self.file = None

        # Dereference data
        self.data.clear()
        del self.data

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.file}': {self.data!r})"

    def __str__(self):
        # pickle here? No.
        return str(self.data)

    def items(self):
        return self.data.items()

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def load(self, file: Union[PathLike, str, bytes, None] = None):
        if file:
            # Update/set file location
            self.file = Path(file)

        self.data.clear()

        if self.file:
            # Empty file?
            self._fhandle.seek(0, SEEK_END)
            fileempty = self._fhandle.tell() == 0
        else:
            fileempty = True

        if self.include_defaults or self.file is None or fileempty:
            # Set defaults
            self.data.update(self.defaults)

        if self.file and not fileempty:
            self._fhandle.seek(0)

            # Pickle mode
            if self.default_file_format in (FileFormat.pickle_human, FileFormat.pickle_binary):
                self.data.update(pickle.load(file=self._fhandle))

            # Json mode
            elif self.default_file_format in (FileFormat.json, FileFormat.json_pretty):
                self.data.update(json.load(fp=self._fhandle))

            else:
                raise ValueError(f"Unsupported default_file_format: {self.default_file_format!s}")
        self.changed = False

    def save(self, file: Union[PathLike, str, bytes, None] = None, force=False):
        if file:
            # Update/set file location
            self.file = Path(file)

        if self.file is None:
            raise IOError("No file location specified for save.")

        if force or not self.track_changes or (self.track_changes and self.changed):
            # Goto start of file and truncate for fresh write
            self._fhandle.seek(0)
            self._fhandle.truncate()

            # Pickle mode
            if self.default_file_format is FileFormat.pickle_human:
                pickle.dump(self.data, file=self._fhandle, protocol=0)

            elif self.default_file_format is FileFormat.pickle_binary:
                pickle.dump(self.data, file=self._fhandle, protocol=4)

            # Json mode
            elif self.default_file_format is FileFormat.json:
                json.dump(self.data, fp=self._fhandle)

            elif self.default_file_format is FileFormat.json_pretty:
                json.dump(self.data, fp=self._fhandle, indent=4)

            else:
                raise ValueError(f"Unsupported default_file_format: {self.default_file_format!s}")

            self._fhandle.flush()

            self.changed = False
