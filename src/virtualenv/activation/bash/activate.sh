# This file must be used with "source bin/activate" *from bash*
# you cannot run it directly


if [ "${BASH_SOURCE-}" = "$0" ]; then
    echo "You must source this script: \$ source $0" >&2
    exit 33
fi

# Nested activation support -------------------------------------------------
# Activating an environment on top of an already active one parks the previous
# layer's restore state in numbered _VSTASH_* variables. Each ``deactivate``
# call pops one layer, so environments are exited in reverse activation order.
_VIRTUAL_STACK_LEVEL="${_VIRTUAL_STACK_LEVEL:-0}"

_virtualenv_stash () {
    # Store $2 (which may be empty, but must be set) as _VSTASH_$1_<level>.
    _virtualenv_stash_escaped=${2//\'/\'\\\'\'}
    eval "_VSTASH_${1}_${_VIRTUAL_STACK_LEVEL}='$_virtualenv_stash_escaped'"
    unset _virtualenv_stash_escaped
}

_virtualenv_restore () {
    # Restore _VSTASH_$1_<level> into the shell variable named $2.
    # A missing slot means the variable was unset before the layer activated.
    if eval "[ \"\${_VSTASH_${1}_${_VIRTUAL_STACK_LEVEL}+x}\" = x ]" ; then
        eval "${2}=\$_VSTASH_${1}_${_VIRTUAL_STACK_LEVEL}"
        eval "unset _VSTASH_${1}_${_VIRTUAL_STACK_LEVEL}"
    else
        unset "$2"
    fi
}

_virtualenv_park_layer () {
    # Park the active layer's saved state before another activation overlays it.
    _VIRTUAL_STACK_LEVEL=$((_VIRTUAL_STACK_LEVEL + 1))
    [ "${_OLD_VIRTUAL_PATH+x}" = x ] && _virtualenv_stash OLDPATH "$_OLD_VIRTUAL_PATH"
    [ "${_OLD_VIRTUAL_PYTHONHOME+x}" = x ] && _virtualenv_stash PYHOME "$_OLD_VIRTUAL_PYTHONHOME"
    [ "${_OLD_VIRTUAL_TCL_LIBRARY+x}" = x ] && _virtualenv_stash TCL "$_OLD_VIRTUAL_TCL_LIBRARY"
    [ "${_VIRTUAL_TCL_MANAGED+x}" = x ] && _virtualenv_stash TCLM "$_VIRTUAL_TCL_MANAGED"
    [ "${_OLD_VIRTUAL_TK_LIBRARY+x}" = x ] && _virtualenv_stash TK "$_OLD_VIRTUAL_TK_LIBRARY"
    [ "${_VIRTUAL_TK_MANAGED+x}" = x ] && _virtualenv_stash TKM "$_VIRTUAL_TK_MANAGED"
    [ "${_OLD_PKG_CONFIG_PATH+x}" = x ] && _virtualenv_stash PKG "$_OLD_PKG_CONFIG_PATH"
    [ "${_OLD_VIRTUAL_PS1+x}" = x ] && _virtualenv_stash PS1 "$_OLD_VIRTUAL_PS1"
    [ "${VIRTUAL_ENV+x}" = x ] && _virtualenv_stash VENV "$VIRTUAL_ENV"
    [ "${VIRTUAL_ENV_PROMPT+x}" = x ] && _virtualenv_stash VENVP "$VIRTUAL_ENV_PROMPT"
    unset _OLD_VIRTUAL_PATH _OLD_VIRTUAL_PYTHONHOME _OLD_VIRTUAL_TCL_LIBRARY \
        _OLD_VIRTUAL_TK_LIBRARY _OLD_PKG_CONFIG_PATH _OLD_VIRTUAL_PS1 \
        _VIRTUAL_TCL_MANAGED _VIRTUAL_TK_MANAGED
}

_virtualenv_deactivate () {
    # Only a real, active layer manages variables. The initial
    # ``deactivate nondestructive`` wipe (no active environment) must leave
    # pre-existing variables such as PATH untouched.
    if [ -n "${VIRTUAL_ENV:-}" ] ; then
        _virtualenv_active=1
    else
        _virtualenv_active=0
    fi

    # reset old environment variables
    if [ "${_OLD_VIRTUAL_PATH+x}" = x ] ; then
        PATH="$_OLD_VIRTUAL_PATH"
        export PATH
        unset _OLD_VIRTUAL_PATH
    elif [ "$_virtualenv_active" = 1 ] ; then
        unset PATH
    fi
    if [ "${_OLD_VIRTUAL_PYTHONHOME+x}" = x ] ; then
        PYTHONHOME="$_OLD_VIRTUAL_PYTHONHOME"
        export PYTHONHOME
        unset _OLD_VIRTUAL_PYTHONHOME
    fi

    if [ "${_OLD_VIRTUAL_TCL_LIBRARY+x}" ]; then
        TCL_LIBRARY="$_OLD_VIRTUAL_TCL_LIBRARY"
        export TCL_LIBRARY
        unset _OLD_VIRTUAL_TCL_LIBRARY
    elif [ "${_VIRTUAL_TCL_MANAGED:-0}" = 1 ] ; then
        unset TCL_LIBRARY
    fi
    [ "${_VIRTUAL_TCL_MANAGED+x}" = x ] && unset _VIRTUAL_TCL_MANAGED
    if [ "${_OLD_VIRTUAL_TK_LIBRARY+x}" ]; then
        TK_LIBRARY="$_OLD_VIRTUAL_TK_LIBRARY"
        export TK_LIBRARY
        unset _OLD_VIRTUAL_TK_LIBRARY
    elif [ "${_VIRTUAL_TK_MANAGED:-0}" = 1 ] ; then
        unset TK_LIBRARY
    fi
    [ "${_VIRTUAL_TK_MANAGED+x}" = x ] && unset _VIRTUAL_TK_MANAGED
    if [ "${_OLD_PKG_CONFIG_PATH+x}" ]; then
        PKG_CONFIG_PATH="$_OLD_PKG_CONFIG_PATH"
        export PKG_CONFIG_PATH
        unset _OLD_PKG_CONFIG_PATH
    elif [ "$_virtualenv_active" = 1 ] ; then
        # PKG_CONFIG_PATH is always prefixed on activation, so no slot means
        # the variable did not exist before the environment was activated.
        unset PKG_CONFIG_PATH
    fi

    # The hash command must be called to get it to forget past
    # commands. Without forgetting past commands the $PATH changes
    # we made may not be respected
    hash -r 2>/dev/null || true

    # PS1 is a shell variable, not an environment variable, so it is never exported.
    if [ "${_OLD_VIRTUAL_PS1+x}" = x ] ; then
        PS1="$_OLD_VIRTUAL_PS1"
        unset _OLD_VIRTUAL_PS1
    fi

    unset VIRTUAL_ENV
    unset VIRTUAL_ENV_PROMPT

    if [ "${_VIRTUAL_STACK_LEVEL:-0}" -gt 0 ] ; then
        # Reveal the previous layer: hand its saved state back so its own
        # deactivate keeps working, and restore its marker variables.
        _virtualenv_restore OLDPATH _OLD_VIRTUAL_PATH
        _virtualenv_restore PYHOME _OLD_VIRTUAL_PYTHONHOME
        _virtualenv_restore TCL _OLD_VIRTUAL_TCL_LIBRARY
        _virtualenv_restore TCLM _VIRTUAL_TCL_MANAGED
        _virtualenv_restore TK _OLD_VIRTUAL_TK_LIBRARY
        _virtualenv_restore TKM _VIRTUAL_TK_MANAGED
        _virtualenv_restore PKG _OLD_PKG_CONFIG_PATH
        _virtualenv_restore PS1 _OLD_VIRTUAL_PS1
        _virtualenv_restore VENV VIRTUAL_ENV
        [ "${VIRTUAL_ENV+x}" = x ] && export VIRTUAL_ENV
        _virtualenv_restore VENVP VIRTUAL_ENV_PROMPT
        [ "${VIRTUAL_ENV_PROMPT+x}" = x ] && export VIRTUAL_ENV_PROMPT
        _VIRTUAL_STACK_LEVEL=$((_VIRTUAL_STACK_LEVEL - 1))
    else
        unset _VIRTUAL_STACK_LEVEL
        if [ ! "${1-}" = "nondestructive" ] ; then
            # The outermost layer is gone: request the user-facing deactivate
            # wrapper to self-destruct. The wrapper performs the function
            # cleanup itself, because ksh aborts if a function still on the
            # call stack is removed (so the cleanup cannot happen here).
            _VIRTUAL_STACK_FINALIZE=1
            unset -f pydoc
            case "${KSH_VERSION-}" in
                ?*) unalias deactivate 2>/dev/null ;;
            esac
        fi
    fi
    unset _virtualenv_active
}

