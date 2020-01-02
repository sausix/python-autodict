# python-autodict
Dictionary extension that saves and restores contents to files.


# Requires
- pickle
- Pathlib


# Usage
Just use it like a dict object.
But add a file path as first argument in your object instanciation.

```python
from autodict import Autodict

# Create instance and load contents based on a file
a = Autodict("/tmp/mydict.dat")

# When providing extra arguments like in dict(...), a prefilled dict is being created
b = Autodict("/tmp/mydict2.dat", x=1, y=2)  # Or pass an existing dict.

# Handle object like a dict
print("MyDict:", a)
a['test'] = 5

# New content will automatically be saved to file on variable destruction or program end.
```

# Extra methods
`load()` Reloads data from file to Autodict. Unsaved data is lost.

`save()` Saves current content of Autodict to file.

`changed` Autodict tries to keep track of changed data inside. Unsafe. See restrictions.


# Restrictions
- Use with simple objects as data. `int, str, float, bool, bytes, bytearray, list, tuple, dict` etc. Saving class instances won't work. Refer to Pickle docs.
- Nesting in lists is possible. "changed" attribute may not work on nested variable changes.
