# python-autodict
Handy dictionary like object that saves and restores contents to file.


# Requires (all in Python included)
- pickle
- json
- pathlib


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

### file
Path to a file (str, bytes or Path from pathlib). May be omitted. Then provide file on load or save methods.

### file_format
Specify the format of the file on disk from `FileFormat` enum. If omitted, class default `Autodict.default_file_format` will be used.
- `pickle_human`  # Human readable pickle (v0)
- `pickle_binary`  # Binary pickle v4 (Python 3.4)
- `json`  # Compacted Json dump
- `json_pretty`  # Pretty Json with indents

### defaults (kwargs)
You may provide keyword args as default values. Keys will be treaten as strings.

# Advanced usage
You may change class default settings in the **dirty** way for all instances like this:
```python
from autodict import Autodict, FileFormat
Autodict.default_file_format = FileFormat.json
instance = Autodict("myfile")
```
**Just don't!**

Better way is making use of inheritance:

```python
from autodict import Autodict, FileFormat

class MyConf(Autodict):
    default_content = {"type": "configfile", "configfile_version": 2}
    auto_load = False
    default_file_format = FileFormat.json_pretty

myconf = MyConf("myfile.json")
```

# Class defaults
* `default_file_format`  # Which file format to use for instances without `file_format` specified.

* `auto_load`  # Calls `load()` after instantiation if `True`.

* `save_on_del`  # Calls `save(force=True)` right before deconstruction of instance if `True`.

* `track_changes`  # Tracks changes on immutable values if `True`. `save()` won't save if no change has made.

* `include_defaults`:  
  * `False`: Use defaults only if persistent file not found on load.
  * `True`:  Use defaults and update from persistent file if exists.

* `default_content`  # Dictionary which will be copied and used for instances. Keys may be specified as any immutable data type. Constructor kwargs just support strings as keys.

* `expand_home`  # File path containing "~" are expanded to the home directory.

* `auto_cast`  # Default is False: New values for existing keys will be cast to the original data types. If `some_Autodict` has an entry `{"numeric": 1}`, assigning `some_Autodict["numeric"] = "2"` will cast the string into int.

* `noahs_ark_modules`  # Dangerzone. Affects following situation: 
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

    default_content = {"path": pathlib.Path("/tmp")}  # Using pathlib
    noahs_ark_modules = {"pathlib": pathlib}  # Assign depending modules for dump pickle
  ```



# Methods
* `load()` Reloads data from the file. Unsaved data is lost.

* `save()` Saves current content of Autodict to file.

* All other methods from `dict`.

# Attributes
* `changed` Autodict tries to keep track of changed data inside. Unsafe. See restrictions.


# Restrictions
- Pickle mode may not support all classes.
- JSON mode supports less data types of Python. Values may change or get lost.
- Use with simple and immutable objects as data. `int, str, float, bool, tuple, bytes, complex, frozenset, Decimal` etc. Mutables like `list, set, bytearray, dict` are supported but `changed` attribute will not work. Use save(force=True) if you save it manually.

# TODOs
- tests
- nested autodicts
- file extenstions
- subclass name matching


# Changelog

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
