setlocal commentstring=#\ %s

if !has("python3")
    finish
endif

execute 'py3file ' . expand('<sfile>:p:h') . "/../python/classes.py"
execute 'py3file ' . expand('<sfile>:p:h') . "/../python/complete.py"

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
        py3 gdscript_complete()
        if exists("gdscript_completions")
            return gdscript_completions
        else
            return []
        endif
    endif
endfun

set omnifunc=GDScriptComplete
