import vim
import re
import os

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

# No preceding tokens:
# - Show locally defined variables and function arguments in current scope.
# - Show members and functions of extended class.
# - Show global scope
# Preceded by 'func':
# - Show virtual functions of extended class.
# Preceded by a built-in type (e.g. Vector2):
# - Show static functions and consts.
# - Show all functions and variables?
# (in string) Preceded by res://:
# - show files in project.

# Order:
# - Local variables
# - Local constants
# - Local functions (excluding overridden)
# - Extended class variables
# - Extended class constants
# - Extended class functions (excluding virtual?)

# Global scope:
# - @GDScript.xml
# - @GlobalScope.xml
# - Built-in types.

# TODO show global scope
# This includes @GDScript and @GlobalScope

# TODO add special completion for 'self'
# Completion in this context is like completing global scope, but only items from
# the extended class are shown.

# TODO complete local vars and function args.
# Possible implementation:
# - From the completion point, look backwards for 'var' and 'const' declns.
#   Only match declns of the same or less indent than the current line.
# - Also search for 'func' and show function arguments IF the the current line
#   is in that function. Stop looking after finding any line starting with 'func'

# TODO recursive token completion.
# e.g. 'Sprite.texture.get_data().*' should examine Sprite for the type of
# 'texture', which is then examined for the type of 'get_data', and so on.
# Use a recursive function that starts with the right-most token and works
# backwards from there. Take into account things like
# ignoring everything inside function parentheses.

# TODO don't do completion in certain contexts.
# - Immediately following 'var', 'const', 'onready', 'for',
# - Anywhere on a line starting with 'signal' or 'class'.
# - Anywhere on a line starting with 'func', except immediately following the keyword.

# TODO complete built-in types following 'extends' and 'export'
# Only complete on 'export' if an open parenthesis is present.

# Flags for selecting what kind of completion items to add.
# There are probably better ways to do this but I'm lazy.
LOCAL = 1
MEMBERS = 2
METHODS = 4
CONSTANTS = 8
ARGS = 16

# I can't figure out how to get the current Python script's directory in this
# context, so let's just use the current vim script instead.
docs_dir = vim.eval("expand('<sfile>:p:h')") + "/../python/godot-docs"
global_scope = {}
classes = {}

# Godot project root directory is cached here.
project_dir = None

def GDScriptComplete():
    base = vim.eval("a:base")

    # Skip regex checks if 'base' is empty.
    # This (probably) helps speed things up when using a completion framework
    # like Deoplete that does it's own searching.
    # It's entirely possible that empty regex matches are optimized out, in
    # which case this is entirely unnecessary.
    if base:
        # Take into account the user's case sensitivity settings.
        ignorecase = int(vim.eval("&ignorecase"))
        smartcase = int(vim.eval("&smartcase"))
        if ignorecase and (not smartcase or not any(x.isupper() for x in base)):
            flags = re.I
        else:
            flags = 0
        base_pattern = re.compile(base, flags)
    else:
        base_pattern = None

    completions = []
    c_name = GetType()
    c = GetClass(c_name)
    if not c:
        return

    col_num = int(vim.eval("col('.')"))
    line = vim.eval("getline('.')")[0:col_num-1]

    # Do file path completion if the cursor is in a string.
    syn_attr = vim.eval("synIDattr(synID(line('.'), col('.')-1, 1), 'name')")
    if syn_attr == "gdString":
        m = re.search("(?<=res://)((\w|-)+/)*$", line)
        if m:
            AddFileCompletions(completions, base_pattern, m.group(0))

    # Only show class functions if preceded by 'func'
    elif re.search("^\s*func", line):
        AddCompletions(completions, c, base_pattern, METHODS | ARGS)
    else:
        AddCompletions(completions, c, base_pattern, MEMBERS | CONSTANTS | METHODS)

    vim.command("let gdscript_completions = " + str(completions))

def AddFileCompletions(completions, pattern, subdir):
    global project_dir

    # Search upwards in the directory tree for 'project.godot',
    # indicating the root of the project.
    if not project_dir:
        cwd = os.getcwd()
        os.chdir(vim.eval("expand('%:p:h')")) # Directory of current file.
        try:
            while not os.path.isfile("project.godot"):
                os.chdir("..")
                if os.getcwd() == "/":
                    return
            project_dir = os.getcwd()
        except Exception:
            pass
        finally:
            os.chdir(cwd)
    if project_dir:
        # Directories and files are grouped and sorted separately.
        dirs = []
        files = []
        dir = "{}/{}".format(project_dir, subdir)
        for entry in os.listdir(dir):
            if not ".import" in entry and (not pattern or pattern.match(entry)):
                if os.path.isdir("{}/{}".format(dir, entry)):
                    dirs.append({
                        "word": entry,
                        "abbr": "{}/".format(entry) })
                else:
                    files.append({"word": entry})
        dirs.sort(key=lambda c: c["word"])
        files.sort(key=lambda c: c["word"])
        for d in dirs:
           completions.append(d)
        for f in files:
            completions.append(f)

