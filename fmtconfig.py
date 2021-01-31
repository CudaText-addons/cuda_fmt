import os
import shutil
from cudatext import *

from cudax_lib import get_translation
_   = get_translation(__file__)  # i18n

ed_filename = ''
ed_lexer = ''

class FmtConfig:
    def __init__(self, fn, dir):
        self.fn = fn
        self.dir = dir

        ini = os.path.join(app_path(APP_DIR_SETTINGS), fn)
        ini0 = os.path.join(self.dir, fn)
        if not os.path.isfile(ini) and os.path.isfile(ini0):
            shutil.copyfile(ini0, ini)
        self.ini_global = ini

    def ini_local(self):
        if ed_filename:
            return os.path.join(os.path.dirname(ed_filename), self.fn)
        else:
            return ''

    def current_filename(self):
        ini = self.ini_local()
        if os.path.isfile(ini):
            return ini
        else:
            return self.ini_global

    def config_global(self):
        if os.path.isfile(self.ini_global):
            file_open(self.ini_global)
        else:
            msg_box(_('Global config file "%s" not found') % self.fn, MB_OK)

    def config_local(self):
        global ed_filename
        ed_filename = ed.get_filename()

        if not ed_filename:
            msg_box(_('Cannot open local config file for untitled tab'), MB_OK)
            return

        ini = self.ini_local()
        ini0 = self.ini_global
        if os.path.isfile(ini):
            file_open(ini)
            return

        if not os.path.isfile(ini0):
            msg_box(_('Global config file "%s" not found') % self.fn, MB_OK)
            return

        if msg_box(_('Local config file "%s" not found.\nDo you want to create it?') % self.fn, MB_OKCANCEL)==ID_OK:
            shutil.copyfile(ini0, ini)
            if os.path.isfile(ini):
                file_open(ini)
            else:
                msg_box(_('Cannot copy global config file "%s" to local folder') % self.fn, MB_OK)
