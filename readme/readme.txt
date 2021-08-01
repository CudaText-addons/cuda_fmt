Framework to use code formatters in CudaText. Formatters are Python functions
which change entire file text or only selected text.
Formatters are distributed as separate 2nd-level plugins, which are called
via this framework. This approach is like CudaLint and its linters.

Commands in the Plugins menu
----------------------------

- Formatter (menu):
  Runs formatter for current editor file. If several formatters are found,
  menu dialog will suggest to choose one of them.

- Formatter per-lexer A...D:
  Runs formatter for current editor file, which has label (A, B, C, D) set.
  Labels are configurable by another command.

- Formatter cross-lexer 1...4:
  Runs formatter for current editor file, which has label (1, 2, 3, 4) set.
  Labels are configurable by another command.

- Configure per-lexer labels:
  Allows to assign labels (A, B, C, D) to formatters. Labels allow to use commands
  "Formatter A"..."Formatter D", e.g. via hotkeys. So you can use command
  "Formatter A" via some hotkey, and be sure that for all lexers "Formatter A"
  will use desired formatters.

- Configure cross-lexer labels:
  Similar to previous item, but for cross-lexer labels (1, 2, 3, 4). For example,
  if formatter "XML Tidy" has the cross-lexer label "2", then calling
  of formatter "2" will always run "XML Tidy", ignoring the current lexer.

- Configure on_save:
  Chooses which formatters are active on file saving. The first formatter,
  which is suitable for current lexer, and has the flag "on_save",
  will be used to format text on file saving.

- Configure formatter:
  For those formatters which support config file, command will suggest
  to open global config file (in the folder "settings" of CudaText).

- Configure formatter (local):
  For those formatters which suppots config file, command will suggest to open
  "local" config (in the folder of current editor file). If local config
  not exists, plugin will suggest to create it from global config.

Docs
----
No docs yet.
To see how to write formatters, install "Formatters for JavaScript"
which has most of features.


Author: Alexey Torgashin (CudaText)
License: MIT
