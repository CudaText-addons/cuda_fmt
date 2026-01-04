import os
import re
import json
import importlib
from typing import List, Dict, Optional, Callable, Tuple, Any
import cudatext as app
from cudatext import ed
from .fmtconfig import *
from .fmtrun import *

from cudax_lib import get_translation, get_opt
_   = get_translation(__file__)  # i18n

FN_CFG = os.path.join(app.app_path(app.APP_DIR_SETTINGS), 'cuda_fmt.json')
MAX_FORMATTERS_PER_PLUGIN = 100
README_PATH = os.path.join('readme', 'readme.txt')

def _call_method_by_name(module: Any, method_name: str) -> None:
    """Call a method from module by name with automatic Command fallback.

    Strategy (KISS principle):
    1. Try module-level function first: module.method_name()
    2. If not found, try Command class: module.Command().method_name()

    This ensures backward compatibility with simple functions while
    supporting class-based plugins without requiring wrapper functions.

    Args:
        module: Imported module object
        method_name: Method name (e.g., 'help', 'config')

    Raises:
        AttributeError: If method not found in module or Command class

    Examples:
        # Plugin with simple function
        _call_method_by_name(my_module, 'help')  # calls my_module.help()

        # Plugin with Command class
        _call_method_by_name(my_module, 'help')  # calls my_module.Command().help()
    """
    # Try 1: Simple function at module level
    if hasattr(module, method_name):
        func = getattr(module, method_name)
        # Make sure it's callable (not a variable)
        if callable(func):
            func()
            return

    # Try 2: Method in Command class (common pattern in CudaText plugins)
    if hasattr(module, 'Command'):
        cmd_class = getattr(module, 'Command')
        # Instantiate Command class
        if isinstance(cmd_class, type):
            cmd_instance = cmd_class()
            if hasattr(cmd_instance, method_name):
                method = getattr(cmd_instance, method_name)
                if callable(method):
                    method()
                    return

    # If we get here, method was not found anywhere
    raise AttributeError(
        f'Method "{method_name}" not found as module function or Command.{method_name}'
    )

def _import_module_cached(module_path: str) -> Any:
    """Import module using cache if available.

    Args:
        module_path: Module path to import (e.g., 'cuda_fmt_prettier')

    Returns:
        Imported module object

    Raises:
        ImportError: If module cannot be imported
    """
    if module_path in importlib.sys.modules:
        return importlib.sys.modules[module_path]
    return importlib.import_module(module_path)

