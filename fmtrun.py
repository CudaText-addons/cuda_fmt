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
        text = do_format(text)
        if not text:
            msg_status(msg + "Cannot format text")
            return

        msg_status(msg + "Formatted selection")

        x0, y0, x1, y1 = ed.get_carets()[0]
        if (y0, x0)>(y1, x1):
            x0, y0, x1, y1 = x1, y1, x0, y0

        ed.set_caret(x0, y0)
        ed.delete(x0, y0, x1, y1)
        ed.insert(x0, y0, text)
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
