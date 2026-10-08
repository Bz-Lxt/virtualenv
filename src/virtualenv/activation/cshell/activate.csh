# This file must be used with "source bin/activate.csh" *from csh*.
# You cannot run it directly.
# Created by Davide Di Blasi <davidedb@gmail.com>.

set newline='\
'

# Nested activation support --------------------------------------------------
# Each activation parks the previous layer's state in numbered shell
# variables (_VSL is the stack depth).  Every ``deactivate`` call pops one
# layer, so environments are exited in reverse activation order.
if (! $?_VSL) set _VSL = 0

# Expanded deactivate body (single quotes are encoded as '"'"' below):
#   test $?VIRTUAL_ENV != 0 && set _va = 1; test $?VIRTUAL_ENV == 0 && set _va = 0
# marks whether a real layer was active (the initial "nondestructive" wipe has
# none and must leave pre-existing variables such as PKG_CONFIG_PATH alone).
#   Live values are restored from _OLD_*; then the previous layer's slots are
# popped back into _OLD_* and the markers.  When the stack is empty the
# deactivate and pydoc aliases self-destruct.
alias deactivate 'test $?VIRTUAL_ENV != 0 && set _va = 1; test $?VIRTUAL_ENV == 0 && set _va = 0; test $?_OLD_VIRTUAL_PATH != 0 && setenv PATH "$_OLD_VIRTUAL_PATH:q" && unset _OLD_VIRTUAL_PATH; rehash; test $?_OLD_VIRTUAL_TCL_LIBRARY != 0 && set _vt = 1; test $?_OLD_VIRTUAL_TCL_LIBRARY == 0 && set _vt = 0; test "$_vt" == "1" && setenv TCL_LIBRARY "$_OLD_VIRTUAL_TCL_LIBRARY:q" && unset _OLD_VIRTUAL_TCL_LIBRARY; test "$_vt" == "0" && test $?_VTCM != 0 && test "$_VTCM:q" == "1" && unsetenv TCL_LIBRARY; unset _vt; unset _VTCM; test $?_OLD_VIRTUAL_TK_LIBRARY != 0 && set _vk = 1; test $?_OLD_VIRTUAL_TK_LIBRARY == 0 && set _vk = 0; test "$_vk" == "1" && setenv TK_LIBRARY "$_OLD_VIRTUAL_TK_LIBRARY:q" && unset _OLD_VIRTUAL_TK_LIBRARY; test "$_vk" == "0" && test $?_VTKM != 0 && test "$_VTKM:q" == "1" && unsetenv TK_LIBRARY; unset _vk; unset _VTKM; test $?_OLD_PKG_CONFIG_PATH != 0 && set _vp = 1; test $?_OLD_PKG_CONFIG_PATH == 0 && set _vp = 0; test "$_vp" == "1" && setenv PKG_CONFIG_PATH "$_OLD_PKG_CONFIG_PATH:q" && unset _OLD_PKG_CONFIG_PATH; test "$_vp" == "0" && test "$_va" == "1" && unsetenv PKG_CONFIG_PATH; unset _vp; test $?_OLD_VIRTUAL_PROMPT != 0 && set prompt="$_OLD_VIRTUAL_PROMPT:q" && unset _OLD_VIRTUAL_PROMPT; unsetenv VIRTUAL_ENV; unsetenv VIRTUAL_ENV_PROMPT; set _vpop = 0; test $?_VSL != 0 && test $_VSL != 0 && @ _vsl = $_VSL; test $?_vsl != 0 && set _vpop = 1; test $?_vsl != 0 && eval '"'"'set _OLD_VIRTUAL_PATH = "$_VSP_PATH'"'"'$_vsl'"'"':q"'"'"'; test $?_vsl != 0 && eval '"'"'unset _VSP_PATH'"'"'$_vsl; test $?_vsl != 0 && eval '"'"'set _h = $_VSH_TCL'"'"'$_vsl; test $?_h != 0 && test "$_h:q" == "1" && eval '"'"'set _OLD_VIRTUAL_TCL_LIBRARY = "$_VSP_TCL'"'"'$_vsl'"'"':q"'"'"'; test $?_h != 0 && unset _h; test $?_vsl != 0 && eval '"'"'unset _VSH_TCL'"'"'$_vsl'"'"' _VSP_TCL'"'"'$_vsl; test $?_vsl != 0 && eval '"'"'set _h = $_VSH_TCLM'"'"'$_vsl; test $?_vsl != 0 && test $?_h != 0 && eval '"'"'set _VTCM = "$_h:q"'"'"'; test $?_vsl != 0 && test $?_h != 0 && unset _h; test $?_vsl != 0 && eval '"'"'unset _VSH_TCLM'"'"'$_vsl; test $?_vsl != 0 && eval '"'"'set _h = $_VSH_TK'"'"'$_vsl; test $?_h != 0 && test "$_h:q" == "1" && eval '"'"'set _OLD_VIRTUAL_TK_LIBRARY = "$_VSP_TK'"'"'$_vsl'"'"':q"'"'"'; test $?_h != 0 && unset _h; test $?_vsl != 0 && eval '"'"'unset _VSH_TK'"'"'$_vsl'"'"' _VSP_TK'"'"'$_vsl; test $?_vsl != 0 && eval '"'"'set _h = $_VSH_TKM'"'"'$_vsl; test $?_vsl != 0 && test $?_h != 0 && eval '"'"'set _VTKM = "$_h:q"'"'"'; test $?_vsl != 0 && test $?_h != 0 && unset _h; test $?_vsl != 0 && eval '"'"'unset _VSH_TKM'"'"'$_vsl; test $?_vsl != 0 && eval '"'"'set _h = $_VSH_PKG'"'"'$_vsl; test $?_h != 0 && test "$_h:q" == "1" && eval '"'"'set _OLD_PKG_CONFIG_PATH = "$_VSP_PKG'"'"'$_vsl'"'"':q"'"'"'; test $?_h != 0 && unset _h; test $?_vsl != 0 && eval '"'"'unset _VSH_PKG'"'"'$_vsl'"'"' _VSP_PKG'"'"'$_vsl; test $?_vsl != 0 && eval '"'"'set _h = $_VSH_PROMPT'"'"'$_vsl; test $?_h != 0 && test "$_h:q" == "1" && eval '"'"'set _OLD_VIRTUAL_PROMPT = "$_VSP_PROMPT'"'"'$_vsl'"'"':q"'"'"'; test $?_h != 0 && unset _h; test $?_vsl != 0 && eval '"'"'unset _VSH_PROMPT'"'"'$_vsl'"'"' _VSP_PROMPT'"'"'$_vsl; test $?_vsl != 0 && eval '"'"'setenv VIRTUAL_ENV "$_VSP_VENV'"'"'$_vsl'"'"':q"'"'"'; test $?_vsl != 0 && eval '"'"'setenv VIRTUAL_ENV_PROMPT "$_VSP_VENVP'"'"'$_vsl'"'"':q"'"'"'; test $?_vsl != 0 && eval '"'"'unset _VSP_VENV'"'"'$_vsl'"'"' _VSP_VENVP'"'"'$_vsl; test $?_vsl != 0 && @ _VSL = $_VSL - 1; test $?_VSL != 0 && test $_VSL == 0 && unset _VSL; test $?_vsl != 0 && unset _vsl; unset _va; test "$_vpop" == "0" && test "\!:*" != "nondestructive" && unalias deactivate && unalias pydoc; unset _vpop'

