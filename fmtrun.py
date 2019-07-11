from cudatext import *

def is_selected(carets):

    for c in carets:
        if c[2]>=0:
            return True
    return False


def run_format(do_format, msg, force_all):

    if ed.get_sel_mode() != SEL_NORMAL:
        msg_status(msg + "Column selection is not supported")
        return

    carets = ed.get_carets()
    use_all = force_all or not is_selected(carets)

    if not use_all:
        nsel = 0
        for x0, y0, x1, y1 in reversed(carets):
            if y1<0: continue
            if (y0, x0)>(y1, x1):
                x0, y0, x1, y1 = x1, y1, x0, y0

            text = ed.get_text_substr(x0, y0, x1, y1)
            with_eol = text.endswith('\n')
            if with_eol:
                text = text.rstrip('\n')

            text = do_format(text)
            if not text:
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
        text1 = ed.get_text_all()
        text = do_format(text1)
        if not text:
            msg_status(msg + "Cannot format text")
            return

        if text==text1:
            msg_status(msg + 'Text is already formatted')
            return

        ed.set_caret(0, 0)
        ed.set_text_all(text)
        msg_status(msg + "Formatted entire text")
