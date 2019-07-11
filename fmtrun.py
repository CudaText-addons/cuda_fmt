from cudatext import *

def run_format(do_format, msg, force_all):

    if ed.get_sel_mode() != SEL_NORMAL:
        msg_status(msg + "Column/line selections not supported")
        return

    if force_all:
        text = ''
    else:
        text = ed.get_text_sel()

    if text:
        with_eol = text.endswith('\n')
        if with_eol:
            text = text.rstrip('\n')

        text = do_format(text)
        if not text:
            msg_status(msg + "Cannot format text")
            return

        if with_eol:
            text += '\n'

        x0, y0, x1, y1 = ed.get_carets()[0]
        if (y0, x0)>(y1, x1):
            x0, y0, x1, y1 = x1, y1, x0, y0

        ed.set_caret(x0, y0)
        ed.replace(x0, y0, x1, y1, text)

        msg_status(msg + "Formatted selection")

    else:
        text1 = ed.get_text_all()
        text = do_format(text1)
        if not text:
            msg_status(msg + "Cannot format text")
            return

        if text==text1:
            msg_status(msg + 'Text is already formatted')
            return

        msg_status(msg + "Formatted entire text")
        ed.set_caret(0, 0)
        ed.set_text_all(text)
