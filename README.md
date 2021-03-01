# python-autodict
This project aims to provide a simple file storage backend accessable by a dictionary interface. The dictionary like object syncs its contents with a file on disk.  
Supports Python's pickle and JSON format.

Python's standard JSON encoder was improved to support Enums, NamedTuples, Tuples, bytes and Pathlib and some other types.


# Basic usage
Just use it like a dict object but add a file path as first argument in your object instantiation.

```python
from autodict import Autodict, FileFormat


# Create instance and load contents based on a file
mystore = Autodict("/tmp/empty_dict.myconf")
# Now use "mystore" like a dictionary.
# Call mystore.save() anytime. Else it will save right before destruction.



# Providing file format and default values for first use.
myconfig = Autodict("/tmp/default_dict.myconf", file_format=FileFormat.json_pretty, name="Python", count=2)
print(myconfig["name"])  # Use values immediately
# result:
#    Python (on first run)
#    Cool (on next run)

myconfig["name"] = "Cool"  # Save for next run
```

## Constructor
```
instance = Autodict(
    file: Union[PathLike, str, bytes] = None,
    file_format: FileFormat = None,
    **defaults
)
```

`file`:  
Path to a file (str, bytes or Path from pathlib). May be omitted. Then provide file on load or save methods.

`file_format`:  
Specify the format of the file on disk from `FileFormat` enum. If omitted, class default `Autodict.default_file_format` will be used:
- `pickle_human`: Human readable pickle (v0)
- `pickle_binary`: Binary pickle v4 (Python 3.4)
- `json`: Compacted Json dump
- `json_pretty`: Pretty Json with indents

`defaults` (kwargs):  
You may provide keyword args as default values for this instance. Keys will be treaten as strings. Other key types are not supported here due to `**kwargs` nature.

# Advanced usage
You may change class default settings in the **dirty** way for all instances like this:
```python
from autodict import Autodict, FileFormat
Autodict.default_file_format = FileFormat.json
instance = Autodict("myfile")
```
**Just don't!**

Better way is making use of inheritance to create specialized classes of autodict:

```python
from autodict import Autodict, FileFormat

class MyConf(Autodict):
    __slots__ = ()  # Save memory by avoiding an extra unused dict
    default_content = {"type": "configfile", "configfile_version": 2}  # Default for each instance.
    auto_load = False  # Explicit call to load() preferred.
    default_file_format = FileFormat.json_pretty  # If you prefer json.

myconf = MyConf("myfile.json")
```

# Class defaults
Alternative Autodict behaviour can be specified by subclassing from Autodict.

* `default_file_format`: Which file format to use for instances without `file_format` specified.

* `auto_load`: Calls `load()` after instantiation if `True`.

* `auto_mkdir`: Allowes to create missing parent directories.

* `parents_create_mode`: Filesystem attributes mode for created directories by `auto_mkdir`.

* `save_on_del`: Calls `save(force=True)` right before deconstruction of instance if `True`.

* `track_changes`: Tracks changes on immutable values if `True`. `save()` won't save if no change has made.

* `include_defaults`:  
  * `False`: Use defaults only if persistent file not found on load.
  * `True`:  Use defaults and update from persistent file if exists.

* `default_content`: Dictionary which will be copied and used for instances. Keys may be specified as any immutable data type. Constructor kwargs just support strings as keys.

* `expand_home`: File paths containing "`~`" are expanded to the home directory.

* `auto_cast`: Default is False: New values for existing keys will be cast to the original data types. If `some_Autodict` has an entry `{"numeric": 1}`, assigning `some_Autodict["numeric"] = "2"` will cast the string into int. Effective on restoring original data types from json files. Works on top level items only. Nested dicts won't be checked or cast.

* `bool_false`, `bool_true`: Values which will be interpreted as `False` or `True` on active `auto_cast`. Default: `{False, 0, "0", "n", "no", "false", 0., None}` and `{True, 1, "1", "y", "yes", "true"}`

* `bool_default`: Bool result on unknown types on active `auto_cast`. Default result: `False`.

* `noahs_ark_modules`: Dangerzone. Affects following situation:
  * `save_on_del` enabled
  * Python interpreter is shutting down
  * `save` called by the destructor
  * Save format set to `pickle_binary`
  * Some classes like `pathlib` are used in the Autodict and want to be pickled.
  
  This situation fails because Python has already emptied `sys.modules` and `pickle` can't lookup modules and classes anymore.
 
  Solution is filling `sys.modules` again before pickle dumping. So if you want to pickle `pathlib`, put it into `noahs_ark_modules` like this:

  ```python
  import pathlib
  from autodict import Autodict

  class MyConf(Autodict):
    # These following options are already default!  
    # save_on_del = True
    # default_file_format = FileFormat.pickle_binary
    __slots__ = ()  # Save memory by avoiding an extra unused dict
    default_content = {"path": pathlib.Path("/tmp")}  # Using pathlib
    noahs_ark_modules = {"pathlib": pathlib}  # Assign depending modules for dump pickle
  ```


# Instance attributes
* `load()`: Reloads data from the file. Unsaved data is lost.

* `save()`: Saves current content of Autodict to file.

* `path`: Property containing the path to load/save contents to/from. Contains path which was set by init.

* All other methods from `dict`.

# Properties
* `changed`: Autodict tries to keep track of changed data inside. Unsafe. See restrictions.


# Restrictions
- Pickle mode may not support all classes.
- JSON mode supports less data types of Python. Values may change or get lost. See `auto_cast` and next chapter.
- Use with simple and immutable objects as data. `int, str, float, bool, tuple, bytes, complex, frozenset, Decimal` etc. Mutables like `list, set, bytearray, dict` are supported but `changed` attribute will not work. Use save(force=True) if you save it manually.


# Data type handling in serialisation

| Data type | Pickle | JSON |
|---|---|---|
| Pathlib (Path, PurePath)  | Native support | Implemented |
| Enum | Native support¹ | Implemented² |
| tuple | Native support | Improved³ |
| NamedTuple | Native support¹ | Implemented² |
| date, time, datetime | Native support | Implemented |
| bytes, bytearray | Native support | Implemented |
| set, frozenset | Native support | Implemented³ |


¹ Relies on the module path of the class as hint. Module containing the class must exist and has been loaded before calling `load()`. Classes may be moved to other modules.  

² Relies primarily on classes used in `default_content` with same key. `save()` will also keep module path as fallback hint. Classes may be moved between modules.  

³ Tuples, set and frozenset are not supported by JSON directly. This implementation encodes them into a list by prepending "&#95;&#95;tuple&#95;&#95;", "&#95;&#95;set&#95;&#95;" or "&#95;&#95;frozenset&#95;&#95;".


# TODOs
- tests
- nested autodicts?
- nested dicts with path access?
- file extenstions
- subclass name matching


# Changelog

## 2021-02-28 v1.4
- Implemented better support for Enums, Tuples, NamedTuples, datetime, date, time, bytes, bytearray, set, frozenset and Pathlib for JSON


## 2021-02-17 v1.3
- auto_cast improved for booleans
- fixed auto_cast was not applied on load()
- bool_false, bool_true, bool_default
- slots (reduced memory consumption)
- parents_create_mode


## 2020-12-03 v1.2
- expand_home setting
- auto_mkdir
- auto_cast
- `noahs_ark_modules` workaround for dangerous auto save of objects to pickle on interpreter shutdown


## 2020-11-16 v1.0
- Implemented json, pickle, class settings
- Added class level default values
- Added interchangable file
- Single r+w file handle which is keeped open until instance destruction
- Simplified track_changes
- First manual tests
- Added licence