def AddCompletions(completions, c, pattern, flags):
    if not c:
        return
    if flags & MEMBERS:
        AddMemberCompletions(completions, c, pattern)
    if flags & METHODS:
        AddMethodCompletions(completions, c, pattern, flags & ARGS)
    if flags & CONSTANTS:
        AddConstantCompletions(completions, c, pattern)

    # Recursively add inherited classes.
    if "inherits" in c:
        AddCompletions(completions, GetClass(c["inherits"]), pattern, flags)

def AddMemberCompletions(completions, c, pattern):
    if not c:
        return
    for member in c["members"]:
        if pattern and not pattern.match(member["name"]):
            continue
        completion = {
                "word": member["name"],
                "abbr": "{}.{}".format(c["name"], member["name"]),
                "kind": member["type"],
                "dup": 1,
                "icase": int(pattern.flags & re.I if pattern else 0) }
        completions.append(completion)

def AddConstantCompletions(completions, c, pattern):
    if not c:
        return
    for constant in c["constants"]:
        if pattern and not pattern.match(constant["name"]):
            continue
        completion = {
                "word": constant["name"],
                "abbr": "{}.{}".format(c["name"], constant["name"]),
                "kind": constant["type"],
                "dup": 1,
                "icase": int(pattern.flags & re.I if pattern else 0) }
        if "value" in constant:
            completion["abbr"] += " = {}".format(constant["value"])
        completions.append(completion)

# If 'complete_args' is True, method arguments are added to completions.
def AddMethodCompletions(completions, c, pattern, complete_args):
    if not c:
        return
    c_name = c["name"]
    for method in c["methods"]:
        if pattern and not pattern.match(method["name"]):
            continue
        name = c_name if method["name"] == c_name else "{}.{}".format(c_name, method["name"])
        args = []
        if complete_args:
            word_args = []
        for arg in method["arguments"]:
            args.append("{} {}{}".format(arg["type"], arg["name"],
                "=" + arg["default"] if "default" in arg else ""))
            if complete_args:
                word_args.append(arg["name"])
        qualifiers = method.get("qualifiers", "")
        if "vararg" in qualifiers:
            args.append("...")
        if complete_args:
            word = "{}({}):".format(method["name"], ", ".join(word_args))
        else:
            word = "{}".format(method["name"])
        # signature = "{} {}({}) {}".format(method["returntype"], name, ", ".join(args), qualifiers)
        signature = "{}({}) {}".format(name, ", ".join(args), qualifiers)
        completion = {
                "word": word,
                "abbr": signature,
                "kind": method["returntype"],
                "dup": 1,
                "icase": int(pattern.flags & re.I if pattern else 0) }
        completions.append(completion)

def GetPrecedingType(cursor_pos, depth=0):
    pass

def GetType():
    # Search for 'extends' statement starting from the top.
    for i in range(1, int(vim.eval("line('$')"))):
        line = vim.eval("getline({})".format(i))
        if not line.strip():
            continue
        m = re.search("(?<=^extends)\s+\w+", line)
        if m:
            return m.group(0).strip()
        elif not re.match("^\s*tool\s*$", line):
            # Give up when encountering a line that isn't 'extends' or 'tool'.
            return None

def GetClass(name):
    if not name or name not in classes:
        classes[name] = ParseClass(name)
    return classes[name]

# Load the XML doc file for the given class and parse the relevant parts into a dict.
def ParseClass(name):
    if not name:
        return
    path = "{}/{}.xml".format(docs_dir, name)
    try:
        c = {"members": [], "constants": [], "methods": []}
        current_method = None
        for event, elem in ET.iterparse(path, events=("start", "end")):
            attrib = elem.attrib
            if event == "start":
                if elem.tag == "class":
                    c["name"] = attrib["name"]
                    if "inherits" in attrib:
                        c["inherits"] = attrib["inherits"]
                elif elem.tag == "member":
                    member = {}
                    member["name"] = attrib["name"]
                    if "enum" in attrib:
                        member["type"] = attrib["enum"]
                    else:
                        member["type"] = attrib["type"]
                    c["members"].append(member)
                elif elem.tag == "constant":
                    constant = {}
                    constant["name"] = attrib["name"]
                    if "enum" in attrib:
                        constant["type"] = attrib["enum"]
                    else:
                        constant["type"] = "int"
                    if "value" in attrib:
                        constant["value"] = int(attrib["value"])
                    c["constants"].append(constant)
                elif elem.tag == "method":
                    current_method = { "arguments": [] }
                    current_method["name"] = attrib["name"]
                    if "qualifiers" in attrib:
                        current_method["qualifiers"] = attrib["qualifiers"]
                    c["methods"].append(current_method)
                elif elem.tag == "argument":
                    args = current_method["arguments"]
                    arg = {}
                    arg["name"] = attrib["name"]
                    arg["type"] = attrib["type"]
                    if "default" in attrib:
                        arg["default"] = attrib["default"]
                    index = int(attrib["index"])
                    while len(args) <= index:
                        args.append(None)
                    args[index] = arg
                elif elem.tag == "return":
                    if "enum" in attrib:
                        current_method["returntype"] = attrib["enum"]
                    else:
                        current_method["returntype"] = attrib["type"]
            else:
                elem.clear()
    except Exception:
        return None
    return c

