from autodict import Autodict, FileFormat
import pathlib

class MyConf(Autodict):
    default_content = {"type": "configfile", "configfile_version": 2, "path": pathlib.Path("/tmp")}
    auto_load = True
    auto_cast = True
    noahs_ark_modules = {"pathlib": pathlib}

ad = MyConf("/tmp/ad2")

# ad["x"] = 1
# ad["numeric"] = 2100

print(ad)
