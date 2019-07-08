import os
import shutil
from cudatext import *

class FmtConfig:
    def __init__(self, fn, dir):
        self.fn = fn
        self.dir = dir
    
    def ini_global(self):
        ini = os.path.join(app_path(APP_DIR_SETTINGS), self.fn)
        ini0 = os.path.join(self.dir, self.fn)
        if not os.path.isfile(ini) and os.path.isfile(ini0):
            shutil.copyfile(ini0, ini)
        return ini

    def ini_local(self):
        fn = ed.get_filename()
        if fn:
            return os.path.join(os.path.dirname(fn), self.fn)
        else:
            return ''

    def current_filename(self):
        ini_g = self.ini_global()
        ini_l = self.ini_local()
        if os.path.isfile(ini_l):
            return ini_l
        else:
            return ini_g

    def config_global(self):
        ini = self.ini_global()
        if os.path.isfile(ini):
            file_open(ini)
        else:
            msg_box('Global config file "%s" not found' % self.fn, MB_OK)

    def config_local(self):
        if not ed.get_filename():
            msg_box('Cannot open local config file for untitled tab', MB_OK)
            return
        ini = self.ini_local()
        ini0 = self.ini_global()
        if os.path.isfile(ini):
            file_open(ini)
            return
        if not os.path.isfile(ini0):
            msg_box('Global config file "%s" not found' % self.fn, MB_OK)
            return
        if msg_box('Local config file "%s" not found.\nDo you want to create it?' % self.fn, MB_OKCANCEL)==ID_OK:
            shutil.copyfile(ini0, ini)
            if os.path.isfile(ini):
                file_open(ini)
            else:
                msg_box('Cannot copy global config file "%s" to local folder' % self.fn, MB_OK)

