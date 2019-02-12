# Core

  - Make keybindings customizable
  - Reconnect if connection is lost

  - ~~Support connection strings~~
  - ~~Allow connection presets in vimrc~~
  
# Features

  - Support Home and End keys in autocomplete menu
  - Allow running a series of queries
  - Shortcuts (e.g. copy a table) (maybe better implemented as snippets?)
  - When autocompleting a name with spaces in it, wrap in backticks
  - Query log

  - ~~Change format of results buffer (ASCII table, CSV, etc.)~~
  - ~~Shortcuts for describing and sampling a table~~
  - ~~Freeze panes in results buffer~~
  - ~~Shortcut for counting a table~~
  - ~~Auto-close results window if last window in tab~~
  - ~~More query metadata in results buffer (e.g. execution time,
    dimensions of result set)~~

# Meta

  - Walk through code to make sure we are doing everything correctly
      - Make sure we're running queries in idiomatic way
  - Documentation
  - Write tests
  - (possible role model: https://github.com/numirias/semshi)

  - ~~Use pynvim package instead of neovim (shouldn't be hard, I think
    they're identical)~~
  - ~~Migrate to python3~~
      - ~~Make sure we are using bytes/str correctly~~
  - ~~Iron out logging (ours and nvim's -- where do they go and how do we
    control them?)~~
  - ~~Simplify installation~~

# Bugs

  - Keybindings should be limited to MySQL-connected buffers
  - Visual selection is lost if MySQLShowResults is called during

  - ~~Second nvim instance freezes when trying to MySQLConnect~~
  - ~~Can't MySQLConnect if buffer has been modified~~
  - ~~In results buffer, PgUp and PgDn go back to the start of the line~~
  - ~~In results buffer, cursor position doesn't reset when new query
    runs~~
  - ~~Autocomplete is case-insensitive for text you've already typed, but
    is case-sensitive for text entered after autocompletion has begun. It
    should be case-insensitive for both.~~
  - ~~Connection and results buffer should be closed/removed when tabpage
    is closed~~
  - ~~Results buffer gets messed up if autochdir option is on~~
  - ~~Autocomplete fails if column alias is preceded by '(' (as in a function
    call)~~
  - ~~Tabs get messed up when you close a tab between two MySQL tabs~~
  - ~~Tab becomes MySQL-enabled even if connection to database fails~~
  - ~~Can't sample or describe table name in backticks~~
  - ~~If you MySQLConnect from the results buffer (e.g. if connection expires),
    it will set ft=mysql~~
  - ~~Custom tabline appears to remove/hide modified flag~~
  - ~~MySQLExecQueryUnderCursor on a blank line runs nearby query~~
  - ~~Binary values are wrapped in b'' in CSV output~~

# Tests

  - Does it handle non-ASCII characters?
  - How do we handle errors and warnings?
  - How do we close connections? Gracefully?
  - Does the plugin wait for the user to activate it before using any
    resources?
  - Confirm that new buffers in MySQL-enabled tabs work just like the
    first buffer
