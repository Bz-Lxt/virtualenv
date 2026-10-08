# This file must be used using `source bin/activate.fish` *within a running fish ( http://fishshell.com ) session*.
# Do not run it directly.

# Nested activation support --------------------------------------------------
# Activating one environment while another is active parks the outer layer's
# saved state in numbered __vs_* variables.  Each `deactivate` call pops one
# layer, so environments are exited in reverse activation order.
if not set -q __vsvl
    set -g __vsvl 0
end

function __virtualenv_stash -d "Park a saved (possibly empty) value for the current nested activation layer." -a key
    set -l lvl $__vsvl
    set -g __vs_$key\_$lvl $argv[2..]
end

function __virtualenv_pop -d "Restore a parked value (or unset its target) when leaving a layer." -a key dest
    set -l lvl $__vsvl
    set -l slot __vs_$key\_$lvl
    if set -q $slot
        eval set -g $dest \$$slot
        set -e $slot
    else
        set -e $dest
    end
end

function __virtualenv_park -d "Park the active layer before a new activation overlays it."
    set -g __vsvl (math $__vsvl + 1)
    if set -q _OLD_VIRTUAL_PATH
        __virtualenv_stash PATH $_OLD_VIRTUAL_PATH
    end
    if set -q _OLD_VIRTUAL_PYTHONHOME
        __virtualenv_stash PYHOME $_OLD_VIRTUAL_PYTHONHOME
    end
    if set -q _OLD_VIRTUAL_TCL_LIBRARY
        __virtualenv_stash TCL $_OLD_VIRTUAL_TCL_LIBRARY
    end
    if set -q __v_tcm
        __virtualenv_stash TCLM $__v_tcm
    end
    if set -q _OLD_VIRTUAL_TK_LIBRARY
        __virtualenv_stash TK $_OLD_VIRTUAL_TK_LIBRARY
    end
    if set -q __v_tkm
        __virtualenv_stash TKM $__v_tkm
    end
    if set -q _OLD_PKG_CONFIG_PATH
        __virtualenv_stash PKG $_OLD_PKG_CONFIG_PATH
    end
    if set -q VIRTUAL_ENV
        __virtualenv_stash VENV $VIRTUAL_ENV
    end
    if set -q VIRTUAL_ENV_PROMPT
        __virtualenv_stash VENVP $VIRTUAL_ENV_PROMPT
    end
    set -e _OLD_VIRTUAL_PATH
    set -e _OLD_VIRTUAL_PYTHONHOME
    set -e _OLD_VIRTUAL_TCL_LIBRARY
    set -e _OLD_VIRTUAL_TK_LIBRARY
    set -e _OLD_PKG_CONFIG_PATH
    set -e __v_tcm
    set -e __v_tkm
end

function deactivate -d 'Exit virtualenv mode and return to the normal environment.'
    # A real, active layer manages variables; the initial "nondestructive"
    # wipe (no active environment) must leave pre-existing variables alone.
    set -l __vs_active 0
    if set -q VIRTUAL_ENV
        set __vs_active 1
    end

    # reset old environment variables
    if set -q _OLD_VIRTUAL_PATH
        set -gx PATH $_OLD_VIRTUAL_PATH
        set -e _OLD_VIRTUAL_PATH
    else if test $__vs_active -eq 1
        set -e PATH
    end

    if set -q _OLD_VIRTUAL_TCL_LIBRARY
        set -gx TCL_LIBRARY "$_OLD_VIRTUAL_TCL_LIBRARY"
        set -e _OLD_VIRTUAL_TCL_LIBRARY
    else if set -q __v_tcm
        set -e TCL_LIBRARY
    end
    set -e __v_tcm
    if set -q _OLD_VIRTUAL_TK_LIBRARY
        set -gx TK_LIBRARY "$_OLD_VIRTUAL_TK_LIBRARY"
        set -e _OLD_VIRTUAL_TK_LIBRARY
    else if set -q __v_tkm
        set -e TK_LIBRARY
    end
    set -e __v_tkm

    if set -q _OLD_PKG_CONFIG_PATH
        # PKG_CONFIG_PATH is a path variable in fish, so restore the saved list as-is.
        set -gx PKG_CONFIG_PATH $_OLD_PKG_CONFIG_PATH
        set -e _OLD_PKG_CONFIG_PATH
    else if test $__vs_active -eq 1
        # PKG_CONFIG_PATH is always prefixed on activation, so no slot means
        # the variable did not exist before the environment was activated.
        set -e PKG_CONFIG_PATH
    end

    if set -q _OLD_VIRTUAL_PYTHONHOME
        set -gx PYTHONHOME "$_OLD_VIRTUAL_PYTHONHOME"
        set -e _OLD_VIRTUAL_PYTHONHOME
    end

    # Prompt chain: the predecessor fish_prompt for this layer was copied as
    # __vs_chain_<layer> when the layer activated (only if prompt override ran).
    set -l __vs_lvl (math $__vsvl + 1)
    if set -q __vs_prompt_$__vs_lvl
        set -e __vs_prompt_$__vs_lvl
        # Set an empty local `$fish_function_path` to allow removal of `fish_prompt` via `functions -e`.
        set -l fish_function_path
        builtin functions -e fish_prompt
        builtin functions -c __vs_chain_$__vs_lvl fish_prompt
        builtin functions -e __vs_chain_$__vs_lvl
    end

    set -e VIRTUAL_ENV
    set -e VIRTUAL_ENV_PROMPT

    if test $__vsvl -gt 0
        # Reveal the previous layer: hand its saved state back so its own
        # deactivate keeps working, and restore its marker variables.
        __virtualenv_pop PATH _OLD_VIRTUAL_PATH
        __virtualenv_pop PYHOME _OLD_VIRTUAL_PYTHONHOME
        __virtualenv_pop TCL _OLD_VIRTUAL_TCL_LIBRARY
        __virtualenv_pop TCLM __v_tcm
        __virtualenv_pop TK _OLD_VIRTUAL_TK_LIBRARY
        __virtualenv_pop TKM __v_tkm
        __virtualenv_pop PKG _OLD_PKG_CONFIG_PATH
        __virtualenv_pop VENV VIRTUAL_ENV
        __virtualenv_pop VENVP VIRTUAL_ENV_PROMPT
        set -g __vsvl (math $__vsvl - 1)
    else
        if test "$argv[1]" != 'nondestructive'
            # Self-destruct!
            builtin functions -e pydoc
            builtin functions -e deactivate
            builtin functions -e __virtualenv_stash
            builtin functions -e __virtualenv_pop
            builtin functions -e __virtualenv_park
            set -e __vsvl
        end
    end
