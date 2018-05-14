setlocal commentstring=#\ %s

if exists("g:gdscript3_loaded")
    finish
endif
let g:gdscript3_loaded=1

if !has("python3") && !has("python")
    finish
endif

if has("python3")
    let s:pyfile_cmd = "py3file"
    let s:py_cmd = "py3"
else
    let s:pyfile_cmd = "pyfile"
    let s:py_cmd = "py"
endif

execute s:pyfile_cmd . expand('<sfile>:p:h') . "/../python/classes.py"
execute s:pyfile_cmd . expand('<sfile>:p:h') . "/../python/complete.py"

fun! GDScriptComplete(findstart, base)
    if a:findstart == 1
        let line = getline('.')
        let start = col('.') - 1
        " Treat '-' as part of the word when completing in a string.
        if synIDattr(synID(line('.'), col('.')-1, 1), 'name') ==# "gdString"
            let pattern = '[-a-zA-Z0-9_]'
        else
            let pattern = '[a-zA-Z0-9_]'
        endif
        while start > 0 && line[start - 1] =~ pattern
            let start -= 1
        endwhile
        return start
    else
        execute s:py_cmd . " gdscript_complete()"
        if exists("gdscript_completions")
            return gdscript_completions
        else
            return []
        endif
    endif
endfun

set omnifunc=GDScriptComplete
