# -*- coding: utf-8 -*-

import pickle
import json
import pathlib
import sys
from json.encoder import encode_basestring, encode_basestring_ascii, INFINITY, _make_iterencode
from io import SEEK_END
from collections.abc import MutableMapping
from typing import Union, Optional, Type
from enum import Enum, auto, EnumMeta
from os import PathLike
from decimal import Decimal
from re import compile
from datetime import date, datetime, time


__VERSION__ = "1.4"
__AUTHOR__ = "Adrian Sausenthaler"
__SOURCE__ = "https://github.com/sausix/python-autodict"

# "<Enum:MyEnum.Member>"
# "<Enum:Package.Subpackage.MyEnum.Member>"
_enum_matcher = compile(r"^<Enum:(?:([a-zA-Z0-9_.]*)\.)?([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)>$")

# "<MyNamedTuple>"
# "<Package.Subpackage.MyNamedTuple>"
_nt_matcher = compile(r"^<(?:([a-zA-Z0-9_.]*)\.)?([a-zA-Z0-9_]+)>$")

# "<Path:/tmp>"
# "<PurePath:/tmp>"
_path_matcher = compile(r"^<(Path|PurePath):(.*)>$")
_path_types_mapping = {
    "Path": pathlib.Path,
    "PurePath": pathlib.PurePath,
}

# "<datetime:2021-02-28T23:11:37.374773>"
# "<date:2021-02-28>"
_date_matcher = compile(r"^<(datetime|date|time):(.*)>$")
_date_types_mapping = {
    "datetime": datetime,
    "date": date,
    "time": time,
}

# "<bytes:00AABBCCFF>"
# "<bytearray:00AABBCCFF>"
_bytes_matcher = compile(r"^<(bytes|bytearray):([0-9A-Fa-f]*)>$")
_bytes_types_mapping = {
    "bytes": bytes,
    "bytearray": bytearray,
}


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


def _get_class(cls_str: str, member_str: str = None, module_hint: str = None, match_type=type) -> Optional[Type]:
    """
    Find object definitions in loaded modules
    """
    if module_hint:
        # Prefer module_hint
        module = sys.modules.get(module_hint)  # or None
        check_class = getattr(module, cls_str, None)
        if check_class:
            if match_type is None or type(check_class) is match_type:
                return check_class

    for module_name, module in sys.modules.copy().items():
        check_class = getattr(module, cls_str, None)
        if not check_class:
            continue

        if match_type is None or type(check_class) is match_type:
            if member_str:
                if hasattr(check_class, member_str):
                    return check_class
            else:
                return check_class

    # Could not find a module containing an Enum of this type and containing this member.
    return None


def _get_nt_class(value: dict) -> Optional[Type[EnumMeta]]:
    nt_cls_str = value.pop("__named_tuple__")

    # Parse namedtuple definition
    nt_data = _nt_matcher.match(nt_cls_str)
    if not nt_data:
        raise ValueError(f"Invalid named tuple class definition: '{nt_cls_str}'.")

    # Find namedtuple class
    return _get_class(nt_data.group(2), module_hint=nt_data.group(1))