# ksh expands aliases in both interactive and non-interactive shells, and the
# expanded line runs after the worker returns, so the cleanup happens off the
# call stack. The trailing ':' swallows any arguments (e.g. "nondestructive")
# users may have typed; internal callers invoke _virtualenv_deactivate directly.
case "${KSH_VERSION-}" in
    ?*)
        alias deactivate='_virtualenv_deactivate ; test "${_VIRTUAL_STACK_FINALIZE:-0}" = 1 && { unset _VIRTUAL_STACK_FINALIZE; unset -f _virtualenv_deactivate _virtualenv_stash _virtualenv_restore _virtualenv_park_layer ; } ; : '
        ;;
    *)
        deactivate () {
            _virtualenv_deactivate "$@"
            if [ "${_VIRTUAL_STACK_FINALIZE:-0}" = 1 ] ; then
                unset _VIRTUAL_STACK_FINALIZE
                unset -f _virtualenv_deactivate
                unset -f _virtualenv_stash _virtualenv_restore _virtualenv_park_layer
                unset -f deactivate
            fi
        }
        ;;
esac

# Either park the currently active environment or wipe stale state.
if [ -n "${VIRTUAL_ENV:-}" ] ; then
    _virtualenv_park_layer
else
    # unset irrelevant variables
    _virtualenv_deactivate nondestructive
