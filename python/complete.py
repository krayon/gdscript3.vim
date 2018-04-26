import vim
import re
import os

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

# Flags for selecting which completion items to add.
# There are probably better ways to do this but I'm lazy.
MEMBERS = 1
CONSTANTS = 2
METHODS = 4

classes = GodotClasses()

def gdscript_complete():
    base = vim.eval("a:base")
    completions = []

    # Only consider the part of the line before the cursor.
    col = get_col() - 1
    line = get_line()[0:col]

    if get_syn_attr() == "gdString":
        # Complete file paths (res://) if cursor is in a string.
        complete_paths(completions, line)
    elif re.match("(extends\s+|export\()\s*\w*$", line):
        # Complete class names following 'extends' or 'export'.
        complete_class_names(completions)
    elif line and line[-1] == ".":
        # When accessing a value via dot notation, try to guess the type of the
        # value preceding the dot. This works recursively, so chaining dot
        # accessors works as expected if all the intermediary values are
        # built-in members or methods.

        # Handle 'self' separately.
        if re.match("[^a-zA-Z0-9_.]self", line[col-6:col]):
            complete_self(completions)
        else:
            complete_dot(completions, line)
    elif re.match("\s*func", line):
        # Complete functions belonging to the extended type if the cursor is
        # preceded by the 'func' keyword. In this context, the user might be
        # trying to override a built-in function, so the entire function
        # signature is completed including args.
        complete_funcs_with_args(completions, get_extended_class())
    else:
        # Complete members/methods of the extended type as well as
        # global scope and user-defined vars/methods.
        complete_global(completions)

    # Take into account the user's case sensitivity settings.
    ignorecase = int(vim.eval("&ignorecase"))
    smartcase = int(vim.eval("&smartcase"))
    flags = 0
    if ignorecase and (not smartcase or not any(x.isupper() for x in base)):
        flags = re.I

    # Filter completions
    if base:
        completions = [c for c in completions if re.match(base, c["word"], flags)]

    for completion in completions:
        completion["icase"] = int(flags & re.I)

    vim.command("let gdscript_completions = " + str(completions))

def add_class_completions(completions, c, flags):
    def map_fun(x):
        return x.get_completion()

    if not c:
        return

    if flags & MEMBERS:
        completions.extend(map(map_fun, c.iter_members()))
    if flags & CONSTANTS:
        completions.extend(map(map_fun, c.iter_constants()))
    if flags & METHODS:
        completions.extend(map(map_fun, c.iter_methods()))

    add_class_completions(completions, c.get_parent(), flags)

def complete_paths(completions, line):
    m = re.search("res://(((\w|-)+/)*)$", line)
    if m:
        project_dir = get_project_dir()
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
            completions.append(d)
        for f in files:
            completions.append(f)

def complete_class_names(completions):
    def map_fun(c_name):
        return {"word": c_name, "dup": 1}
    completions.extend(map(map_fun, classes.iter_class_names()))

def complete_self(completions):
    c = get_extended_class()
    complete_user(completions)
    add_class_completions(completions, c, MEMBERS | METHODS)

def complete_dot(completions, line):
    (c, is_static) = get_preceding_class(line, get_col() - 2)
    if c:
        if is_static:
            add_class_completions(completions, c, CONSTANTS)
        else:
            add_class_completions(completions, c, MEMBERS | METHODS)


def complete_funcs_with_args(completions, c):
    def map_fun(f):
        return f.get_completion_with_args()
    if c:
        completions.extend(map(map_fun, c.iter_methods()))
        complete_funcs_with_args(completions, c.get_parent())


def complete_global(completions):
    c = get_extended_class()
    flags = MEMBERS | CONSTANTS | METHODS
    complete_user(completions)
    add_class_completions(completions, c, flags)
    add_class_completions(completions, classes.get_global_scope(), flags)
    complete_class_names(completions)