class JSONSpecialsEncoder(json.JSONEncoder):
    def default(self, obj):
        """
        Is being called for encoding unknown types.
        """
        t = type(obj)

        if type(t) is EnumMeta:
            # Enum classes
            if hasattr(t, "__module__"):
                enum_str = f"<Enum:{t.__module__}.{obj!s}>"
            else:
                enum_str = f"<Enum:{obj!s}>"

            if not _enum_matcher.match(enum_str):
                raise TypeError(f"Enum or member has invalid characters: '{enum_str}'.")
            return enum_str

        if isinstance(obj, tuple):
            # Some kind of tuple
            if hasattr(obj, "_asdict"):
                # It's a named tuple!
                # Save with keywords and tag the object.
                data = obj._asdict()

                if hasattr(t, "__module__"):
                    data["__named_tuple__"] = f"<{t.__module__}.{t.__name__}>"
                else:
                    data["__named_tuple__"] = f"<{t.__name__}>"
                return data

            # JSON encoder does not understand tuples anymore.
            # And tuples get converted to lists by default.
            # So let's not drop tuple info and encode it as a tagged list.
            return ["__tuple__"] + list(obj)

        if isinstance(obj, pathlib.Path):
            return f"<Path:{obj!s}>"

        if isinstance(obj, pathlib.PurePath):
            return f"<PurePath:{obj!s}>"

        if isinstance(obj, (datetime, date, time)):
            return f"<{type(obj).__name__}:{obj.isoformat()}>"

        if isinstance(obj, (bytes, bytearray)):
            return f"<{type(obj).__name__}:{obj.hex()}>"

        if isinstance(obj, set):
            return ["__set__"] + list(obj)

        if isinstance(obj, frozenset):
            return ["__frozenset__"] + list(obj)

        # Default conversion with builtin JSONEncoder.default
        raise TypeError(f"Unknown/unsupported data type for serialization: {obj!r}.")

    def _create_iterencode(self):
        """
        Mostly an awful redefinition of json.encoder.JSONEncoder.iterencode just to "unsupport" tuples.
        Tuples then get processed by default() method.

        Used to avoid tuples get converted to lists and also adds support of namedtuples.
        """
        if self.check_circular:
            markers = {}
        else:
            markers = None
        if self.ensure_ascii:
            _encoder = encode_basestring_ascii
        else:
            _encoder = encode_basestring

        def floatstr(_o, allow_nan=self.allow_nan, _repr=float.__repr__, _inf=INFINITY, _neginf=-INFINITY):
            if _o != _o:
                text = 'NaN'
            elif _o == _inf:
                text = 'Infinity'
            elif _o == _neginf:
                text = '-Infinity'
            else:
                return _repr(_o)

            if not allow_nan:
                raise ValueError("Out of range float values are not JSON compliant: " + repr(_o))

            return text

        return _make_iterencode(
            markers, self.default, _encoder, self.indent, floatstr,
            self.key_separator, self.item_separator, self.sort_keys,
            self.skipkeys, False, tuple=type("FakeClass", (), {}))

    def iterencode(self, o, one_shot=False):
        return self._create_iterencode()(o, 0)


