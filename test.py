from autodict import Autodict, FileFormat
import pathlib


class MyConf(Autodict):
    __slots__ = ()
    # default_content = {"bool": False, "type": "configfile", "configfile_version": 2, "path": pathlib.Path("/tmp")}
    default_content = {"bool": False, "type": "configfile", "configfile_version": 2}
    auto_load = True
    auto_cast = True
    # noahs_ark_modules = {"pathlib": pathlib}
    default_file_format = FileFormat.json_pretty


ad = MyConf("/tmp/ad5")

# ad["bool"] = "False"

# ad["x"] = 1
# ad["numeric"] = 2100

print(ad)
