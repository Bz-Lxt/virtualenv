# virtualenv activation module:
# - Activate with `overlay use activate.nu`
# - Deactivate with `deactivate`, as usual
#
# Environments can be activated several times in the same session: each
# activation pushes a layer on an internal stack and `deactivate` only pops
# the most recent layer. PATH, the prompt and the managed environment
# variables are restored losslessly, including the distinction between
# variables that were unset, empty or non-empty before activation.
#
# To customize the overlay name, call `overlay use activate.nu as foo`, but then `deactivate` won't work —
# you'd need to run `overlay hide foo` manually. Do not activate with `use activate.nu *`; that does not
# create an overlay and deactivation will fail.

module warning {
    export-env {
        const file = path self
        error make -u {
            msg: $"`($file | path basename)` is meant to be used with `overlay use`, not `source`"
        }
    }

}

use warning

export-env {

    let nu_ver = (version | get version | split row '.' | take 2 | each { into int })
        if $nu_ver.0 == 0 and $nu_ver.1 < 106 {
            error make {
                msg: 'virtualenv Nushell activation requires Nushell 0.106 or greater.'
            }
    }

    def is-string [x] {
        ($x | describe) == 'string'
    }

    def has-env [...names] {
        $names | each {|n| ($n in $env) and (($env | get --optional $n) != null) } | all {|i| $i }
    }

    def is-env-true [name: string] {
        if (has-env $name) {
            let val = ($env | get --optional $name)
            if ($val | describe) == 'bool' {
                $val
            } else {
                not ($val | is-empty)
            }
        } else {
            false
        }
    }

    let virtual_env = __VIRTUAL_ENV__
    let bin = __BIN_NAME__
    let path_name = if (has-env 'Path') { 'Path' } else { 'PATH' }
    let venv_path = ([$virtual_env $bin] | path join)
    let new_path = ($env | get $path_name | prepend $venv_path)
    let virtual_env_prompt = if (__VIRTUAL_PROMPT__ | is-empty) {
        ($virtual_env | path basename)
    } else {
        __VIRTUAL_PROMPT__
    }
    let old_pkg_config_path = if (has-env 'PKG_CONFIG_PATH') { $env.PKG_CONFIG_PATH } else { '' }
    let venv_pkg_config_path = ([$virtual_env lib pkgconfig] | path join)
    let new_pkg_config_path = if ($old_pkg_config_path | is-empty) {
        $venv_pkg_config_path
    } else {
        $'($venv_pkg_config_path)(char esep)($old_pkg_config_path)'
    }

    # Snapshot the current environment before touching it. Nushell re-using the
    # same overlay name does not keep the intermediate states, so the stack is
    # maintained explicitly; the final deactivate hides the overlay itself.
    let old_prompt_command = ($env | get --optional PROMPT_COMMAND)
    let old_virtual_prefix = ($env | get --optional VIRTUAL_PREFIX)
    let snapshot = {
        path_name: $path_name,
        path: ($env | get $path_name),
        pythonhome_present: (has-env 'PYTHONHOME'),
        pythonhome: ($env | get --optional PYTHONHOME),
        pkg_config_path_present: (has-env 'PKG_CONFIG_PATH'),
        pkg_config_path: $old_pkg_config_path,
        tcl_library_present: (has-env 'TCL_LIBRARY'),
        tcl_library: ($env | get --optional TCL_LIBRARY),
        tk_library_present: (has-env 'TK_LIBRARY'),
        tk_library: ($env | get --optional TK_LIBRARY),
        virtual_env_present: (has-env 'VIRTUAL_ENV'),
        virtual_env: ($env | get --optional VIRTUAL_ENV),
        virtual_env_prompt_present: (has-env 'VIRTUAL_ENV_PROMPT'),
        virtual_env_prompt: ($env | get --optional VIRTUAL_ENV_PROMPT),
        prompt_command_present: (has-env 'PROMPT_COMMAND'),
        prompt_command: $old_prompt_command,
        virtual_prefix_present: (has-env 'VIRTUAL_PREFIX'),
        virtual_prefix: $old_virtual_prefix,
    }
    let virtualenv_stack = ($env | get --optional _VIRTUAL_ENV_STACK | default [])
    $env._VIRTUAL_ENV_STACK = ($virtualenv_stack | append $snapshot)

    let new_env = { $path_name: $new_path VIRTUAL_ENV: $virtual_env VIRTUAL_ENV_PROMPT: $virtual_env_prompt PKG_CONFIG_PATH: $new_pkg_config_path }
    if (has-env 'PYTHONHOME') {
        hide-env PYTHONHOME
    }
    if (has-env 'TCL_LIBRARY')  {
        let $new_env = $new_env | insert TCL_LIBRARY __TCL_LIBRARY__
    }
    if (has-env 'TK_LIBRARY')  {
        let $new_env = $new_env | insert TK_LIBRARY __TK_LIBRARY__
    }
    let new_env = if (is-env-true 'VIRTUAL_ENV_DISABLE_PROMPT') {
        $new_env
    } else {
        let virtual_prefix = $'(char lparen)($virtual_env_prompt)(char rparen) '
        let new_prompt = if (has-env 'PROMPT_COMMAND') {
            if ('closure' in ($old_prompt_command | describe)) {
                {|| $'($virtual_prefix)(do $old_prompt_command)' }
            } else {
                {|| $'($virtual_prefix)($old_prompt_command)' }
            }
        } else {
            {|| $'($virtual_prefix)' }
        }
        $new_env | merge { PROMPT_COMMAND: $new_prompt VIRTUAL_PREFIX: $virtual_prefix }
    }
    load-env $new_env
}

