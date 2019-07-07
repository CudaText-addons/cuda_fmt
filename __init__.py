import os
import importlib
import cudatext as app
from cudatext import ed
from . import format_proc

MAX_SECTIONS = 8

class Command:
    helpers = {}

    def __init__(self):

        dir = app.app_path(app.APP_DIR_PY)
        dirs = os.listdir(dir)
        dirs = [os.path.join(dir, s) for s in dirs if s.startswith('cuda_fmt_')]
        for dir in dirs:
            fn_inf = os.path.join(dir, 'install.inf')
            s_module = app.ini_read(fn_inf, 'info', 'subdir', '')
            for index in range(1, MAX_SECTIONS+1):
                section = 'fmt'+str(index)
                s_method = app.ini_read(fn_inf, section, 'method', '')
                if not s_method: continue
                s_lexers = app.ini_read(fn_inf, section, 'lexers', '')
                if not s_lexers: continue
                s_caption = app.ini_read(fn_inf, section, 'caption', '')
                helper = {
                        'caption': s_caption,
                        'module': s_module,
                        'method': s_method,
                        }
                for s_lex in s_lexers.split(','):
                    if s_lex not in self.helpers:
                        self.helpers[s_lex] = []
                    self.helpers[s_lex] = self.helpers[s_lex] + [helper]

        items = sorted(list(self.helpers.keys()))
        if items:
            print('Formatters: ' + ', '.join(items))


    def get_func(self, lexer):

        d = self.helpers.get(lexer)
        if not d: return

        if len(d)==1:
            item = d[0]
        else:
            items = [item['caption'] for item in d]
            res = app.dlg_menu(app.MENU_LIST, items, caption='Formatters for %s'%lexer)
            if res is None: return
            item = d[res]
            
        module = item['module']
        method = item['method']
        caption = item['caption']
        _m = importlib.import_module(module)
        func = getattr(_m, method)
        return (func, caption)


    def format(self):

        lexer = ed.get_prop(app.PROP_LEXER_FILE)
        if not lexer:
            app.msg_status('No formatters for None-lexer')
            return

        res = self.get_func(lexer)
        if not res:
            app.msg_status('No formatters for lexer "%s"'%lexer)
            return
            
        func, caption = res
        format_proc.run(func, '['+caption+'] ')
