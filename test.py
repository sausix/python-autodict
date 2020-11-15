from autodict import Autodict, FileFormat
# Autodict.include_defaults = False


class MyConf(Autodict):
    default_content = {"type": "configfile", "configfile_version": 2}
    auto_load = True
    default_file_format = FileFormat.json_pretty


ad = MyConf("/tmp/ad1")

print(ad)
