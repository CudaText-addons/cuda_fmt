import os
import re
import json
import importlib
import cudatext as app
from cudatext import ed
from .fmtconfig import *
from .fmtrun import *

from cudax_lib import get_translation
_   = get_translation(__file__)  # i18n

FN_CFG = os.path.join(app.app_path(app.APP_DIR_SETTINGS), 'cuda_fmt.json')

class Helpers:
    helpers = []

    def get_editor_lexer():

        carets = ed.get_carets()
        if len(carets)==0:
            app.msg_status(_('Cannot handle none-carets'))
            return

        if len(carets)>1:
            app.msg_status(_('Cannot handle multi-carets yet'))
            return

        lexer0 = ed.get_prop(app.PROP_LEXER_FILE)
        if not lexer0:
            app.msg_status(_('Cannot handle None-lexer'))
            return

        x1, y1, x2, y2 = carets[0]
        if y2<0:
            return lexer0

        if (y1, x1)>(y2, x2):
            x1, y1, x2, y2 = x2, y2, x1, y1

        # decrease ending pos, it's often after the sub-lexer ending
        if x2>0:
            x2 -= 1
        elif y2>0:
            y2 -= 1
            x2 = len(ed.get_text_line(y2))

        lexer1 = ed.get_prop(PROP_LEXER_POS, (x1, y1))
        lexer2 = ed.get_prop(PROP_LEXER_POS, (x2, y2))
        if lexer1!=lexer2:
            app.msg_status(_('Selection overlaps sub-lexer block: "{}"/"{}"').format(lexer1, lexer2))
            return

        return lexer1


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
                        'func': None,
                        'lexers': s_lexers,
                        'caption': s_caption,
                        'config': s_config,
                        'force_all': force_all,
                        'label': None,
                        'on_save': False,
                        }

                self.helpers.append(helper)


    def get_item_props(self, helper):

        func = helper['func']
        caption = helper['caption']
        force_all = helper['force_all']

        if func is None:
            _m = importlib.import_module(helper['module'])
            func = getattr(_m, helper['method'])
            helper['func'] = func

        return (func, caption, force_all)


    def get_props(self, lexer):

        d = self.helpers_for_lexer(lexer)
        if not d: return

        if len(d)==1:
            item = d[0]
        else:
            items = [item['caption'] for item in d]
            res = app.dlg_menu(app.DMENU_LIST, items, caption=_('Formatters for %s')%lexer)
            if res is None: return False
            item = d[res]

        return self.get_item_props(item)


    def get_props_on_save(self, lexer):

        d = self.helpers_for_lexer(lexer)
        if not d: return

        d = [h for h in d if h['on_save']]
        if not d: return
        return self.get_item_props(d[0])


helpers = Helpers()
helpers.load_dir(app.app_path(app.APP_DIR_PY))
print(_('Formatters: ') + ', '.join(helpers.lexers()))


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

            data = all.get('labels_x')
            if data:
                for key in data:
                    val = data[key]
                    for helper in helpers.helpers:
                        if helper['caption'] == key:
                            helper['label_x'] = val
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

        lexer = Helpers.get_editor_lexer()
        if not lexer:
            return

        res = helpers.get_props(lexer)
        if res is None:
            app.msg_status(_('No formatters for "%s"')%lexer)
            return

        if res is False:
            return

        func, caption, force_all = res
        run_format(ed, func, '['+caption+'] ', force_all)


    def on_save_pre(self, ed_self):

        lexer = ed_self.get_prop(app.PROP_LEXER_FILE)
        if not lexer:
            return

        res = helpers.get_props_on_save(lexer)
        if not res: # None or False
            return

        func, caption, _ = res
        run_format(ed_self, func, '['+caption+'] ', True)


    def config(self, is_global):

        items = [item for item in helpers.helpers if item['config']]
        if not items:
            app.msg_status(_('No configurable formatters'))
            return

        caps = ['%s\t%s'%(item['caption'], item['lexers']) for item in items]

        res = app.dlg_menu(app.DMENU_LIST, caps, caption=_('Formatters'))
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

        if not ed.get_filename():
            msg_box(_('Cannot open local config for untitled tab'), MB_OK+MB_ICONWARNING)
            return

        self.config(False)


    def config_labels(self):

        self.config_labels_ex(
            _('Formatters per-lexer labels'),
            'ABCD',
            'label',
            'labels'
            )

    def config_labels_cross(self):

        self.config_labels_ex(
            _('Formatters cross-lexer labels'),
            '1234',
            'label_x',
            'labels_x'
            )

    def config_labels_ex(self, caption, chars, key_label, key_labels):

        while True:
            caps = [item['caption']+((' -- '+item[key_label]) if item.get(key_label) else '')+
                    '\t'+item['lexers'] for item in helpers.helpers]
            res = app.dlg_menu(app.DMENU_LIST, caps, caption=caption)
            if res is None:
                return

            helper = helpers.helpers[res]
            label = helper.get(key_label) or '_'

            res = app.dlg_menu(app.DMENU_LIST,
                [_('(None)'), chars[0], chars[1], chars[2], chars[3]],
                focused = ('_'+chars).find(label),
                caption = _('Label for "%s"')%helper['caption']
                )
            if res is None:
                continue
            if res==0:
                label = None
            else:
                label = ('_'+chars)[res]

            helper[key_label] = label

            data = {}
            if os.path.isfile(FN_CFG):
                with open(FN_CFG, 'r', encoding='utf8') as f:
                    data = json.load(f)

            if key_labels in data:
                if label:
                    data[key_labels][helper['caption']] = label
                else:
                    del data[key_labels][helper['caption']]
            else:
                if label:
                    data[key_labels] = {helper['caption']: label}

            with open(FN_CFG, 'w', encoding='utf8') as f:
                s = json.dumps(data, indent=2)
                f.write(s)


    def config_label_save(self):

        while True:
            caps = [item['caption']+(' -- on_save' if item['on_save'] else '')+
                    '\t'+item['lexers'] for item in helpers.helpers]
            res = app.dlg_menu(app.DMENU_LIST, caps, caption=_('Formatters label "save"'))
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

        lexer = Helpers.get_editor_lexer()
        if not lexer:
            return

        items = helpers.helpers_for_lexer(lexer)
        if not items:
            app.msg_status(_('No formatters for "%s"')%lexer)
            return

        for helper in items:
            if helper.get('label')==label:
                func, caption, force_all = helpers.get_item_props(helper)
                run_format(
                    ed,
                    func,
                    '['+caption+'] ',
                    force_all
                    )
                return

        app.msg_status(_('No formatter for "{}" with label "{}"').format(lexer, label))


    def format_label_x(self, label):

        if len(ed.get_carets())>1:
            app.msg_status(_('Cannot handle multi-carets yet'))
            return

        for helper in helpers.helpers:
            if helper.get('label_x')==label:
                func, caption, force_all = helpers.get_item_props(helper)
                run_format(
                    ed,
                    func,
                    '['+caption+'] ',
                    force_all
                    )
                return

        app.msg_status(_('No cross-lexer formatter with label "{}"').format(label))


    def format_a(self):

        self.format_label('A')

    def format_b(self):

        self.format_label('B')

    def format_c(self):

        self.format_label('C')

    def format_d(self):

        self.format_label('D')


    def format_1(self):

        self.format_label_x('1')

    def format_2(self):

        self.format_label_x('2')

    def format_3(self):

        self.format_label_x('3')

    def format_4(self):

        self.format_label_x('4')
