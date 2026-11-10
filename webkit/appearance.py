"""Persistent interface choices, independent of document formatting."""
import json
import math
import os
from pathlib import Path
import tempfile

DEFAULTS_VERSION = 1

DEFAULTS = {"theme":"mixed", "blur":False, "opacity":0.88, "blur_radius":14.0}


def normalise(value):
    if not isinstance(value,dict):
        value={}
    result=DEFAULTS.copy()
    if value.get("theme") in ("light","dark","mixed"):
        result["theme"]=value["theme"]
    if isinstance(value.get("blur"),bool):
        result["blur"]=value["blur"]
    for name,lower,upper in (("opacity",0.0,1.0),("blur_radius",0.0,40.0)):
        number=value.get(name)
        if isinstance(number,(int,float)) and not isinstance(number,bool) and math.isfinite(number):
            result[name]=max(lower,min(upper,float(number)))
    return result


class AppearanceStore:
    def __init__(self,path):
        self.path=Path(path)

    def load(self):
        try:
            saved=json.loads(self.path.read_text(encoding="utf-8"))
            settings=normalise(saved)
            # Apply the new startup defaults once to preferences from older builds.
            if not isinstance(saved,dict) or saved.get("defaults_version") != DEFAULTS_VERSION:
                settings.update(theme="mixed",blur=False)
                self.save(settings)
            return settings
        except (OSError,ValueError):
            return DEFAULTS.copy()

    def save(self,settings):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=self.path.parent,delete=False) as file:
                temporary=Path(file.name)
                json.dump({**normalise(settings),"defaults_version":DEFAULTS_VERSION},file)
            os.replace(temporary,self.path)
        finally:
            if temporary and temporary.exists():temporary.unlink()
