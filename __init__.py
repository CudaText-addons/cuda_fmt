import os
import re
import json
import importlib
import cudatext as app
from cudatext import ed
from .fmtconfig import *
from .fmtrun import *

FN_CFG = os.path.join(app.app_path(app.APP_DIR_SETTINGS), 'cuda_fmt.json')

class Helpers:
    helpers = []

    def lexers(self):

        r = ''
        for helper in self.helpers:
            r += helper['lexers']+','
        r = sorted(list(set(r.split(','))))
        r.remove('')
        return r


    def helpers_for_lexer(self, lexer):

        res = []
        if lexer in ('', '-'):
            return
        for helper in self.helpers:
            for item in helper['lexers'].split(','):
                if item.startswith('regex:'):
                    ok = re.match(item[6:], lexer)
                else:
                    ok = item==lexer
                if ok:
                    res.append(helper)
        return res


    def load_dir(self, dir):

        dirs = os.listdir(dir)
        dirs = [os.path.join(dir, s) for s in dirs if s.startswith('cuda_fmt_')]
        dirs = sorted(dirs)

        for dir in dirs:
            fn_inf = os.path.join(dir, 'install.inf')
            s_module = app.ini_read(fn_inf, 'info', 'subdir', '')
            for index in range(1, 100):
                section = 'fmt'+str(index)
                s_method = app.ini_read(fn_inf, section, 'method', '')
                if not s_method: break
                s_lexers = app.ini_read(fn_inf, section, 'lexers', '')
                if not s_lexers: break
                s_caption = app.ini_read(fn_inf, section, 'caption', '')
                if not s_caption: break
                s_config = app.ini_read(fn_inf, section, 'config', '')
                force_all = app.ini_read(fn_inf, section, 'force_all', '')=='1'

                helper = {
                        'dir': dir,
                        'module': s_module,
                        'method': s_method,
                        'lexers': s_lexers,
                        'caption': s_caption,
                        'config': s_config,
                        'force_all': force_all,
                        'label': None,
                        'on_save': False,
                        }

                self.helpers.append(helper)


    def get_props(self, lexer):

        d = self.helpers_for_lexer(lexer)
        if not d: return

        if len(d)==1:
            item = d[0]
        else:
            items = [item['caption'] for item in d]
            res = app.dlg_menu(app.MENU_LIST, items, caption='Formatters for %s'%lexer)
            if res is None: return False
            item = d[res]

        module = item['module']
        method = item['method']
        caption = item['caption']
        force_all = item['force_all']

        _m = importlib.import_module(module)
        func = getattr(_m, method)
        return (func, caption, force_all)


helpers = Helpers()
helpers.load_dir(app.app_path(app.APP_DIR_PY))
print('Formatters: ' + ', '.join(helpers.lexers()))


def get_config_filename(caption):

    for helper in helpers.helpers:
        if helper['caption']==caption and helper['config']:
            cfg = FmtConfig(helper['config'], helper['dir'])
            return cfg.current_filename()



class Command:

    def __init__(self):

        self.load_labels()


    def load_labels(self):

        if not os.path.isfile(FN_CFG):
            return

        with open(FN_CFG, 'r', encoding='utf8') as f:
            all = json.load(f)

            data = all.get('labels')
            if data:
                for key in data:
                    val = data[key]
                    for helper in helpers.helpers:
                        if helper['caption'] == key:
                            helper['label'] = val
                            #print(helper)
                            continue

            data = all.get('on_save')
            if data:
                for key in data:
                    val = data[key]
                    for helper in helpers.helpers:
                        if helper['caption'] == key:
                            helper['on_save'] = val
                            #print(helper)
                            continue


    def format(self):

        lexer = ed.get_prop(app.PROP_LEXER_FILE)
        if not lexer:
            app.msg_status('No formatters for None-lexer')
            return

        res = helpers.get_props(lexer)
        if res is None:
            app.msg_status('No formatters for "%s"'%lexer)
            return

        if res==False:
            return

        func, caption, force_all = res
        run_format(func, '['+caption+'] ', force_all)


    def config(self, is_global):

        items = [item for item in helpers.helpers if item['config']]
        if not items:
            app.msg_status('No configurable formatters')
            return

        caps = ['%s\t%s'%(item['caption'], item['lexers']) for item in items]

        res = app.dlg_menu(app.MENU_LIST, caps, caption='Formatters')
        if res is None: return
        item = items[res]

        cfg = FmtConfig(item['config'], item['dir'])
        if is_global:
            cfg.config_global()
        else:
            cfg.config_local()

    def config_global(self):

        self.config(True)

    def config_local(self):

        self.config(False)

    def config_labels(self):

        while True:
            caps = [item['caption']+((' -- '+item['label']) if item['label'] else '')+
                    '\t'+item['lexers'] for item in helpers.helpers]
            res = app.dlg_menu(app.MENU_LIST, caps, caption='Formatters labels')
            if res is None:
                return

            helper = helpers.helpers[res]
            label = helper['label'] or '_'

            res = app.dlg_menu(app.MENU_LIST,
                ['(None)', 'A', 'B', 'C', 'D'],
                focused = '_ABCD'.find(label),
                caption = 'Label for "%s"'%helper['caption']
                )
            if res is None:
                continue
            if res==0:
                label = None
            else:
                label = '_ABCD'[res]

            helper['label'] = label

            data = {}
            if os.path.isfile(FN_CFG):
                with open(FN_CFG, 'r', encoding='utf8') as f:
                    data = json.load(f)

            if 'labels' in data:
                if label:
                    data['labels'][helper['caption']] = label
                else:
                    del data['labels'][helper['caption']]
            else:
                if label:
                    data['labels'] = {helper['caption']: label}

            with open(FN_CFG, 'w', encoding='utf8') as f:
                s = json.dumps(data, indent=2)
                f.write(s)


    def config_label_save(self):

        while True:
            caps = [item['caption']+(' -- on_save' if item['on_save'] else '')+
                    '\t'+item['lexers'] for item in helpers.helpers]
            res = app.dlg_menu(app.MENU_LIST, caps, caption='Formatters label "save"')
            if res is None:
                return

            helper = helpers.helpers[res]
            helper['on_save'] = not helper['on_save']

            data = {}
            if os.path.isfile(FN_CFG):
                with open(FN_CFG, 'r', encoding='utf8') as f:
                    data = json.load(f)

            if 'on_save' in data:
                if helper['on_save']:
                    data['on_save'][helper['caption']] = True
                else:
                    del data['on_save'][helper['caption']]
            else:
                if helper['on_save']:
                    data['on_save'] = {helper['caption']: True}

            with open(FN_CFG, 'w', encoding='utf8') as f:
                s = json.dumps(data, indent=2)
                f.write(s)


    def format_label(self, label):

        lexer = ed.get_prop(app.PROP_LEXER_FILE)
        if not lexer:
            return

        items = helpers.helpers_for_lexer(lexer)
        if not items:
            app.msg_status('No formatters for "%s"'%lexer)
            return

        for helper in items:
            if helper['label']==label:
                _m = importlib.import_module(helper['module'])
                func = getattr(_m, helper['method'])
                run_format(
                    func,
                    '['+helper['caption']+'] ',
                    helper['force_all']
                    )
                return

        app.msg_status('No formatter for "%s" with label "%s"'%(lexer, label))


    def format_a(self):

        self.format_label('A')

    def format_b(self):

        self.format_label('B')

    def format_c(self):

        self.format_label('C')

    def format_d(self):

        self.format_label('D')
