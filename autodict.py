import pickle
from pathlib import Path
from collections.abc import MutableMapping
from typing import Union


class Autodict(MutableMapping):
    def __init__(self, file: Union[Path, str], *args, **kwargs):
        if type(file) is str:
            file = Path(file)

        self.file: Path = file  # Remember path
        self.changed = False  # Keep track if data has changed

        if len(args) or len(kwargs):
            # Passed some values. Create data based on args and save immediately.
            self.data = dict(*args, **kwargs)
            self.save()
        else:
            self.data = dict()
            self.load()

    def __getitem__(self, key):
        return self.data[key]

    def __delitem__(self, key):
        del self.data[key]
        self.changed = True

    def __setitem__(self, key, value):
        if not self.changed and key in self.data:
            # Check only if:
            #   - Dictionary is not yet changed before (not dirty, synced, saved)
            #   - There is already a value for the key
            existing_value = self.data[key]

            if type(value) in (int, str, float, bool, bytes, bytearray, complex, frozenset):
                # Compare simple, mutable values
                self.changed = existing_value is not value

            elif type(value) in (list, tuple):
                if len(existing_value) != len(value):
                    # Count of elements changed
                    self.changed = True

                else:
                    # Dig deeper for comparison
                    try:
                        # Try internal hash comparison anyway
                        self.changed = existing_value is not value

                    except TypeError:
                        # Hash not possble. Some elements seem mutable.
                        self.changed = True

            else:
                # Other type.
                # Just handle as changed
                self.changed = True

        # Update internal dict
        self.data[key] = value

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __del__(self):
        self.save()

    def __repr__(self):
        return f"AutoDict('{self.file}')"

    def __str__(self):
        return str(self.data)

    def load(self):
        self.data.clear()
        if self.file.exists():
            with self.file.open('rb') as f:
                self.data = dict(pickle.load(f))
        self.changed = False

    def save(self):
        with self.file.open('wb+') as f:
            pickle.dump(self.data, f, pickle.HIGHEST_PROTOCOL)
        self.changed = False
