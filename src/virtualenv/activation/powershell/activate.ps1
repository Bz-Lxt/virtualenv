<#
.Synopsis
Activate a Python virtual environment for the current PowerShell session.

.Description
Pushes the python executable for a virtual environment to the front of the
$Env:PATH environment variable and sets the prompt to signify that you are
in a Python virtual environment. Makes use of the command line switches as
well as the `pyvenv.cfg` file values present in the virtual environment.

Virtual environments can be activated several times in the same session
(nested activation). Each activation pushes a layer on a stack, and
``deactivate`` only restores the most recent layer, so activating
environment B on top of A and then running ``deactivate`` returns the
session to A. PATH, the prompt and the managed environment variables are
restored losslessly, distinguishing variables that were unset, empty or
non-empty before the activation.

.Parameter VenvDir
Path to the directory that contains the virtual environment to activate. The
default value for this is the parent of the directory that the activate.ps1
script is located within.

.Parameter Prompt
The prompt prefix to display when this virtual environment is activated. By
default, this prompt is the name of the virtual environment folder (VenvDir)
surrounded by parentheses and followed by a single space (ie. '(.venv) ').

.Example
activate.ps1
Activates the Python virtual environment that contains the activate.ps1 script.

.Example
activate.ps1 -Verbose
Activates the Python virtual environment that contains the activate.ps1 script,
and shows extra information about the activation as it executes.

.Example
activate.ps1 -VenvDir C:\Users\MyUser\Common\.venv
Activates the Python virtual environment located in the specified location.

.Example
activate.ps1 -Prompt "MyPython"
Activates the Python virtual environment that contains the activate.ps1 script,
and prefixes the current prompt with the specified string (surrounded in
parentheses) while the virtual environment is active.

.Notes
On Windows, it may be required to enable this activate.ps1 script by setting the
execution policy for the user. You can do this by issuing the following PowerShell
command:

PS C:\> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

For more information on Execution Policies:
https://go.microsoft.com/fwlink/?LinkID=135170

#>
Param(
    [Parameter(Mandatory = $false)]
    [String]
    $VenvDir,
    [Parameter(Mandatory = $false)]
    [String]
    $Prompt
)

function Get-PyVenvConfig(
    [String]
    $ConfigDir
) {
    Write-Verbose "Given ConfigDir=$ConfigDir, obtain values in pyvenv.cfg"

    $pyvenvConfigPath = Join-Path -Resolve -Path $ConfigDir -ChildPath 'pyvenv.cfg' -ErrorAction Continue

    $pyvenvConfig = @{ }

    if ($pyvenvConfigPath) {
        Write-Verbose "File exists, parse ``key = value`` lines"
        $pyvenvConfigContent = Get-Content -Path $pyvenvConfigPath

        $pyvenvConfigContent | ForEach-Object {
            $keyval = $PSItem -split "\s*=\s*", 2
            if ($keyval[0] -and $keyval[1]) {
                $val = $keyval[1]

                if ("'""".Contains($val.Substring(0, 1))) {
                    $val = $val.Substring(1, $val.Length - 2)
                }

                $pyvenvConfig[$keyval[0]] = $val
                Write-Verbose "Adding Key: '$($keyval[0])'='$val'"
            }
        }
    }
    return $pyvenvConfig
}

# Stack of parked activation layers (newest last). Each entry is a hashtable
# holding the exact state (including whether a variable was present) that the
# outer layer must be restored to when the inner layer is deactivated.
if (-not (Test-Path variable:global:_VIRTUAL_STACK)) {
    New-Variable -Scope global -Name _VIRTUAL_STACK -Value (New-Object System.Collections.ArrayList)
}