# Pop one activation layer, restoring the snapshot captured for it. Nushell
# parser keywords (such as `overlay hide`) cannot run from inside a command
# definition, so the overlay itself and its commands stay loaded once created;
# after the last layer is popped the environment is fully restored to its
# pre-activation state and these commands simply become inert (the overlay can
# still be removed manually with `overlay hide activate`).
export def --env deactivate [--non-destructive] {
    let virtualenv_stack = ($env | get --optional _VIRTUAL_ENV_STACK | default [])
    if ($virtualenv_stack | is-empty) {
        return
    }

    let depth = ($virtualenv_stack | length)
    let layer = ($virtualenv_stack | last)
    let remaining = ($virtualenv_stack | first ($depth - 1))

    if $layer.path_name == "PATH" {
        $env.PATH = $layer.path
    } else {
        $env.Path = $layer.path
    }

    if $layer.pythonhome_present { $env.PYTHONHOME = $layer.pythonhome } else { $env.PYTHONHOME = null }
    if $layer.pkg_config_path_present { $env.PKG_CONFIG_PATH = $layer.pkg_config_path } else { $env.PKG_CONFIG_PATH = null }
    if $layer.tcl_library_present { $env.TCL_LIBRARY = $layer.tcl_library } else { $env.TCL_LIBRARY = null }
    if $layer.tk_library_present { $env.TK_LIBRARY = $layer.tk_library } else { $env.TK_LIBRARY = null }
    if $layer.virtual_env_present { $env.VIRTUAL_ENV = $layer.virtual_env } else { $env.VIRTUAL_ENV = null }
    if $layer.virtual_env_prompt_present { $env.VIRTUAL_ENV_PROMPT = $layer.virtual_env_prompt } else { $env.VIRTUAL_ENV_PROMPT = null }
    if $layer.prompt_command_present { $env.PROMPT_COMMAND = $layer.prompt_command } else { $env.PROMPT_COMMAND = null }
    if $layer.virtual_prefix_present { $env.VIRTUAL_PREFIX = $layer.virtual_prefix } else { $env.VIRTUAL_PREFIX = null }

    if ($remaining | is-empty) {
        $env._VIRTUAL_ENV_STACK = null
    } else {
        $env._VIRTUAL_ENV_STACK = $remaining
    }
}

export alias pydoc = python -m pydoc
# The activate overlay can be unloaded completely (removing deactivate/pydoc) with `overlay hide activate`;
# for custom names use `overlay hide NAME`