class Helpers:
    """Manages formatter plugin loading and selection.

    Formatters are loaded from install.inf files with sections:

    Legacy mode (file-based config):
        [fmtX]
        config=myconfig.ini

    New mode (method-based config/help):
        [info]  # Global defaults
        config_global=gen_global_config
        config_local=gen_local_config
        help=show_help

        [fmtX]  # Override per formatter
        config_global=custom_global
        help=custom_help

    Priority: [fmtX] > [info] > legacy config=
    """
    helpers = []

    @staticmethod
    def get_editor_lexer() -> Optional[str]:
        """Get lexer at current caret position.

        Returns:
            Lexer name or None if unavailable/multi-caret/overlapping
        """
        carets = ed.get_carets()
        if len(carets) == 0:
            app.msg_status(_('Cannot handle none-carets'))
            return

        if len(carets) > 1:
            app.msg_status(_('Cannot handle multi-carets yet'))
            return

        lexer0 = ed.get_prop(app.PROP_LEXER_FILE)
        if not lexer0:
            error_max_size = False
            fn = ed.get_filename()
            if fn:
                try:
                    size = os.path.getsize(fn)
                    error_max_size = (size > get_opt('ui_max_size_lexer', 2) * 1024 * 1024)
                except (FileNotFoundError, OSError):
                    # File deleted or inaccessible after get_filename()
                    error_max_size = False
            if error_max_size:
                app.msg_status(_(
                    'Cannot handle None-lexer; '
                    'maybe file is big and "ui_max_size_lexer" blocks the lexer?'
                ))
            else:
                app.msg_status(_('Cannot handle None-lexer'))
            return

        x1, y1, x2, y2 = carets[0]
        if y2 < 0:
            return lexer0

        if (y1, x1) > (y2, x2):
            x1, y1, x2, y2 = x2, y2, x1, y1

        # decrease ending pos, it's often after the sub-lexer ending
        if x2 > 0:
            x2 -= 1
        elif y2 > 0:
            y2 -= 1
            x2 = len(ed.get_text_line(y2))

        lexer1 = ed.get_prop(PROP_LEXER_POS, (x1, y1))
        lexer2 = ed.get_prop(PROP_LEXER_POS, (x2, y2))
        if lexer1 != lexer2:
            app.msg_status(_(
                'Selection overlaps sub-lexer block: "{}"/"{}"\''
            ).format(lexer1, lexer2))
            return

        return lexer1

    def lexers(self) -> List[str]:
        """Get sorted list of all supported lexers.

        Returns:
            Sorted list of unique lexer names
        """
        lexer_strings = [helper.get('lexers', '') for helper in self.helpers]
        all_lexers = ','.join(lexer_strings)
        lexer_list = [lex for lex in all_lexers.split(',') if lex]
        return sorted(set(lexer_list))

    def helpers_for_lexer(self, lexer: str) -> Optional[List[Dict[str, Any]]]:
        """Find all formatters supporting given lexer.

        Args:
            lexer: Lexer name to search for

        Returns:
            List of helper dicts, or None if lexer is empty/invalid.
            Returns empty list [] if lexer is valid but no formatters found.
        """
        if lexer in ('', '-'):
            return None

        res = []
        for helper in self.helpers:
            lexers_str = helper.get('lexers', '')
            for item in lexers_str.split(','):
                if item.startswith('regex:'):
                    ok = re.match(item[6:], lexer)
                else:
                    ok = item == lexer
                if ok:
                    res.append(helper)
                    break
        return res

    def load_dir(self, plugin_dir: str) -> None:
        """Load formatter plugins from directory.

        Supports both legacy config files and new method-based config/help.
        Priority: [fmtX] section > [info] section (for global defaults).

        Args:
            plugin_dir: Path to plugins directory
        """
        dirs = os.listdir(plugin_dir)
        dirs = [os.path.join(plugin_dir, s) for s in dirs if s.startswith('cuda_fmt_')]
        dirs = sorted(dirs)

        for formatter_dir in dirs:
            fn_inf = os.path.join(formatter_dir, 'install.inf')
            s_module = app.ini_read(fn_inf, 'info', 'subdir', '')

            # Read global defaults from [info] section
            global_config = app.ini_read(fn_inf, 'info', 'config', '')
            global_config_global = app.ini_read(fn_inf, 'info', 'config_global', '')
            global_config_local = app.ini_read(fn_inf, 'info', 'config_local', '')
            global_help = app.ini_read(fn_inf, 'info', 'help', '')

            for index in range(1, MAX_FORMATTERS_PER_PLUGIN):
                section = 'fmt'+str(index)
                s_method = app.ini_read(fn_inf, section, 'method', '')
                if not s_method: break
                s_lexers = app.ini_read(fn_inf, section, 'lexers', '')
                if not s_lexers: break
                s_caption = app.ini_read(fn_inf, section, 'caption', '')
                if not s_caption: break

                # Legacy mode: config= (file-based)
                s_config = app.ini_read(fn_inf, section, 'config', '')

                # New mode: config_global=/config_local=/help= (method-based)
                s_config_global = app.ini_read(fn_inf, section, 'config_global', '')
                s_config_local = app.ini_read(fn_inf, section, 'config_local', '')
                s_help = app.ini_read(fn_inf, section, 'help', '')

                # Inherit from [info] if not specified in [fmtX]
                if not s_config and not s_config_global:
                    s_config = global_config
                    s_config_global = global_config_global
                if not s_config_local:
                    s_config_local = global_config_local
                if not s_help:
                    s_help = global_help

                force_all = app.ini_read(fn_inf, section, 'force_all', '') == '1'
                minifier = app.ini_read(fn_inf, section, 'minifier', '') == '1'

                helper = {
                        'dir': formatter_dir,
                        'module': s_module,
                        'method': s_method,
                        'func': None,
                        'lexers': s_lexers,
                        'caption': s_caption,
                        'config': s_config,  # Legacy: config file name
                        'config_global': s_config_global,  # New: method name
                        'config_local': s_config_local,    # New: method name
                        'help': s_help,                    # New: method name
                        'force_all': force_all,
                        'minifier': minifier,
                        'label': None,
                        'on_save': False,
                        }

                self.helpers.append(helper)

    def get_item_props(self, helper: Dict[str, Any]) -> Tuple[Callable, str, bool]:
        """Get formatter properties and ensure function is loaded.

        Args:
            helper: Formatter dictionary with module/method info

        Returns:
            Tuple of (func, caption, force_all)

        Raises:
            AttributeError: If method not found in module
            ImportError: If module cannot be imported
            ValueError: If helper missing required keys
        """
        func = helper.get('func')
        caption = helper.get('caption', 'Unknown')
        force_all = helper.get('force_all', False)

        if func is None:
            module_name = helper.get('module')
            method_name = helper.get('method')

            if not module_name or not method_name:
                raise ValueError(f'Helper missing module or method: {helper}')

            _m = _import_module_cached(module_name)
            func = getattr(_m, method_name)
            helper['func'] = func

        return (func, caption, force_all)

    def get_props(self, lexer: str) -> Optional[Tuple[Callable, str, bool]]:
        """Get formatter properties for lexer.

        Args:
            lexer: Lexer name to search for

        Returns:
            Tuple of (func, caption, force_all) or None if no formatter/user cancelled
        """
        d = self.helpers_for_lexer(lexer)
        if not d:
            return None

        if len(d) == 1:
            item = d[0]
        else:
            items = [item.get('caption', 'Unknown') for item in d]
            res = app.dlg_menu(app.DMENU_LIST, items, caption=_('Formatters for %s')%lexer)
            if res is None:
                return None  # User cancelled
            item = d[res]

        return self.get_item_props(item)

    def get_props_on_save(self, lexer: str) -> Optional[Tuple[Callable, str, bool]]:
        """Get formatter properties for on_save event.

        Args:
            lexer: Lexer name

        Returns:
            Tuple of (func, caption, force_all) or None if no formatter with on_save
        """
        d = self.helpers_for_lexer(lexer)
        if not d:
            return None

        d = [h for h in d if h.get('on_save')]
        if not d:
            return None
        return self.get_item_props(d[0])