# Park the currently active layer, or wipe stale state when nothing is active.
if ($?VIRTUAL_ENV) then
    @ _VSL = $_VSL + 1
    if ($?_OLD_VIRTUAL_PATH) eval 'set _VSP_PATH'$_VSL' = "$_OLD_VIRTUAL_PATH:q"'
    if ($?_VTCM) then
        eval 'set _VSH_TCLM'$_VSL' = "$_VTCM:q"'
    else
        eval 'set _VSH_TCLM'$_VSL' = 0'
    endif
    if ($?_VTKM) then
        eval 'set _VSH_TKM'$_VSL' = "$_VTKM:q"'
    else
        eval 'set _VSH_TKM'$_VSL' = 0'
    endif
    if ($?_OLD_VIRTUAL_TCL_LIBRARY) then
        eval 'set _VSH_TCL'$_VSL' = 1'
        eval 'set _VSP_TCL'$_VSL' = "$_OLD_VIRTUAL_TCL_LIBRARY:q"'
    else
        eval 'set _VSH_TCL'$_VSL' = 0'
    endif
    if ($?_OLD_VIRTUAL_TK_LIBRARY) then
        eval 'set _VSH_TK'$_VSL' = 1'
        eval 'set _VSP_TK'$_VSL' = "$_OLD_VIRTUAL_TK_LIBRARY:q"'
    else
        eval 'set _VSH_TK'$_VSL' = 0'
    endif
    if ($?_OLD_PKG_CONFIG_PATH) then
        eval 'set _VSH_PKG'$_VSL' = 1'
        eval 'set _VSP_PKG'$_VSL' = "$_OLD_PKG_CONFIG_PATH:q"'
    else
        eval 'set _VSH_PKG'$_VSL' = 0'
    endif
    if ($?_OLD_VIRTUAL_PROMPT) then
        eval 'set _VSH_PROMPT'$_VSL' = 1'
        eval 'set _VSP_PROMPT'$_VSL' = "$_OLD_VIRTUAL_PROMPT:q"'
    else
        eval 'set _VSH_PROMPT'$_VSL' = 0'
    endif
    eval 'set _VSP_VENV'$_VSL' = "$VIRTUAL_ENV:q"'
    eval 'set _VSP_VENVP'$_VSL' = "$VIRTUAL_ENV_PROMPT:q"'
    unset _OLD_VIRTUAL_PATH _OLD_VIRTUAL_TCL_LIBRARY _OLD_VIRTUAL_TK_LIBRARY _OLD_PKG_CONFIG_PATH _OLD_VIRTUAL_PROMPT _VTCM _VTKM
