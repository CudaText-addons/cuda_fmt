from cudatext import *
from .fmtconfig import ed_filename

def is_selected(carets):

    for c in carets:
        if c[2]>=0:
            return True
    return False


def run_format(ed, do_format, msg, force_all):

    if ed.get_sel_mode() != SEL_NORMAL:
        msg_status(msg + "Column selection is not supported")
        return

    ed_filename = ed.get_filename()
    carets = ed.get_carets()
    use_all = force_all or not is_selected(carets)

    if not use_all:
        nsel = 0
        for x0, y0, x1, y1 in reversed(carets):
            if y1<0: continue
            if (y0, x0)>(y1, x1):
                x0, y0, x1, y1 = x1, y1, x0, y0

            text1 = ed.get_text_substr(x0, y0, x1, y1)
            if not text1.strip():
                continue

            with_eol = text1.endswith('\n')
            if with_eol:
                text1 = text1.rstrip('\n')

            text = do_format(text1)
            if not text:
                continue
            if text==text1:
                continue

            if with_eol:
                text += '\n'

            ed.set_caret(x0, y0)
            ed.replace(x0, y0, x1, y1, text)
            nsel += 1

        if nsel>1:
            msg_status(msg + "Formatted %d selections"%nsel)
        elif nsel==1:
            msg_status(msg + "Formatted selection")
        else:
            msg_status(msg + "Cannot format selection(s)")

    else:
        # format entire file
        x0, y0, x1, y1 = ed.get_carets()[0]
        text1 = ed.get_text_all()
        if not text1.strip():
            return
        text = do_format(text1)

        if not text:
            msg_status(msg + "Cannot format text")
            return

        if text==text1:
            msg_status(msg + 'Text is already formatted')
            return

        ed.set_text_all(text)
        msg_status(msg + "Formatted entire text")

        # restore caret pos
        cnt = ed.get_line_count()
        if y0 < cnt and y1 < cnt:
            ed.set_caret(x0, y0, x1, y1)
        else:
            ed.set_caret(0, min(y0, y1))
