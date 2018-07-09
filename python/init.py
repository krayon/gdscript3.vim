import sys
import re
import vim

sys.path.append(vim.eval("expand('<sfile>:p:h')") + "/../python/")

import util
import completer
import classes
import script

def gdscript_complete():
    util.clear_cursor_cache()
    completer.clear_completions()

    line = util.get_line()[0:util.get_cursor_col_num()]
    syn_attr = util.get_syn_attr()
    if syn_attr == "gdComment":
        return
    elif syn_attr == "gdString":
        completer.complete_paths()
    elif re.match("(\s*class\s+\w+\s+)?extends\s*", line):
        completer.complete_class_names(classes.EXTENDABLE)
    elif re.match("export\(\s*", line):
        completer.complete_class_names(classes.EXPORTABLE)
    else:
        completer.complete_globals()

    completions = completer.get_completions()
    vim.command("let gdscript_completions = " + str(completions))

# TODO: implement
def echodoc_search():
    pass
