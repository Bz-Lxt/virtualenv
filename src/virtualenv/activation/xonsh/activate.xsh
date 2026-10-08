# This file must be used with "source bin/activate.xsh" *from xonsh*.
# You cannot run it directly.


_UNSET_SENTINEL = "__virtualenv_was_not_set__"


class _VirtualEnvActivator:
    """xonsh activation for virtualenv.

    Rendered into ``<venv>/bin/activate.xsh`` by the template in
    ``src/virtualenv/activation/xonsh/`` at generate-time.

    Activations nest: every ``activate()`` pushes a layer snapshot onto a
    shared stack, and every ``deactivate`` pops one layer, restoring PATH,
    PYTHONHOME, PKG_CONFIG_PATH, TCL/TK and the marker variables exactly as
    they were (unset, empty or non-empty).

    - Project: https://github.com/pypa/virtualenv
    - Template source: https://github.com/pypa/virtualenv/tree/main/src/virtualenv/activation/xonsh
    """

    # Stashed when a variable was not set before activation; deactivate
    # treats this as "unset" rather than "restore to this string".
    _UNSET_SENTINEL = _UNSET_SENTINEL

    def __init__(self):
        self.env = __xonsh__.env
        try:
            # Values substituted by virtualenv's XonshActivator at generate-time.
            # If this file was sourced before template rendering, the bare
            # identifiers below resolve to NameError.
            self.embedded_virtual_env = __VIRTUAL_ENV__
            self.embedded_virtual_prompt = __VIRTUAL_PROMPT__
            self.embedded_bin_name = __BIN_NAME__
            self.embedded_tcl_library = __TCL_LIBRARY__
            self.embedded_tk_library = __TK_LIBRARY__
        except NameError:
            print("virtualenv activate.xsh: template was not rendered")
            raise
        # Variables whose previous value this layer snapshotted on activation.
        self.backups = {}

    def _snapshot(self, name):
        """Record the current value of *name* (or the unset sentinel)."""
        self.backups[name] = self.env[name] if name in self.env else self._UNSET_SENTINEL

    def _restore(self, name):
        """Restore *name* from this layer's snapshot."""
        if name not in self.backups:
            return
        previous = self.backups.pop(name)
        if previous == self._UNSET_SENTINEL:
            self.env.pop(name, None)
        else:
            self.env[name] = previous

    def register_pydoc(self):
        if "pydoc" not in aliases:
            aliases["pydoc"] = ["python", "-m", "pydoc"]

    def unregister_pydoc(self):
        aliases.pop("pydoc", None)

    def activate(self):
        from os.path import join, basename

        # Snapshot everything the activation is about to touch.
        self._snapshot("PATH")
        self._snapshot("PYTHONHOME")
        self._snapshot("PKG_CONFIG_PATH")
        self._snapshot("VIRTUAL_ENV")
        self._snapshot("VIRTUAL_ENV_PROMPT")
        if self.embedded_tcl_library:
            self._snapshot("TCL_LIBRARY")
        if self.embedded_tk_library:
            self._snapshot("TK_LIBRARY")

        $VIRTUAL_ENV = self.embedded_virtual_env
        $VIRTUAL_ENV_PROMPT = self.embedded_virtual_prompt or basename($VIRTUAL_ENV)

        $PATH = [join($VIRTUAL_ENV, self.embedded_bin_name), *$PATH]
        self.env.pop("PYTHONHOME", None)

        pkg_config_dir = join($VIRTUAL_ENV, "lib", "pkgconfig")
        old_pkg = self.backups["PKG_CONFIG_PATH"]
        # PKG_CONFIG_PATH is a path variable in xonsh, so it is handled as a list
        # (unset: sentinel, empty: empty list, non-empty: previous elements).
        if old_pkg == self._UNSET_SENTINEL or not old_pkg:
            $PKG_CONFIG_PATH = [pkg_config_dir]
        else:
            $PKG_CONFIG_PATH = [pkg_config_dir, *old_pkg]

        if self.embedded_tcl_library:
            $TCL_LIBRARY = self.embedded_tcl_library
        if self.embedded_tk_library:
            $TK_LIBRARY = self.embedded_tk_library

        self.register_pydoc()


def _virtualenv_xonsh_deactivate(args=None):
    """Pop the top activation layer, if any (shared across nested sources)."""
    xontrib = getattr(__xonsh__, "xontrib", None)
    stack = getattr(xontrib, "virtualenv_stack", None) if xontrib is not None else None
    if not stack:
        # Nothing tracked (e.g. stale call); keep the alias harmless.
        return
    layer = stack.pop()
    for name in (
        "VIRTUAL_ENV",
        "VIRTUAL_ENV_PROMPT",
        "PKG_CONFIG_PATH",
        "TK_LIBRARY",
        "TCL_LIBRARY",
        "PYTHONHOME",
        "PATH",
    ):
        layer._restore(name)
    if not stack:
        # Outermost layer gone: remove all activation surface.
        layer.unregister_pydoc()
        aliases.pop("deactivate", None)
        try:
            delattr(xontrib, "virtualenv_stack")
        except AttributeError:
            pass
        try:
            delattr(xontrib, "virtualenv")
        except AttributeError:
            pass


if not hasattr(__xonsh__, "xontrib"):
    __xonsh__.xontrib = __xonsh__.imp.types.SimpleNamespace()

# A single shared deactivate alias pops the stack, so repeated activations
# and repeated deactivations nest and unnest correctly.
aliases["deactivate"] = _virtualenv_xonsh_deactivate

if not hasattr(__xonsh__.xontrib, "virtualenv_stack"):
    __xonsh__.xontrib.virtualenv_stack = []

_layer = _VirtualEnvActivator()
__xonsh__.xontrib.virtualenv_stack.append(_layer)
__xonsh__.xontrib.virtualenv = _layer
_layer.activate()
