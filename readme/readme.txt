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
  These are per-lexer labels, ie you can have formatter for label 'B' in C++,
  and another formatter for 'B' in XML, and another one for JSON.

- Formatter cross-lexer 1...4:
  Runs formatter for current editor file, which has label (1, 2, 3, 4) set.
  These are cross-lexer labels, ie they ignore the current lexer.

- Minify to separate file:
  Runs the 'minifier', and puts its output to a separate file
  filename.min.js (example for JavaScript). The ".min" is inserted to get
  the new filename.
  What is 'minifier' here? It is a usual formatter, which is marked in the
  formatter's install.inf file, by line "minifier=1".

- Configure per-lexer labels:
  Allows to assign labels A, B, C, D. Labels allow to use commands
  "Formatter per-lexer A" ... "Formatter per-lexer D" (e.g. via hotkeys).
  These are per-lexer labels, ie you can have formatter 'A' for C++,
  and another formatter 'A' for XML, and another formatter 'A' for JSON.

- Configure cross-lexer labels:
  Similar to previous item, but for cross-lexer labels 1, 2, 3, 4.
  For example, if formatter "XML Tidy" has the cross-lexer label "2",
  then running formatter "2" will always run "XML Tidy", ignoring
  the current lexer, ignoring the file type.

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
