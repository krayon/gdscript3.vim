# Functions for gathering completion items.

import os
import re

import classes
import util
import script

# Flags for selecting which built-in items to complete.
_MEMBERS = 1
_METHODS = 2
_CONSTANTS = 4

_completions = None

def clear_completions():
    global _completions
    _completions = []

def get_completions():
    return _completions

def append_completion(completion):
    if completion:
        _completions.append(completion)

def complete_paths():
    m = re.search("res://(((\w|-)+/)*)$", util.get_line())
    if m:
        project_dir = util.get_project_dir()
        if not project_dir:
            return
        subdir = m.group(1)
        # Directories and files are grouped and sorted separately.
        dirs = []
        files = []
        dir = "{}/{}".format(project_dir, subdir)
        if not os.path.isdir(dir):
            return
        for entry in os.listdir(dir):
            if not entry.startswith("."):
                if not util.filter(entry):
                    continue
                if os.path.isdir("{}/{}".format(dir, entry)):
                    dirs.append({
                        "word": entry,
                        "abbr": "{}/".format(entry),
                        "dup": 1,
                    })
                else:
                    files.append({
                        "word": entry,
                        "dup": 1,
                    })
        dirs.sort(key=lambda c: c["word"])
        files.sort(key=lambda c: c["word"])
        for d in dirs:
            append_completion(d)
        for f in files:
            append_completion(f)

def complete_class_names(type=0):
    for name in classes.iter_class_names(type):
        append_completion(build_completion(name))

def complete_method_signatures():
    c = classes.get_class(script.get_extended_class())
    while c:
        for method in c.iter_methods():
            d = build_completion(method, c.get_name())
            mapped_args = map(lambda a: a.name, method.args)
            d["word"] = "{}({}):".format(method.name, ", ".join(mapped_args))
            append_completion(d)
        c = c.get_inherited_class()

def complete_globals():
    # Complete user decls.
    down_search_start = 1
    for decl in script.iter_decls(util.get_cursor_line_num(), direction=-1):
        decl_type = type(decl)
        if decl_type == script.ClassDecl:
            down_search_start = decl.line
        elif decl_type != script.FuncDecl:
            append_completion(build_completion(decl))
    for decl in script.iter_decls(down_search_start, direction=1):
        append_completion(build_completion(decl))

    # Complete extended class.
    c = classes.get_class(script.get_extended_class())
    _add_class_items(c)

    # Complete global scope.
    _add_class_items(classes.get_global_scope())

# Recursively add class items.
def _add_class_items(c, flags=None):
    if not flags:
        flags = _MEMBERS | _METHODS | _CONSTANTS
    while c:
        c_name = c.get_name()
        for member in c.iter_members():
            append_completion(build_completion(member, c_name))
        for method in c.iter_methods():
            append_completion(build_completion(method, c_name))
        for constant in c.iter_constants():
            append_completion(build_completion(constant, c_name))
        c = c.get_inherited_class()

# Generic function for building completion dicts.
def build_completion(item, c_name=None):
    t = type(item)
    if t is str:
        if util.filter(item):
            return { "word": item }
    elif item.name:
        if not util.filter(item.name):
            return
        d = {"word": item.name}

        # Built-in
        if t is classes.GodotMember:
            if c_name:
                d["abbr"] = "{}.{}".format(c_name, item.name)
            d["kind"] = item.type
        elif t is classes.GodotConstant:
            if c_name:
                d["abbr"] = "{}.{} = {}".format(c_name, item.name, item.value)
            else:
                d["abbr"] = "{} = {}".format(item.name, item.value)
            if item.type:
                d["kind"] = item.type
        elif t is classes.GodotMethod:
            args = ", ".join(map(lambda a: "{} {}".format(a.type, a.name), item.args))
            qualifiers = " {}".format(item.qualifiers) if item.qualifiers else ""
            if c_name:
                d["abbr"] = "{}.{}({}){}".format(c_name, item.name, args, qualifiers)
            else:
                d["abbr"] = "{}({}){}".format(item.name, args, qualifiers)
            d["kind"] = item.returns

        # User decls
        elif t is script.VarDecl:
            d["word"] = item.name
            if item.type:
                d["kind"] = item.type
        elif t is script.ConstDecl:
            d["word"] = item.name
            d["abbr"] = "{} = {}".format(item.name, item.value)
        elif t is script.FuncDecl:
            if len(item.args) > 0:
                d["word"] = "{}(".format(item.name)
            else:
                d["word"] = "{}()".format(item.name)
            d["abbr"] = "{}({})".format(item.name, ", ".join(item.args))
        elif t is script.EnumDecl:
            d["kind"] = "enum"
        elif t is script.ClassDecl:
            d["kind"] = "class"
        return d