# Set a process environment variable, preserving the three possible states:
# $null removes the variable, an empty string keeps it present but empty
# (assigning '' through the env: drive would delete it).
function global:__virtualenv_set_env([String] $Name, $Value) {
    if ($null -eq $Value) {
        Remove-Item ("env:" + $Name) -ErrorAction SilentlyContinue
    } else {
        [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    }
}

# Snapshot an environment variable into the backup slot. A companion "<slot>_PRES"
# variable records whether the environment variable existed, so that an unset
# variable is not confused with one that was set to an empty string.
function global:__virtualenv_save_env([String] $Slot, [String] $Name) {
    if (Test-Path ("env:" + $Name)) {
        New-Variable -Scope global -Name $Slot -Value ([Environment]::GetEnvironmentVariable($Name, "Process"))
        New-Variable -Scope global -Name ($Slot + "_PRES") -Value 1
    }
}

# Restore one environment variable from its backup slot. When the slot is
# missing and a virtual environment layer is genuinely active, the variable
# did not exist before the activation and is removed.
function global:__virtualenv_restore_env([String] $Slot, [String] $Name, [Boolean] $Active) {
    if (Test-Path ("variable:" + $Slot)) {
        __virtualenv_set_env $Name (Get-Variable -Name $Slot -Scope global -ValueOnly)
        Remove-Variable -Name $Slot -Scope global -ErrorAction SilentlyContinue
        Remove-Variable -Name ($Slot + "_PRES") -Scope global -ErrorAction SilentlyContinue
    } elseif ($Active) {
        __virtualenv_set_env $Name $null
    }
}

# Reload a backup slot from a popped stack layer.
function global:__virtualenv_reload_env([String] $Slot, $Layer, [String] $Key, [String] $Name) {
    if ($Layer[$Key + "_PRES"]) {
        New-Variable -Scope global -Name $Slot -Value $Layer[$Key]
        New-Variable -Scope global -Name ($Slot + "_PRES") -Value 1
    } elseif ($Layer["ACTIVE"] -and -not (Test-Path ("env:" + $Name))) {
        # The variable was already unset by the outer activation; make sure no
        # stale backup slot survives.
        Remove-Variable -Name $Slot -Scope global -ErrorAction SilentlyContinue
        Remove-Variable -Name ($Slot + "_PRES") -Scope global -ErrorAction SilentlyContinue
    }
}

# Park the currently active layer before another environment is activated on
# top of it: stash the backup slots (plus the live VIRTUAL_ENV values and the
# prompt chain) so the outer layer can be rebuilt when the inner one leaves.
function global:__virtualenv_park_layer {
    $layer = @{ ACTIVE = $true }
    # The backup slots hold the state from before the outer layer activated;
    # parking those (rather than the live environment) is what lets the outer
    # layer eventually restore the session to its original state.
    foreach ($pair in @(
        @("_OLD_VIRTUAL_PATH", "PATH"),
        @("_OLD_VIRTUAL_PYTHONHOME", "PYTHONHOME"),
        @("_OLD_PKG_CONFIG_PATH", "PKG"),
        @("_OLD_VIRTUAL_TCL_LIBRARY", "TCL"),
        @("_OLD_VIRTUAL_TK_LIBRARY", "TK")
    )) {
        $slot = $pair[0]
        $key = $pair[1]
        if (Test-Path ("variable:" + $slot)) {
            $layer[$key] = Get-Variable -Name $slot -Scope global -ValueOnly
            $layer[$key + "_PRES"] = $true
        } else {
            $layer[$key + "_PRES"] = $false
        }
    }
    $layer["TCLM"] = Test-Path variable:global:__virtualenv_tcl_managed
    $layer["TKM"] = Test-Path variable:global:__virtualenv_tk_managed

    foreach ($pair in @(
        @("VENV", "VIRTUAL_ENV"),
        @("VENVP", "VIRTUAL_ENV_PROMPT")
    )) {
        $key = $pair[0]
        $name = $pair[1]
        if (Test-Path ("env:" + $name)) {
            $layer[$key] = [Environment]::GetEnvironmentVariable($name, "Process")
            $layer[$key + "_PRES"] = $true
        } else {
            $layer[$key + "_PRES"] = $false
        }
    }

    if (Test-Path function:_old_virtual_prompt) {
        $layer["PROMPT_BODY"] = $function:_old_virtual_prompt
        $layer["PROMPT_USED"] = $true
    } else {
        $layer["PROMPT_USED"] = $false
    }
    if (Test-Path variable:global:_PYTHON_VENV_PROMPT_PREFIX) {
        $layer["PROMPT_PREFIX"] = $global:_PYTHON_VENV_PROMPT_PREFIX
    }

    [void]$global:_VIRTUAL_STACK.Add($layer)

    Remove-Variable -Name "_OLD_VIRTUAL_PATH" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_VIRTUAL_PATH_PRES" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_VIRTUAL_PYTHONHOME" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_VIRTUAL_PYTHONHOME_PRES" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_PKG_CONFIG_PATH" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_PKG_CONFIG_PATH_PRES" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_VIRTUAL_TCL_LIBRARY" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_VIRTUAL_TCL_LIBRARY_PRES" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_VIRTUAL_TK_LIBRARY" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "_OLD_VIRTUAL_TK_LIBRARY_PRES" -Scope global -ErrorAction SilentlyContinue
    Remove-Variable -Name "__virtualenv_tcl_managed" -Scope global -Force -ErrorAction SilentlyContinue
    Remove-Variable -Name "__virtualenv_tk_managed" -Scope global -Force -ErrorAction SilentlyContinue
    Remove-Variable -Name "_PYTHON_VENV_PROMPT_PREFIX" -Scope global -Force -ErrorAction SilentlyContinue
    Remove-Item function:\_old_virtual_prompt -ErrorAction SilentlyContinue
}

# The canonical virtual environment prompt. It is recreated for every live
# layer and resolves "_old_virtual_prompt" dynamically, so nested layers chain
# without one layer's prompt body calling back into itself by name.
function global:__virtualenv_venv_prompt {
    Write-Host -NoNewline -ForegroundColor Green "($($_PYTHON_VENV_PROMPT_PREFIX)) "
    _old_virtual_prompt
}

# Install the prompt machinery for the layer being activated. When an outer
# layer is parked on the stack, its prompt is made self-contained (its prefix
# and predecessor body are held in numbered global variables) so the captured
# script block cannot recurse into the new layer's "_old_virtual_prompt".
function global:__virtualenv_install_prompt([String] $Prefix) {
    function global:_old_virtual_prompt { "" }
    if ($global:_VIRTUAL_STACK.Count -gt 0) {
        $outer = $global:_VIRTUAL_STACK[$global:_VIRTUAL_STACK.Count - 1]
        if ($outer["PROMPT_USED"]) {
            $level = $global:_VIRTUAL_STACK.Count
            $bodyVar = "__virtualenv_prompt_body_$level"
            $prefixVar = "__virtualenv_prompt_prefix_$level"
            Set-Variable -Scope global -Name $bodyVar -Value $outer["PROMPT_BODY"]
            Set-Variable -Scope global -Name $prefixVar -Value $outer["PROMPT_PREFIX"]
            $synthetic = [scriptblock]::Create(
                'Write-Host -NoNewline -ForegroundColor Green ([string]::Concat("(", (Get-Variable -Scope global -Name ''' + $prefixVar + ''' -ValueOnly), ") ")); ' +
                '& (Get-Variable -Scope global -Name ''' + $bodyVar + ''' -ValueOnly)'
            )
            $function:_old_virtual_prompt = $synthetic
        } else {
            $function:_old_virtual_prompt = $function:prompt
        }
    } else {
        $function:_old_virtual_prompt = $function:prompt
    }

    New-Variable -Name _PYTHON_VENV_PROMPT_PREFIX -Description "Python virtual environment prompt prefix" -Scope Global -Option ReadOnly -Visibility Public -Value $Prefix
    function global:prompt {
        __virtualenv_venv_prompt
    }
}

# Bring back the layer underneath after the current one has been restored.
function global:__virtualenv_pop_layer {
    if ($global:_VIRTUAL_STACK.Count -eq 0) {
        return $null
    }
    $level = $global:_VIRTUAL_STACK.Count
    $index = $level - 1
    $layer = $global:_VIRTUAL_STACK[$index]
    $global:_VIRTUAL_STACK.RemoveAt($index)

    __virtualenv_reload_env "_OLD_VIRTUAL_PATH" $layer "PATH"
    __virtualenv_reload_env "_OLD_VIRTUAL_PYTHONHOME" $layer "PYTHONHOME"
    __virtualenv_reload_env "_OLD_PKG_CONFIG_PATH" $layer "PKG"
    __virtualenv_reload_env "_OLD_VIRTUAL_TCL_LIBRARY" $layer "TCL"
    __virtualenv_reload_env "_OLD_VIRTUAL_TK_LIBRARY" $layer "TK"
    if ($layer["TCLM"]) { New-Variable -Scope global -Name "__virtualenv_tcl_managed" -Value 1 }
    if ($layer["TKM"]) { New-Variable -Scope global -Name "__virtualenv_tk_managed" -Value 1 }

    if ($layer["VENV_PRES"]) {
        __virtualenv_set_env "VIRTUAL_ENV" $layer["VENV"]
    } else {
        __virtualenv_set_env "VIRTUAL_ENV" $null
    }
    if ($layer["VENVP_PRES"]) {
        __virtualenv_set_env "VIRTUAL_ENV_PROMPT" $layer["VENVP"]
    } else {
        __virtualenv_set_env "VIRTUAL_ENV_PROMPT" $null
    }

    if ($layer["PROMPT_USED"]) {
        function global:_old_virtual_prompt { "" }
        $function:_old_virtual_prompt = $layer["PROMPT_BODY"]
        New-Variable -Name _PYTHON_VENV_PROMPT_PREFIX -Description "Python virtual environment prompt prefix" -Scope Global -Option ReadOnly -Visibility Public -Value $layer["PROMPT_PREFIX"]
        function global:prompt {
            __virtualenv_venv_prompt
        }
    }
    Remove-Variable -Name "__virtualenv_prompt_body_$level" -Scope global -Force -ErrorAction SilentlyContinue
    Remove-Variable -Name "__virtualenv_prompt_prefix_$level" -Scope global -Force -ErrorAction SilentlyContinue

    return $layer
}

function global:deactivate([switch] $NonDestructive) {
    # Remember whether a layer was really active before touching anything. A
    # bare "deactivate -NonDestructive" on an untouched session must never wipe
    # the user's own PATH.
    $active = Test-Path env:VIRTUAL_ENV

    if (Test-Path variable:_OLD_VIRTUAL_PATH) {
        $env:PATH = $variable:_OLD_VIRTUAL_PATH
        Remove-Variable "_OLD_VIRTUAL_PATH" -Scope global
    }

    __virtualenv_restore_env "_OLD_VIRTUAL_PYTHONHOME" "PYTHONHOME" $active

    if (Test-Path variable:_OLD_VIRTUAL_TCL_LIBRARY) {
        __virtualenv_set_env "TCL_LIBRARY" $variable:_OLD_VIRTUAL_TCL_LIBRARY
        Remove-Variable "_OLD_VIRTUAL_TCL_LIBRARY" -Scope global
    } elseif ($active -and (Test-Path variable:global:__virtualenv_tcl_managed)) {
        __virtualenv_set_env "TCL_LIBRARY" $null
    }
    Remove-Variable -Name "__virtualenv_tcl_managed" -Scope global -Force -ErrorAction SilentlyContinue

    if (Test-Path variable:_OLD_VIRTUAL_TK_LIBRARY) {
        __virtualenv_set_env "TK_LIBRARY" $variable:_OLD_VIRTUAL_TK_LIBRARY
        Remove-Variable "_OLD_VIRTUAL_TK_LIBRARY" -Scope global
    } elseif ($active -and (Test-Path variable:global:__virtualenv_tk_managed)) {
        __virtualenv_set_env "TK_LIBRARY" $null
    }
    Remove-Variable -Name "__virtualenv_tk_managed" -Scope global -Force -ErrorAction SilentlyContinue

    __virtualenv_restore_env "_OLD_PKG_CONFIG_PATH" "PKG_CONFIG_PATH" $active

    if (Test-Path function:_old_virtual_prompt) {
        $function:prompt = $function:_old_virtual_prompt
        Remove-Item function:\_old_virtual_prompt
    }

    if (Get-Variable -Name "_PYTHON_VENV_PROMPT_PREFIX" -ErrorAction SilentlyContinue) {
        Remove-Variable -Name _PYTHON_VENV_PROMPT_PREFIX -Scope Global -Force
    }

    if ($active) {
        Remove-Item env:VIRTUAL_ENV -ErrorAction SilentlyContinue
        Remove-Item env:VIRTUAL_ENV_PROMPT -ErrorAction SilentlyContinue
    }

    # Pop the outer layer back into the live slots. Only when the stack is
    # empty and the call is destructive does this deactivate the machinery.
    $popped = __virtualenv_pop_layer

    if (($null -eq $popped) -and !$NonDestructive) {
        Remove-Variable -Name _VIRTUAL_STACK -Scope global -Force -ErrorAction SilentlyContinue
        Remove-Item function:deactivate
        Remove-Item function:pydoc
        Remove-Item function:__virtualenv_set_env
        Remove-Item function:__virtualenv_save_env
        Remove-Item function:__virtualenv_restore_env
        Remove-Item function:__virtualenv_reload_env
        Remove-Item function:__virtualenv_park_layer
        Remove-Item function:__virtualenv_pop_layer
        Remove-Item function:__virtualenv_install_prompt
        Remove-Item function:__virtualenv_venv_prompt
    }
}

function global:pydoc {
    & python -m pydoc $args
}

$VenvExecPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvExecDir = Get-Item -Path $VenvExecPath

Write-Verbose "Activation script is located in path: '$VenvExecPath'"

if ($VenvDir) {
    Write-Verbose "VenvDir given as parameter, using '$VenvDir' to determine values"
} else {
    $VenvDir = $VenvExecDir.Parent.FullName.TrimEnd("\\/")
    Write-Verbose "VenvDir=$VenvDir"
}

$pyvenvCfg = Get-PyVenvConfig -ConfigDir $VenvDir

if ($Prompt) {
    Write-Verbose "Prompt specified as argument, using '$Prompt'"
} else {
    if ($pyvenvCfg -and $pyvenvCfg['prompt']) {
        Write-Verbose "Setting based on value in pyvenv.cfg='$($pyvenvCfg['prompt'])'"
        $Prompt = $pyvenvCfg['prompt']
    } elseif (__VIRTUAL_PROMPT__ -ne "") {
        $Prompt = __VIRTUAL_PROMPT__
    } else {
        $Prompt = Split-Path -Path $VenvDir -Leaf
    }
}

# Nested activation: park the layer that is currently live instead of
# destroying it; otherwise just make sure there is no stale state.
if (Test-Path env:VIRTUAL_ENV) {
    __virtualenv_park_layer
} else {
    deactivate -NonDestructive
}

__virtualenv_set_env "VIRTUAL_ENV" $VenvDir
__virtualenv_set_env "VIRTUAL_ENV_PROMPT" $Prompt

__virtualenv_save_env "_OLD_VIRTUAL_PYTHONHOME" "PYTHONHOME"
__virtualenv_set_env "PYTHONHOME" $null

# a $null saved value tells deactivate to remove the variable
if (__TCL_LIBRARY__ -ne "") {
    New-Variable -Scope global -Name "__virtualenv_tcl_managed" -Value 1 -Force
    __virtualenv_save_env "_OLD_VIRTUAL_TCL_LIBRARY" "TCL_LIBRARY"
    $env:TCL_LIBRARY = __TCL_LIBRARY__
}

if (__TK_LIBRARY__ -ne "") {
    New-Variable -Scope global -Name "__virtualenv_tk_managed" -Value 1 -Force
    __virtualenv_save_env "_OLD_VIRTUAL_TK_LIBRARY" "TK_LIBRARY"
    $env:TK_LIBRARY = __TK_LIBRARY__
}

New-Variable -Scope global -Name _OLD_VIRTUAL_PATH -Value $env:PATH

__virtualenv_save_env "_OLD_PKG_CONFIG_PATH" "PKG_CONFIG_PATH"
$pkgConfigPath = [IO.Path]::Combine($VenvDir, "lib", "pkgconfig")
if ((Test-Path env:PKG_CONFIG_PATH) -and $env:PKG_CONFIG_PATH) {
    $env:PKG_CONFIG_PATH = $pkgConfigPath + __PATH_SEP__ + $env:PKG_CONFIG_PATH
} else {
    __virtualenv_set_env "PKG_CONFIG_PATH" $pkgConfigPath
}

$env:PATH = "$VenvDir/" + __BIN_NAME__ + __PATH_SEP__ + $env:PATH

if (!$env:VIRTUAL_ENV_DISABLE_PROMPT) {
    __virtualenv_install_prompt $Prompt
}
