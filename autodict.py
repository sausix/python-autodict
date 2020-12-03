# -*- coding: utf-8 -*-

import pickle
import json
from io import SEEK_END
from collections.abc import MutableMapping
from typing import Union, Optional
from enum import Enum, auto
from os import PathLike
from decimal import Decimal
import pathlib
import sys


__VERSION__ = "1.2"
__AUTHOR__ = "Adrian Sausenthaler"
__SOURCE__ = "https://github.com/sausix/python-autodict"

# TODO: tests
# TODO: nested autodicts
# TODO: file extenstions
# TODO: subclass name matching


class FileFormat(Enum):
    pickle_human = auto()  # Human readable pickle (v0)
    pickle_binary = auto()  # Binary pickle v4 (Python 3.4)
    json = auto()  # Json dump
    json_pretty = auto()  # Pretty Json dump
    # Add others also to _openflags

IMMUTABLES = (int, str, float, bool, tuple, bytes, complex, frozenset, Decimal)
MUTABLES_WITH_EQ = (list, set, bytearray, dict)

# These need extra attention on autosave during interpreter shutdown
_DANGEROUS_OBJECT_PICKLE_FORMATS = (FileFormat.pickle_binary, )

_openflags = {
    # All r+w with creation and no truncation
    FileFormat.pickle_binary: "ab+",
    FileFormat.pickle_human: "ab+",
    FileFormat.json: "a+",
    FileFormat.json_pretty: "a+",
}


def _cast(value, totype):
    cast = totype(value)
    return cast


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

    # Create parent paths
    auto_mkdir = True

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

    # Expand ~ to HOME
    expand_home = True

    # Try to keep non-string datatypes by casting from string
    auto_cast = False

    # TODO: File extensions
    # File extension
    # file_extension = "adict"
    # file_extension_force_add = False
    # file_extension_needed = False

    # Hack to enable specific classes of modules to be pickled on __del__ after interpreter shutdown.
    # Problem is, sys.modules was already emptied and pickle does not find the modules of containing classes.
    # Reference modules like {"pathlib": pathlib} as shown in sys.modules.
    noahs_ark_modules = {}

    def __init__(self, file: Union[PathLike, str, bytes] = None, file_format: FileFormat = None, **defaults):
        self._file: Optional[pathlib.Path] = None

        # Keep an open handle on files.
        self._fhandle: Optional = None

        if file_format:
            self.default_file_format = file_format  # Set a local instance copy of desired format

        if file is not None:
            # File path given
            self.file = file

        # Create default values
        # Use defaults of class
        self.instancedefaults = self.default_content.copy()

        # Update with defaults supplied by kwargs (if given)
        self.instancedefaults.update(defaults)

        # Keep track if data has changed
        self.changed = False

        # Create internal data dict storage based on defaults
        self.data = dict()

        if self.auto_load:
            self.load()

        self._del = False

    @property
    def file(self) -> Union[PathLike, str, bytes]:
        """
        Returns current file as Path object or None.
        Setter may receive any PathLike, str or bytes.
        """
        return self._file

    @file.setter
    def file(self, newfile: Union[PathLike, str, bytes] = None):
        if newfile:
            # not None
            if self.expand_home:
                newfile = pathlib.Path(newfile).expanduser()
            else:
                newfile = pathlib.Path(newfile)

        if self._file == newfile:
            # No change
            return

        if self._fhandle:
            # Close current open handle
            self._fhandle.close()
            self._fhandle = None

        if newfile:
            # New file given. open it.

            # Check if we have the correct open mode for file type
            if self.default_file_format not in _openflags:
                raise TypeError(f"File mode not found for: {self.default_file_format!s}")

            if self.auto_mkdir:
                parent = newfile.parent
                if not parent.exists():
                    parent.mkdir(mode=0o700, parents=True, exist_ok=True)

            # Get correct open flags for format
            filemode = _openflags[self.default_file_format]

            # Open text modes always as utf8.
            self._fhandle = open(newfile, mode=filemode, encoding=None if "b" in filemode else "utf8")
            # TODO path.open

        self._file = newfile

    @property
    def has_mutables(self) -> bool:
        """
        Returns True is dictionary has at least one mutable object.
        Indicates that content of Autodict may have changed even if changed attribute was not triggered.
        """
        for value in self.data.values():
            if not isinstance(value, IMMUTABLES):
                return True

        return False  # Found no mutables

    def __getitem__(self, key):
        return self.data[key]

    def __delitem__(self, key):
        del self.data[key]
        if self.track_changes:
            self.changed = True

    def __setitem__(self, key, value):
        done_cast = False

        if self.track_changes:
            # Do a deeper track for changes

            if key not in self.data:
                # Key-Value is new
                self.changed = True

            if not self.changed:
                # Possibly updated a key-value first time after save. Deep check for a change.
                existing_value = self.data[key]

                if self.auto_cast and type(existing_value) is not str and type(value) is str:
                    cls = type(existing_value)
                    value = _cast(value, cls)
                    done_cast = True

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

        if self.auto_cast and not done_cast and type(value) is str and key in self.data:
            # Cast required and not yet done by track_changes
            existing_value = self.data[key]

            if type(existing_value) is not str:
                cls = type(existing_value)
                value = _cast(value, cls)

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
        self._del = True  # Set flag. Interpreter may shutdown

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
            self.file = pathlib.Path(file)

        self.data.clear()

        if self.file:
            # Empty file?
            self._fhandle.seek(0, SEEK_END)
            fileempty = self._fhandle.tell() == 0
        else:
            fileempty = True

        if self.include_defaults or self.file is None or fileempty:
            # Set defaults
            self.data.update(self.instancedefaults)

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
            self.file = pathlib.Path(file)

        if self.file is None:
            raise IOError("No file location specified for save.")

        if force or not self.track_changes or (self.track_changes and self.changed):
            # Goto start of file and truncate for fresh write
            self._fhandle.seek(0)
            self._fhandle.truncate()

            if self._del and len(sys.modules) == 0 and self.default_file_format in _DANGEROUS_OBJECT_PICKLE_FORMATS:
                # On interpreter exit, we need to use the safer method because sys.modules is already emptied etc.
                pdump = pickle._dump
                sys.modules.update(self.noahs_ark_modules)

            else:
                # Always prefer faster compiled method
                pdump = pickle.dump

            # Pickle mode
            if self.default_file_format is FileFormat.pickle_human:
                pdump(self.data, file=self._fhandle, protocol=0)

            elif self.default_file_format is FileFormat.pickle_binary:
                pdump(self.data, file=self._fhandle, protocol=4)

            # Json mode
            elif self.default_file_format is FileFormat.json:
                json.dump(self.data, fp=self._fhandle)

            elif self.default_file_format is FileFormat.json_pretty:
                json.dump(self.data, fp=self._fhandle, indent=4)

            else:
                raise ValueError(f"Unsupported default_file_format: {self.default_file_format!s}")

            self._fhandle.flush()
            self.changed = False