else
    # Unset irrelevant variables.
    deactivate nondestructive
endif

setenv VIRTUAL_ENV __VIRTUAL_ENV__

set _OLD_VIRTUAL_PATH="$PATH:q"
setenv PATH "$VIRTUAL_ENV:q/"__BIN_NAME__":$PATH:q"

if ($?PKG_CONFIG_PATH) then
    set _OLD_PKG_CONFIG_PATH="$PKG_CONFIG_PATH"
    if ("$PKG_CONFIG_PATH:q" == "") then
        setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig"
    else
        setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig:${PKG_CONFIG_PATH}"
    endif
else
    unset _OLD_PKG_CONFIG_PATH
    setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig"
endif

if (__TCL_LIBRARY__ != "") then
    set _VTCM = 1
    if ($?TCL_LIBRARY) then
        set _OLD_VIRTUAL_TCL_LIBRARY="$TCL_LIBRARY"
    else
        unset _OLD_VIRTUAL_TCL_LIBRARY
    endif
    setenv TCL_LIBRARY __TCL_LIBRARY__
endif

if (__TK_LIBRARY__ != "") then
    set _VTKM = 1
    if ($?TK_LIBRARY) then
        set _OLD_VIRTUAL_TK_LIBRARY="$TK_LIBRARY"
    else
        unset _OLD_VIRTUAL_TK_LIBRARY
    endif
    setenv TK_LIBRARY __TK_LIBRARY__
endif

if (__VIRTUAL_PROMPT__ != "") then
    setenv VIRTUAL_ENV_PROMPT __VIRTUAL_PROMPT__
else
    setenv VIRTUAL_ENV_PROMPT "$VIRTUAL_ENV:t:q"
endif

if ( $?VIRTUAL_ENV_DISABLE_PROMPT ) then
    if ( $VIRTUAL_ENV_DISABLE_PROMPT == "" ) then
        set do_prompt = "1"
    else
        set do_prompt = "0"
    endif
else
    set do_prompt = "1"
endif

if ( $do_prompt == "1" ) then
    # Could be in a non-interactive environment,
    # in which case, $prompt is undefined and we wouldn't
    # care about the prompt anyway.
    if ( $?prompt ) then
        set _OLD_VIRTUAL_PROMPT="$prompt:q"
        if ( "$prompt:q" =~ *"$newline:q"* ) then
            :
        else
            set prompt = '('"$VIRTUAL_ENV_PROMPT:q"') '"$prompt:q"
        endif
    else
        unset _OLD_VIRTUAL_PROMPT
    endif
endif

unset env_name
unset do_prompt

alias pydoc python -m pydoc

rehash
