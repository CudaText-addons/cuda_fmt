Plugin for CudaText.
Framework to use code formatters. Formatters are Python functions which change entire file text or only selected text. Formatters are distributed as separate 2nd-level plugins, which are called via this framework. This approach is like CudaLint and its linters.

All existing plugins like "JS Format", "Python ReIndent", "SQL Format", "CSS Minifier" will be converted to such formatters.

Plugin gives commands in Plugins menu:
- Format: Runs formatter for current editor file. If several formatters are found, menu dialog will suggest to choose one of them.
- Configure formatter: For those formatters which support config file, command will suggest to open global config file (in the folder "settings" of CudaText).
- Configure formatter (local): For those formatters which suppots config file, command will suggest to open "local config" (in the folder of current editor file). If local file not exists, plugin will suggest to create it from global config.

To see how to write formatters, install "Formatters for JavaScript" which has most of features.

Author: Alexey Torgashin (CudaText)
License: MIT