fi

if [ ! -d __VIRTUAL_ENV__ ]; then
    echo "Virtual environment directory __VIRTUAL_ENV__ does not exist!" >&2
    CURRENT_PATH=$(realpath "${BASH_SOURCE[0]}")
    CURRENT_DIR=$(dirname "${CURRENT_PATH}")
    VIRTUAL_ENV="$(realpath "${CURRENT_DIR}/../")"
else
    VIRTUAL_ENV=__VIRTUAL_ENV__
fi

case "$(uname)" in
    CYGWIN*|MSYS*|MINGW*)
        VIRTUAL_ENV=$(cygpath "$VIRTUAL_ENV")
        ;;
esac
export VIRTUAL_ENV

if [ "${PATH+x}" = x ] ; then
    _OLD_VIRTUAL_PATH="$PATH"
else
    unset _OLD_VIRTUAL_PATH
fi
PATH="$VIRTUAL_ENV/"__BIN_NAME__":$PATH"
export PATH

if [ "${PKG_CONFIG_PATH+x}" = x ] ; then
    _OLD_PKG_CONFIG_PATH="$PKG_CONFIG_PATH"
else
    unset _OLD_PKG_CONFIG_PATH
fi
PKG_CONFIG_PATH="${VIRTUAL_ENV}/lib/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
export PKG_CONFIG_PATH

if [ "x"__VIRTUAL_PROMPT__ != x ] ; then
    VIRTUAL_ENV_PROMPT=__VIRTUAL_PROMPT__
else
    VIRTUAL_ENV_PROMPT=$(basename "$VIRTUAL_ENV")
fi
export VIRTUAL_ENV_PROMPT

# unset PYTHONHOME if set (remember whether it was unset, empty or non-empty)
if [ "${PYTHONHOME+x}" = x ] ; then
    _OLD_VIRTUAL_PYTHONHOME="$PYTHONHOME"
    unset PYTHONHOME
else
    unset _OLD_VIRTUAL_PYTHONHOME
fi

# an empty saved value tells deactivate to unset the variable
if [ __TCL_LIBRARY__ != "" ]; then
    _VIRTUAL_TCL_MANAGED=1
    if [ "${TCL_LIBRARY+x}" = x ] ; then
        _OLD_VIRTUAL_TCL_LIBRARY="$TCL_LIBRARY"
    else
        unset _OLD_VIRTUAL_TCL_LIBRARY
    fi
    TCL_LIBRARY=__TCL_LIBRARY__
    export TCL_LIBRARY
fi

if [ __TK_LIBRARY__ != "" ]; then
    _VIRTUAL_TK_MANAGED=1
    if [ "${TK_LIBRARY+x}" = x ] ; then
        _OLD_VIRTUAL_TK_LIBRARY="$TK_LIBRARY"
    else
        unset _OLD_VIRTUAL_TK_LIBRARY
    fi
    TK_LIBRARY=__TK_LIBRARY__
    export TK_LIBRARY
fi

if [ -z "${VIRTUAL_ENV_DISABLE_PROMPT-}" ] ; then
    if [ "${PS1+x}" = x ] ; then
        _OLD_VIRTUAL_PS1="$PS1"
    else
        unset _OLD_VIRTUAL_PS1
    fi
    PS1="(${VIRTUAL_ENV_PROMPT}) ${PS1-}"
fi

# Make sure to unalias pydoc if it's already there
alias pydoc 2>/dev/null >/dev/null && unalias pydoc || true

pydoc () {
    python -m pydoc "$@"
}

# The hash command must be called to get it to forget past
# commands. Without forgetting past commands the $PATH changes
# we made may not be respected
hash -r 2>/dev/null || true
