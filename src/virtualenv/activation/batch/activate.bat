@REM This file is UTF-8 encoded, so we need to update the current code page while executing it
@for /f "tokens=2 delims=:." %%a in ('"%SystemRoot%\System32\chcp.com"') do @set _OLD_CODEPAGE=%%a

@if defined _OLD_CODEPAGE (
    "%SystemRoot%\System32\chcp.com" 65001 > nul
)

@REM Nested activations are tracked with a depth counter; every layer stores its
@REM own backup slots suffixed with the current depth, so deactivate only rolls
@REM back the most recent layer. cmd.exe cannot represent a variable that is
@REM present but empty ("set X=" deletes it), therefore unset and empty values
@REM are both restored as unset under cmd.
@if not defined _VENV_DEPTH @set "_VENV_DEPTH=0"
@set /a "_VENV_DEPTH=_VENV_DEPTH+1" > nul
@set "_VENV_LVL=%_VENV_DEPTH%"

@REM Remember the identity of the outer (already active) environment, if any.
@if defined VIRTUAL_ENV @set "_VIRTUAL_ENV_%_VENV_LVL%=%VIRTUAL_ENV%"
@if defined VIRTUAL_ENV_PROMPT @set "_VIRTUAL_ENV_PROMPT_%_VENV_LVL%=%VIRTUAL_ENV_PROMPT%"

@set "VIRTUAL_ENV=__VIRTUAL_ENV__"

@set "VIRTUAL_ENV_PROMPT=__VIRTUAL_PROMPT__"
@if NOT DEFINED VIRTUAL_ENV_PROMPT (
    @for %%d in ("%VIRTUAL_ENV%") do @set "VIRTUAL_ENV_PROMPT=%%~nxd"
)

@if defined PROMPT @set "_OLD_VIRTUAL_PROMPT_%_VENV_LVL%=%PROMPT%"
@if not defined VIRTUAL_ENV_DISABLE_PROMPT @set "PROMPT=(%VIRTUAL_ENV_PROMPT%) %PROMPT%"

@REM Don't use () to avoid problems with them in %PATH%
@if defined PYTHONHOME @set "_OLD_VIRTUAL_PYTHONHOME_%_VENV_LVL%=%PYTHONHOME%"
@set PYTHONHOME=

@if defined TCL_LIBRARY @set "_OLD_VIRTUAL_TCL_LIBRARY_%_VENV_LVL%=%TCL_LIBRARY%"
@if NOT "__TCL_LIBRARY__"=="" @set "TCL_LIBRARY=__TCL_LIBRARY__"
@if NOT "__TCL_LIBRARY__"=="" @set "_VENV_TCLM_%_VENV_LVL%=1"

@if defined TK_LIBRARY @set "_OLD_VIRTUAL_TK_LIBRARY_%_VENV_LVL%=%TK_LIBRARY%"
@if NOT "__TK_LIBRARY__"=="" @set "TK_LIBRARY=__TK_LIBRARY__"
@if NOT "__TK_LIBRARY__"=="" @set "_VENV_TKM_%_VENV_LVL%=1"

@if defined PKG_CONFIG_PATH @set "_OLD_PKG_CONFIG_PATH_%_VENV_LVL%=%PKG_CONFIG_PATH%"
@if not defined PKG_CONFIG_PATH @goto :__VENV_PKG_EMPTY
@set "PKG_CONFIG_PATH=%VIRTUAL_ENV%\lib\pkgconfig;%PKG_CONFIG_PATH%"
@goto :__VENV_PKG_DONE
:__VENV_PKG_EMPTY
@set "PKG_CONFIG_PATH=%VIRTUAL_ENV%\lib\pkgconfig"
:__VENV_PKG_DONE

@set "_OLD_VIRTUAL_PATH_%_VENV_LVL%=%PATH%"
@set "PATH=%VIRTUAL_ENV%\__BIN_NAME__;%PATH%"

@set _VENV_LVL=

@if defined _OLD_CODEPAGE (
    "%SystemRoot%\System32\chcp.com" %_OLD_CODEPAGE% > nul
    @set _OLD_CODEPAGE=
)