end

# Either park the currently active environment or wipe stale state.
if set -q VIRTUAL_ENV
    __virtualenv_park
else
    # Unset irrelevant variables.
    deactivate nondestructive
end

set -gx VIRTUAL_ENV __VIRTUAL_ENV__
if string match -qr 'CYGWIN|MSYS|MINGW' (uname)
    set -gx VIRTUAL_ENV (cygpath -u $VIRTUAL_ENV)
end

if set -q PKG_CONFIG_PATH
    # Keep the path variable's list form (empty elements are preserved).
    set -gx _OLD_PKG_CONFIG_PATH $PKG_CONFIG_PATH
    if test -n "$PKG_CONFIG_PATH"
        set -gx PKG_CONFIG_PATH "$VIRTUAL_ENV/lib/pkgconfig" $PKG_CONFIG_PATH
    else
        set -gx PKG_CONFIG_PATH "$VIRTUAL_ENV/lib/pkgconfig"
    end
else
    set -e _OLD_PKG_CONFIG_PATH
    set -gx PKG_CONFIG_PATH "$VIRTUAL_ENV/lib/pkgconfig"
end

set -gx _OLD_VIRTUAL_PATH $PATH
set -gx PATH "$VIRTUAL_ENV"'/'__BIN_NAME__ $PATH

if test -n __TCL_LIBRARY__
    set -g __v_tcm 1
    if set -q TCL_LIBRARY
        set -gx _OLD_VIRTUAL_TCL_LIBRARY "$TCL_LIBRARY"
    else
        set -e _OLD_VIRTUAL_TCL_LIBRARY
    end
    set -gx TCL_LIBRARY '__TCL_LIBRARY__'
end
if test -n __TK_LIBRARY__
    set -g __v_tkm 1
    if set -q TK_LIBRARY
        set -gx _OLD_VIRTUAL_TK_LIBRARY "$TK_LIBRARY"
    else
        set -e _OLD_VIRTUAL_TK_LIBRARY
    end
    set -gx TK_LIBRARY '__TK_LIBRARY__'
end

# Prompt override provided?
# If not, just use the environment name.
if test -n __VIRTUAL_PROMPT__
    set -gx VIRTUAL_ENV_PROMPT __VIRTUAL_PROMPT__
else
    set -gx VIRTUAL_ENV_PROMPT (basename "$VIRTUAL_ENV")
end

# Unset `$PYTHONHOME` if set (remember whether it was unset, empty or non-empty).
if set -q PYTHONHOME
    set -gx _OLD_VIRTUAL_PYTHONHOME $PYTHONHOME
    set -e PYTHONHOME
else
    set -e _OLD_VIRTUAL_PYTHONHOME
end

function pydoc
    python -m pydoc $argv
end

if test -z "$VIRTUAL_ENV_DISABLE_PROMPT"
    # Number of the layer being activated (one more than the parked count).
    set -l __vs_lvl (math $__vsvl + 1)
    set -g __vs_prompt_$__vs_lvl 1

    # Copy the current `fish_prompt` function as this layer's predecessor.
    builtin functions -c fish_prompt __vs_chain_$__vs_lvl

    # Route every builtin the prompt path uses through `builtin` so a user function that shadows
    # `printf`, `string`, `echo`, or `source`/`.` cannot hijack the prompt (Issue #93858 follow-up,
    # CPython gh-140006). A dot-style directory navigator redefining `.` is the common trigger.
    # The predecessor's name is baked into the generated function so each layer
    # calls the wrapper directly below it (or the original prompt for layer 1).
    eval "function fish_prompt
        set -l old_status \$status
        set -l prompt (__vs_chain_$__vs_lvl)

        builtin printf '(%s) ' \$VIRTUAL_ENV_PROMPT

        builtin string join -- \\n \$prompt # handle multi-line prompts
        builtin echo \"exit \$old_status\" | builtin source -
    end"
end