helpers = Helpers()
helpers.load_dir(app.app_path(app.APP_DIR_PY))
print(_('Formatters: ') + ', '.join(helpers.lexers()))

def get_config_filename(caption: str) -> Optional[str]:
    """Get current config filename for formatter by caption.

    Args:
        caption: Formatter caption to search for

    Returns:
        Path to config file or None if not found
    """
    for helper in helpers.helpers:
        config = helper.get('config')
        if helper.get('caption') == caption and config:
            config_file = config
            config_dir = helper.get('dir', '')
            if config_dir:
                cfg = FmtConfig(config_file, config_dir)
                return cfg.current_filename()
    return None

class Command:

    def __init__(self) -> None:

        self.load_labels()

    def load_labels(self) -> None:
        """Load formatter labels from config file."""
        if not os.path.isfile(FN_CFG):
            return

        with open(FN_CFG, 'r', encoding='utf8') as f:
            all_data = json.load(f)

        # Define mappings: config_key -> helper_key
        mappings = [
            ('labels', 'label'),
            ('labels_x', 'label_x'),
            ('on_save', 'on_save'),
        ]

        for config_key, helper_key in mappings:
            data = all_data.get(config_key)
            if data:
                for caption, value in data.items():
                    for helper in helpers.helpers:
                        if helper.get('caption') == caption:
                            helper[helper_key] = value
                            break

    def format(self) -> None:
        """Format current file/selection using appropriate formatter for lexer."""

        lexer = Helpers.get_editor_lexer()
        if not lexer:
            return

        res = helpers.get_props(lexer)
        if res is None:
            app.msg_status(_('No formatters for "%s"')%lexer)
            return

        func, caption, force_all = res
        run_format(ed, func, '['+caption+'] ', force_all)

    def on_save_pre(self, ed_self: Any) -> None:
        """Event handler: auto-format before save if configured.

        Args:
            ed_self: Editor instance
        """

        lexer = ed_self.get_prop(app.PROP_LEXER_FILE)
        if not lexer:
            return

        res = helpers.get_props_on_save(lexer)
        if not res: # None or False
            return

        func, caption, _ = res
        run_format(ed_self, func, '['+caption+'] ', True)

    def config(self, is_global: bool) -> None:
        """Open formatter configuration (global or local).

        Supports both legacy file-based config and new method-based config.
        If only one formatter is configurable, opens it directly without menu.
        Only shows formatters that support the current file's lexer.

        Args:
            is_global: True for global config, False for local config
        """
        # Get current lexer
        lexer = Helpers.get_editor_lexer()
        if not lexer:
            return

        # Get formatters for this lexer
        all_items = helpers.helpers_for_lexer(lexer)
        if not all_items:
            app.msg_status(_('No formatters for "%s"') % lexer)
            return

        # Filter items that have ANY config method
        items = [item for item in all_items
                 if item.get('config') or item.get('config_global') or item.get('config_local')]

        if not items:
            app.msg_status(_('No configurable formatters for "%s"') % lexer)
            return

        # If only one formatter, use it directly (same behavior as format())
        if len(items) == 1:
            item = items[0]
        else:
            # Multiple formatters: show menu
            caps = ['%s\t%s' % (item.get('caption', 'Unknown'), item.get('lexers', '')) for item in items]
            res = app.dlg_menu(app.DMENU_LIST, caps, caption=_('Formatters for %s') % lexer)
            if res is None:
                return
            item = items[res]

        # Determine which config method to use
        if is_global:
            method_name = item.get('config_global')
        else:
            method_name = item.get('config_local')

        # New method-based config (priority)
        if method_name:
            module_path = item.get('module')
            if module_path:
                try:
                    # Import module (use cache if already loaded)
                    _m = _import_module_cached(module_path)
                    # Call method with automatic fallback to Command class
                    _call_method_by_name(_m, method_name)
                    return

                except AttributeError as e:
                    app.msg_status(_('Config method "%s" not found in module "%s"') %
                                  (method_name, module_path))
                    return
                except ImportError as e:
                    app.msg_status(_('Cannot import module "%s": %s') % (module_path, str(e)))
                    return
                except Exception as e:
                    app.msg_status(_('Error calling config method: %s') % str(e))
                    return

        # Legacy file-based config (fallback)
        config_file = item.get('config')
        if config_file:
            config_dir = item.get('dir', '')
            if config_dir:
                cfg = FmtConfig(config_file, config_dir)
                if is_global:
                    cfg.config_global()
                else:
                    cfg.config_local()
        else:
            app.msg_status(_('No configuration available for "%s"') % item.get('caption', 'formatter'))

    def config_help(self) -> None:
        """Show help for selected formatter.

        Calls custom help method if available.
        Automatically tries module function first, then Command class method.
        If only one formatter has help, shows it directly without menu.
        Only shows formatters that support the current file's lexer.
        """
        # Get current lexer
        lexer = Helpers.get_editor_lexer()
        if not lexer:
            return

        # Get formatters for this lexer
        all_items = helpers.helpers_for_lexer(lexer)
        if not all_items:
            app.msg_status(_('No formatters for "%s"') % lexer)
            return

        # Filter items that have help method OR readme file
        items = []
        for item in all_items:
            if item.get('help'):
                items.append(item)
            else:
                item_dir = item.get('dir', '')
                if item_dir:
                    readme = os.path.join(item_dir, README_PATH)
                    if os.path.isfile(readme):
                        items.append(item)

        if not items:
            app.msg_status(_('No formatters with help available for "%s"') % lexer)
            return

        # If only one formatter, use it directly (same behavior as format())
        if len(items) == 1:
            item = items[0]
        else:
            # Multiple formatters: show menu
            caps = ['%s\t%s' % (item.get('caption', 'Unknown'), item.get('lexers', '')) for item in items]
            res = app.dlg_menu(app.DMENU_LIST, caps, caption=_('Formatter Help for %s') % lexer)
            if res is None:
                return
            item = items[res]

        method_name = item.get('help')

        if method_name:
            module_path = item.get('module')
            if module_path:
                try:
                    _m = _import_module_cached(module_path)
                    _call_method_by_name(_m, method_name)
                    return

                except AttributeError as e:
                    app.msg_status(_('Help method "%s" not found in module "%s"') %
                                  (method_name, module_path))
                except ImportError as e:
                    app.msg_status(_('Cannot import module "%s": %s') % (module_path, str(e)))
                except Exception as e:
                    app.msg_status(_('Error calling help method: %s') % str(e))

        # Fallback: try readme (executes if no method_name OR if exception occurred)
        item_dir = item.get('dir', '')
        if item_dir:
            readme = os.path.join(item_dir, README_PATH)
            if os.path.isfile(readme):
                app.file_open(readme)
            else:
                app.msg_status(_('No help available for "%s"') % item.get('caption', 'formatter'))
        else:
            app.msg_status(_('No help available for "%s"') % item.get('caption', 'formatter'))

    def config_global(self) -> None:
        """Open global formatter configuration.

        Only shows formatters that support the current file's lexer.
        Delegates to config(is_global=True).
        """
        self.config(True)

    def config_local(self) -> None:
        """Open local formatter configuration for current file.

        Requires file to be saved (not untitled).
        Only shows formatters that support the current file's lexer.
        """
        filename = ed.get_filename()

        if not filename:
            app.msg_box(
                _('Cannot open local config for untitled tab'),
                app.MB_OK + app.MB_ICONWARNING
            )
            return

        # Verify file exists on disk
        if not os.path.isfile(filename):
            app.msg_box(
                _('File must be saved before creating local config'),
                app.MB_OK + app.MB_ICONWARNING
            )
            return

        # Delegate to config() which now filters by lexer
        self.config(False)

    def _save_label_to_config(self, key: str, caption: str, value: Any) -> None:
        """Save label configuration to JSON file (internal helper).

        Args:
            key: Config key (e.g., 'labels', 'on_save')
            caption: Formatter caption
            value: Value to save, or None to delete
        """
        data = {}
        if os.path.isfile(FN_CFG):
            with open(FN_CFG, 'r', encoding='utf8') as f:
                data = json.load(f)

        if key in data:
            if value is not None:
                data[key][caption] = value
            else:
                data[key].pop(caption, None)
        else:
            if value is not None:
                data[key] = {caption: value}

        with open(FN_CFG, 'w', encoding='utf8') as f:
            json.dump(data, f, indent=2)

    def config_labels(self) -> None:
        """Configure per-lexer labels for formatters.

        Allows assigning labels A, B, C, D to formatters for quick access.
        """
        self.config_labels_ex(
            _('Formatters per-lexer labels'),
            'ABCD',
            'label',
            'labels'
        )

    def config_labels_cross(self) -> None:
        """Configure cross-lexer labels for formatters.

        Allows assigning labels 1, 2, 3, 4 to formatters for cross-lexer access.
        """
        self.config_labels_ex(
            _('Formatters cross-lexer labels'),
            '1234',
            'label_x',
            'labels_x'
        )

    def config_labels_ex(self, caption: str, chars: str, key_label: str, key_labels: str) -> None:
        """Configure labels for formatters (internal helper).

        Args:
            caption: Menu caption to display
            chars: String of available label characters (e.g., 'ABCD' or '1234')
            key_label: Dictionary key for individual formatter label (e.g., 'label' or 'label_x')
            key_labels: Dictionary key for all labels in config (e.g., 'labels' or 'labels_x')
        """
        while True:
            caps = []
            for item in helpers.helpers:
                label_val = item.get(key_label)
                cap = (
                    item.get('caption', 'Unknown') +
                    ((' -- ' + label_val) if label_val else '') +
                    '	' + item.get('lexers', '')
                )
                caps.append(cap)
            res = app.dlg_menu(app.DMENU_LIST, caps, caption=caption)
            if res is None:
                return

            helper = helpers.helpers[res]
            label = helper.get(key_label) or '_'

            res = app.dlg_menu(app.DMENU_LIST,
                [_('(None)'), chars[0], chars[1], chars[2], chars[3]],
                focused = ('_'+chars).find(label),
                caption = _('Label for "%s"') % helper.get('caption', 'Unknown')
                )
            if res is None:
                continue
            if res == 0:
                label = None
            else:
                label = ('_'+chars)[res]

            helper[key_label] = label

            # Save to config using helper method
            helper_caption = helper.get('caption', 'unknown')
            self._save_label_to_config(key_labels, helper_caption, label)

    def config_label_save(self) -> None:
        """Configure on_save auto-formatting for formatters.

        Enables/disables automatic formatting when file is saved.
        """
        while True:
            caps = [
                item.get('caption', 'Unknown') +
                (' -- on_save' if item.get('on_save') else '') +
                '\t' + item.get('lexers', '')
                for item in helpers.helpers
            ]
            res = app.dlg_menu(app.DMENU_LIST, caps, caption=_('Formatters label "on_save"'))
            if res is None:
                return

            helper = helpers.helpers[res]
            helper['on_save'] = not helper.get('on_save', False)

            # Save to config using helper method
            helper_caption = helper.get('caption', 'unknown')
            value = True if helper.get('on_save') else None
            self._save_label_to_config('on_save', helper_caption, value)

    def format_label(self, label: str) -> None:
        """Format using formatter with given per-lexer label (A/B/C/D).

        Args:
            label: Label character to search for
        """

        lexer = Helpers.get_editor_lexer()
        if not lexer:
            return

        items = helpers.helpers_for_lexer(lexer)
        if not items:
            app.msg_status(_('No formatters for "%s"')%lexer)
            return

        for helper in items:
            if helper.get('label') == label:
                func, caption, force_all = helpers.get_item_props(helper)
                run_format(
                    ed,
                    func,
                    '['+caption+'] ',
                    force_all
                    )
                return

        app.msg_status(_('No formatter for "{}" with label "{}"').format(lexer, label))

    def format_label_x(self, label: str) -> None:
        """Format using formatter with given cross-lexer label (1/2/3/4).

        Args:
            label: Label character to search for
        """

        if len(ed.get_carets()) > 1:
            app.msg_status(_('Cannot handle multi-carets yet'))
            return

        for helper in helpers.helpers:
            if helper.get('label_x') == label:
                func, caption, force_all = helpers.get_item_props(helper)
                run_format(
                    ed,
                    func,
                    '['+caption+'] ',
                    force_all
                    )
                return

        app.msg_status(_('No cross-lexer formatter with label "{}"').format(label))

    def get_min_filename(self, fn: str) -> Tuple[str, str]:
        """Generate minified filename.

        Args:
            fn: Original filename

        Returns:
            Tuple of (minified_filename, error_message)
            If error_message is not empty, minified_filename will be empty string
        """
        if not fn:
            return '', _('Cannot handle untitled tab')

        file_dir = os.path.dirname(fn)
        file_name = os.path.basename(fn)
        dot_pos = file_name.rfind('.')
        if dot_pos < 0:
            return '', _('File name does not contain "." char')

        fn_new = os.path.join(file_dir, file_name[:dot_pos] + '.min' + file_name[dot_pos:])
        return fn_new, ''

    def minify(self) -> None:
        """Minify current file to separate .min.ext file."""

        fn_new, error = self.get_min_filename(ed.get_filename())
        if not fn_new:
            app.msg_status(error)
            return

        lexer = Helpers.get_editor_lexer()
        if not lexer:
            app.msg_status(_('No lexer active'))
            return

        items = helpers.helpers_for_lexer(lexer)
        if not items:
            app.msg_status(_('No formatters for "%s"')%lexer)
            return

        for helper in items:
            if helper.get('minifier'):
                func, caption, force_all = helpers.get_item_props(helper)
                text0 = ed.get_text_all()
                text = func(text0)
                is_same = text == text0
                del text0
                if is_same:
                    app.msg_status(_('Already minified'))
                    return
                with open(fn_new, 'w', encoding='utf-8') as f:
                    f.write(text)
                app.msg_status(_('Minified to "%s"'%os.path.basename(fn_new)))
                file_open(fn_new, -1, '/passive')
                return

        app.msg_status(_('No minifier for "%s"')%lexer)

    def format_a(self) -> None:

        self.format_label('A')

    def format_b(self) -> None:

        self.format_label('B')

    def format_c(self) -> None:

        self.format_label('C')

    def format_d(self) -> None:

        self.format_label('D')

    def format_1(self) -> None:

        self.format_label_x('1')

    def format_2(self) -> None:

        self.format_label_x('2')

    def format_3(self) -> None:

        self.format_label_x('3')

    def format_4(self) -> None:

        self.format_label_x('4')