class Autodict(MutableMapping):
    """
    Persistent dict which syncs its content automatically with a file.

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

    # File mode of parent folders which may be created on auto_mkdir
    parents_create_mode = 0o700

    # Call save() on destruction
    save_on_del = True

    # Track changes for physical save only if data has been changed.
    # May not be accurate on nested collections or mutables.
    track_changes = True

    # True:  Use defaults and update from persistent file if exists
    # False: Use defaults only if persistent file not found on load
    include_defaults = True

    # Default content (class level)
    default_content = {}

    # Expand ~ to HOME
    expand_home = True

    # Try to keep data types by casting from input source.
    # data types will be acquired from default_content or current content.
    auto_cast = False

    # Cast hints for booleans (lower case on strings)
    bool_false = {False, 0, "0", "n", "no", "false", 0., None}
    bool_true = {True, 1, "1", "y", "yes", "true"}
    bool_default = False  # Bool result on unknown types

    json_specials_encoder = JSONSpecialsEncoder

    # Hack to enable specific classes of modules to be pickled on __del__ after interpreter shutdown.
    # Problem is, sys.modules was already emptied and pickle does not find the modules of containing classes.
    # Reference modules like {"pathlib": pathlib} as shown in sys.modules.
    noahs_ark_modules = {}

    # File extension
    # file_extension = "adict"
    # file_extension_force_add = False
    # file_extension_needed = False

    __slots__ = ("_file", "_fhandle", "instancedefaults", "changed", "data", "_del", "file_format")

    def json_specials_decoder(self, d: dict):
        # #################################################
        # Look for reserved keys in dictionary.
        if "__named_tuple__" in d:
            nt_cls = _get_nt_class(d)
            if not nt_cls:
                raise ValueError(f"Could not find class for namedtuple structure: {d!r}.")

            # Create namedtuple by kwargs
            return nt_cls(**d)

        # #################################################
        # Look for well known structures in values.
        for key, value in d.items():
            if type(value) is list and value:
                if value[0] == "__tuple__":
                    # Recreate tuple from list
                    d[key] = tuple(value[1:])

                elif value[0] == "__set__":
                    # Recreate set from list
                    d[key] = set(value[1:])

                elif value[0] == "__frozenset__":
                    # Recreate frozenset from list
                    d[key] = frozenset(value[1:])

            if type(value) is str:
                # Check for types encoded as strings
                # Enum?
                enum_data = _enum_matcher.match(value)
                if enum_data:
                    # Matches Enum pattern
                    default_enum_hint = None
                    if key in self.instancedefaults:
                        # Get enum class from defaults as hint
                        enum_value = self.instancedefaults[key]
                        t = type(enum_value)
                        if type(t) is EnumMeta:
                            default_enum_hint = t
                    module_hint = enum_data.group(1)
                    etype = enum_data.group(2)
                    emember = enum_data.group(3)

                    if default_enum_hint and default_enum_hint.__name__ == etype:
                        # Use Enum class found in defaults
                        # Enum definition may have moved.
                        enum = default_enum_hint
                    else:
                        # No hint from default_dict. Search all modules containing this enum and member.
                        enum = _get_class(etype, emember, module_hint, EnumMeta)

                    if not enum:
                        raise TypeError(f"Could not find Enum class to decode '{value}'.")

                    attr = getattr(enum, emember, None)
                    if not attr:
                        raise TypeError(f"Could not find member '{emember}' in Enum {enum:r} to decode '{value}'.")

                    d[key] = attr

                # Path?
                path_data = _path_matcher.match(value)
                if path_data:
                    # Matches Path/PurePath pattern
                    cls = _path_types_mapping[path_data.group(1)]
                    d[key] = cls(path_data.group(2))

                # datetime/date/time
                date_data = _date_matcher.match(value)
                if date_data:
                    cls = _date_types_mapping[date_data.group(1)]
                    d[key] = cls.fromisoformat(date_data.group(2))

                # bytes/bytearray
                bytes_data = _bytes_matcher.match(value)
                if bytes_data:
                    cls = _bytes_types_mapping[bytes_data.group(1)]
                    d[key] = cls.fromhex(bytes_data.group(2))

        # Return dict as plain dict
        return d

    def __init__(self, file: Union[PathLike, str, bytes] = None, file_format: FileFormat = None, **defaults):
        self._file: Optional[pathlib.Path] = None

        # Keep an open handle on files.
        self._fhandle: Optional = None

        # Set a local instance copy of desired format
        self.file_format = file_format or self.default_file_format

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

    @classmethod
    def _cast(cls, value, totype):
        """
        Will be called if type of value differs from totype
        """
        fromtype = type(value)

        if totype is bool:  # returns
            if fromtype is str:
                value = value.lower()

            if value in cls.bool_false:
                return False
            elif value in cls.bool_true:
                return True
            else:
                return cls.bool_default

        if hasattr(totype, "_asdict"):  # returns
            if fromtype is dict:
                # Create from dict source
                if "__named_tuple__" in value:
                    # Contains class definition
                    nt_cls = _get_nt_class(value)

                    if not nt_cls:
                        # Bad. Try to use nt type from default-dict
                        nt_cls = totype

                    return nt_cls(**value)
                else:
                    # dict without hint for namedtuple
                    # Instantiate by kwargs
                    return totype(**value)

            elif fromtype in (list, tuple):
                # Unpack sequence into named tuple. Order matters!
                return totype(*value)

            else:
                # Unsupported type to cast namedtuple from
                raise ValueError(f"Can't cast namedtuple from {fromtype!r}.")

        if totype is tuple:  # returns
            if fromtype is list:
                if value and value[0] == "__tuple__":
                    return tuple(value[1:])
                else:
                    return tuple(value)
            else:
                raise ValueError(f"Can't cast tuple from {value!r}.")

        # Unknown. Last chance is casting by class contructor.
        return totype(value)

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
            # New file given, open it.

            # Check if we have the correct open mode for file type
            if self.file_format not in _openflags:
                raise TypeError(f"File mode not found for: {self.file_format!s}")

            if self.auto_mkdir:
                parent = newfile.parent
                if not parent.exists():
                    parent.mkdir(mode=self.parents_create_mode, parents=True, exist_ok=True)

            # Get correct open flags for format
            filemode = _openflags[self.file_format]

            # Open text modes always as utf8.
            self._fhandle = newfile.open(mode=filemode, encoding=None if "b" in filemode else "utf8")

        self._file = newfile

    @property
    def has_mutables(self) -> bool:
        """
        Returns True if dictionary has at least one mutable object.
        Indicates that content of Autodict may have changed even if changed attribute was not triggered.
        """
        for value in self.data.values():
            if not isinstance(value, IMMUTABLES):
                return isinstance(type(value), (EnumMeta, ))

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
                # Key-value is new
                self.changed = True

            if not self.changed:
                # Possibly updated a key-value first time after save. Deep check for a change.
                existing_value = self.data[key]

                if existing_value is value:
                    # Assigned same object. Absolutely not a change.
                    return  # Speed up

                if self.auto_cast and type(existing_value) is not type(value):
                    cast_to = type(existing_value)
                    value = self._cast(value, cast_to)
                    done_cast = True

                if isinstance(value, (IMMUTABLES, MUTABLES_WITH_EQ)) or type(type(value)) is EnumMeta:
                    # New identity of value.
                    # These types allow comparison.
                    self.changed = existing_value != value

                else:
                    # Other type. Comparison not possible.
                    # Just handle as changed data.
                    # TODO: check __eq__?
                    self.changed = True

        if self.auto_cast and not done_cast and key in self.data:
            # Cast required and not yet done by track_changes
            existing_value = self.data[key]

            if type(existing_value) is not type(value):
                cast_to = type(existing_value)
                value = self._cast(value, cast_to)

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
        # Set flag. Interpreter may shutdown
        self._del = True

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
        # Pickle here? No.
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
            if self.file_format in (FileFormat.pickle_human, FileFormat.pickle_binary):
                self.update(pickle.load(file=self._fhandle))

            # Json mode
            elif self.file_format in (FileFormat.json, FileFormat.json_pretty):
                self.update(json.load(fp=self._fhandle, object_hook=self.json_specials_decoder))

            else:
                raise ValueError(f"Unsupported file_format: {self.file_format!s}")
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

            if self._del and len(sys.modules) == 0 and self.file_format in _DANGEROUS_OBJECT_PICKLE_FORMATS:
                # On interpreter exit, we need to use the safer method because sys.modules is already emptied etc.
                pdump = pickle._dump
                sys.modules.update(self.noahs_ark_modules)

            else:
                # Always prefer faster compiled method
                pdump = pickle.dump

            # Pickle mode
            if self.file_format is FileFormat.pickle_human:
                pdump(self.data, file=self._fhandle, protocol=0)

            elif self.file_format is FileFormat.pickle_binary:
                pdump(self.data, file=self._fhandle, protocol=4)

            # Json mode
            elif self.file_format is FileFormat.json:
                json.dump(self.data, fp=self._fhandle, cls=self.json_specials_encoder)

            elif self.file_format is FileFormat.json_pretty:
                json.dump(self.data, fp=self._fhandle, indent=4, cls=self.json_specials_encoder)

            else:
                raise ValueError(f"Unsupported file_format: {self.file_format!s}")

            self._fhandle.flush()
            self.changed = False