# Gather user-defined vars and funcs.
# Only items accessible from the current scope are added.
def complete_user(completions):
    line = get_line()[0:get_col()-1]
    lnum = int(vim.eval("line('.')"))
    if line.lstrip():
        indent = int(vim.eval("indent({})".format(lnum)))
    else:
        # Remember that only the part of the line up to the cursor is considered.
        # If that part of the line is empty, but the entire line is not, vim's
        # indent() function will not return the desired result.
        # In this case, the cursor pos is used instead.
        indent = get_col() - 1

    # Ignore all function arguments after the first encountered function.
    found_func = False
    for prev_lnum in reversed(range(lnum)):
        line = vim.eval("getline({})".format(prev_lnum)).lstrip()
        if not line:
            continue
        prev_indent = int(vim.eval("indent({})".format(prev_lnum)))
        if prev_indent > indent:
            continue
        if line.startswith("func"):
            m = re.match("^func\s+(\w+)\(((\w|,|\s)*)\)", line)
            if m:
                if not found_func and indent > prev_indent:
                    found_func = True
                    for group in m.group(2).split(","):
                        completions.append({"word": group.strip(), "kind": "(local arg)"})
                completions.append({
                    "word": "{}(".format(m.group(1)),
                    "abbr": "{}({})".format(m.group(1), m.group(2)),
                    "kind": "(local func)"
                })
                indent = prev_indent
        elif re.match("^class\s+\w+", line):
            indent = prev_indent
        elif line.startswith("var") or line.startswith("const"):
            m = re.match("(var|const)\s(\w+)", line)
            if m:
                completions.append({"word": m.group(2), "kind": "(local {})".format(m.group(1))})

# Examine the token(s) before a dot accessor and try to figure out the type.
# Returns a tuple (GodotClass, bool).
# The bool indicates whether the class is being statically accessed.
# This whole thing is pretty messy but I'm afraid to change any of it.
def get_preceding_class(line, cursor_pos):
    start = cursor_pos
    is_method = False
    paren_count = 0
    search_global = False
    c = None

    # Dot accessor after string literal.
    if get_syn_attr(col=cursor_pos) == "gdString":
        return (classes.get_class("String"), False)

    for i, char in enumerate(line[cursor_pos - 1::-1]):
        if char == ")":
            is_method = True
            paren_count += 1
        elif char == "(":
            paren_count -= 1
            if paren_count == 0:
                cursor_pos = start - i -1
                continue
        elif paren_count == 0 and not char.isalnum() and char != "_":
            if char == ".":
                c = get_preceding_class(line, start - i - 1)[0]
            else:
                c = get_extended_class()
                # Complete only extended class after 'self'.
                if line[start - i:cursor_pos] == "self":
                    return (c, False)
                search_global = True
            break
    token = line[start - i:cursor_pos]
    type_name = None
    if is_method:
        method = c.get_method(token, search_parent=True)
        if not method and search_global:
            method = classes.get_global_scope().get_method(token)
        if method:
            type_name = method.get_return_type()
    else:
        member = c.get_member(token, search_parent=True)
        if not member and search_global:
            member = classes.get_global_scope().get_member(token)
        if member:
            type_name = member.get_type()
        elif search_global and classes.is_class(token):
            return (classes.get_class(token), True)
    if type_name and type_name != "void":
        return (classes.get_class(type_name), False)
    else:
        return (None, False)

def get_extended_class():
    # Search for 'extends' statement starting from the top.
    for i in range(1, int(vim.eval("line('$')"))):
        line = vim.eval("getline({})".format(i))
        if not line.strip():
            continue
        m = re.match("^extends\s+(\w+)", line)
        if m:
            return classes.get_class(m.group(1))
        elif not re.match("^\s*tool\s*$", line):
            # Give up when encountering a line that isn't 'extends' or 'tool'.
            return None

def get_line():
    return vim.eval("getline('.')")


def get_col():
    return int(vim.eval("col('.')"))

def get_syn_attr(line=None, col=None):
    if not line:
        line = "."
    if not col:
        col = "."
    return vim.eval("synIDattr(synID(line('{}'), col('{}')-1, 1), 'name')".
            format(line, col))


# Get the root directory of the Godot project containing the current script.
# This is for completing 'res://'
_project_dir = None
def get_project_dir():
    global _project_dir
    if not _project_dir:
        cwd = os.getcwd()
        os.chdir(vim.eval("expand('%:p:h')")) # Directory of current file.
        try:
            while not os.path.isfile("project.godot"):
                os.chdir("..")
                if os.getcwd() == "/":
                    return
            _project_dir = os.getcwd()
        except:
            pass
        finally:
            os.chdir(cwd)
    return _project_dir

