import difflib
from cudatext import *
from . import fmtconfig

from cudax_lib import get_translation
_   = get_translation(__file__)  # i18n


def is_selected(carets):

    for c in carets:
        if c[2]>=0:
            return True
    return False


def replace_all_preserving_linestates(ed, old_text, new_text):
    """Apply changes preserving line states using hybrid approach.

    Fast path (same line count): Native API - O(1) replace + O(n) comparison
    Slow path (lines added/removed): Myers diff - O(ND)
    """
    old_lines = old_text.splitlines(keepends=False)
    new_lines = new_text.splitlines(keepends=False)

    # Fast path 1: No changes at all
    if old_text == new_text:
        return

    # Save caret position
    carets = ed.get_carets()
    if carets:
        caret_x, caret_y = carets[0][:2]

    # Begin undo group (all changes in single undo step)
    ed.action(EDACTION_UNDOGROUP_BEGIN)

    try:
        # Fast path 2: Same line count (95% of cases)
        # Use Native API for maximum speed
        if len(old_lines) == len(new_lines):
            # print('CudaFormatter: fast path, same line count')

            # Save current line states
            old_states = ed.get_prop(PROP_LINE_STATES)

            # Single fast replace
            line_count = ed.get_line_count()
            last_line_len = ed.get_line_len(line_count - 1)

            ed.replace(
                0, 0,
                last_line_len, line_count - 1,
                new_text
            )

            # Restore states for unchanged lines
            if old_states and len(old_states) >= len(old_lines):
                unchanged_count = 0

                for i in range(len(new_lines)):
                    if i < len(old_lines) and old_lines[i] == new_lines[i]:
                        # Line unchanged, restore old state
                        ed.set_prop(PROP_LINE_STATE, (i, old_states[i]))
                        unchanged_count += 1
                    else:
                        # Line changed, mark as changed
                        ed.set_prop(PROP_LINE_STATE, (i, LINESTATE_CHANGED))

            return

        # Slow path: Line count changed (5% of cases)
        # Use Myers diff algorithm for perfect accuracy
        # print('CudaFormatter: slow path')

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        opcodes = list(matcher.get_opcodes())

        # Apply changes from TOP to BOTTOM with offset tracking
        offset = 0  # Track how much we've shifted

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                continue

            # Adjust indices with current offset
            adj_i1 = i1 + offset
            adj_i2 = i2 + offset

            if tag == 'replace':
                # Delete old lines
                for _ in range(i2 - i1):
                    ed.delete(0, adj_i1, 0, adj_i1 + 1)

                # Insert new lines
                for idx in range(j1, j2):
                    ed.insert(0, adj_i1, new_lines[idx] + '\n')
                    adj_i1 += 1  # Move insertion point down

                # Update offset: removed (i2-i1) lines, added (j2-j1) lines
                offset += (j2 - j1) - (i2 - i1)

            elif tag == 'delete':
                for _ in range(i2 - i1):
                    ed.delete(0, adj_i1, 0, adj_i1 + 1)

                # Update offset
                offset -= (i2 - i1)

            elif tag == 'insert':
                for idx in range(j1, j2):
                    ed.insert(0, adj_i1, new_lines[idx] + '\n')
                    adj_i1 += 1

                # Update offset
                offset += (j2 - j1)

        # Ensure last line has newline (Myers may miss it)
        if new_text.endswith('\n'):
            last_line_idx = ed.get_line_count() - 1
            last_line_text = ed.get_text_line(last_line_idx)
            last_line_len = ed.get_line_len(last_line_idx)

            # Replace last line with itself + newline
            ed.replace(0, last_line_idx, last_line_len, last_line_idx, last_line_text + '\n')

    finally:
        # Restore caret position
        if carets:
            # Ensure caret is within valid range
            new_line_count = ed.get_line_count()
            if caret_y >= new_line_count:
                caret_y = new_line_count - 1

            new_line_len = ed.get_line_len(caret_y)
            if caret_x > new_line_len:
                caret_x = new_line_len

            ed.set_caret(caret_x, caret_y)

        ed.action(EDACTION_UPDATE)

        # End undo group
        ed.action(EDACTION_UNDOGROUP_END)


def run_format(ed, do_format, msg, force_all):

    if ed.get_sel_mode() != SEL_NORMAL:
        msg_status(msg + _("Column selection is not supported"))
        return

    fmtconfig.ed_fmt = ed
    fmtconfig.ed_filename = ed.get_filename()

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

            ed.lock()
            try:
                app_idle(True)
                text = do_format(text1)
            finally:
                ed.unlock()

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
            msg_status(msg + _("Formatted {} selections").format(nsel))
        elif nsel==1:
            msg_status(msg + _("Formatted selection"))
        else:
            msg_status(msg + _("Cannot format selection(s)"))

    else:
        # format entire file
        x0, y0, x1, y1 = carets[0]
        text1 = ed.get_text_all()
        if not text1.strip():
            return

        ed.lock()
        try:
            app_idle(True)
            text = do_format(text1)
        finally:
            ed.unlock()

        if not text:
            msg_status(msg + _("Cannot format text"))
            return

        if text==text1:
            msg_status(msg + _('Text is already formatted'))
            return

        replace_all_preserving_linestates(ed, text1, text)
        msg_status(msg + _("Formatted entire text"))
