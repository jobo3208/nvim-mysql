# Core

  - [ ] Reconnect if connection is lost

  - [x] Make keybindings customizable
  - [x] Support connection strings
  - [x] Allow connection presets in vimrc
  
# Features

  - [ ] Support Home and End keys in autocomplete menu
  - [ ] Shortcuts (e.g. copy a table) (maybe better implemented as snippets?)
  - [ ] Query log
  - [ ] Add more objects to tree view (views, functions, triggers, etc.)

  - [x] When autocompleting a name with spaces in it, wrap in backticks
  - [x] Raw view of a single data point
  - [x] Database tree view
  - [x] Allow running a series of queries
  - [x] Change format of results buffer (ASCII table, CSV, etc.)
  - [x] Shortcuts for describing and sampling a table
  - [x] Freeze panes in results buffer
  - [x] Shortcut for counting a table
  - [x] Auto-close results window if last window in tab
  - [x] More query metadata in results buffer (e.g. execution time,
    dimensions of result set)

# Meta

  - [ ] Walk through code to make sure we are doing everything correctly
      - [ ] Make sure we're running queries in idiomatic way
  - [ ] Documentation
  - [ ] Write tests
  - [ ] (possible role model: https://github.com/numirias/semshi)

  - [x] Use pynvim package instead of neovim (shouldn't be hard, I think
    they're identical)
  - [x] Migrate to python3
      - [x] Make sure we are using bytes/str correctly
  - [x] Iron out logging (ours and nvim's -- where do they go and how do we
    control them?)
  - [x] Simplify installation

# Bugs

  - [ ] Visual selection is lost if MySQLShowResults is called during
  - [ ] Tree view: make unmodifiable by user (but obviously *we* need to be
    able to modify it)

  - [x] Keybindings should be limited to MySQL-connected buffers
  - [x] Tree view: infer database from position in tree when doing a describe,
    count, sample, etc. on a table
  - [x] When closing aux window, go back to previous window
  - [x] Tree view: when running a command on a table in the tree view, the
    results window should not be confined to the tree view window. It
    should use the "main" results window.
  - [x] Second nvim instance freezes when trying to MySQLConnect
  - [x] Can't MySQLConnect if buffer has been modified
  - [x] In results buffer, PgUp and PgDn go back to the start of the line
  - [x] In results buffer, cursor position doesn't reset when new query
    runs
  - [x] Autocomplete is case-insensitive for text you've already typed, but
    is case-sensitive for text entered after autocompletion has begun. It
    should be case-insensitive for both.
  - [x] Connection and results buffer should be closed/removed when tabpage
    is closed
  - [x] Results buffer gets messed up if autochdir option is on
  - [x] Autocomplete fails if column alias is preceded by '(' (as in a function
    call)
  - [x] Tabs get messed up when you close a tab between two MySQL tabs
  - [x] Tab becomes MySQL-enabled even if connection to database fails
  - [x] Can't sample or describe table name in backticks
  - [x] If you MySQLConnect from the results buffer (e.g. if connection expires),
    it will set ft=mysql
  - [x] Custom tabline appears to remove/hide modified flag
  - [x] MySQLExecQueryUnderCursor on a blank line runs nearby query
  - [x] Binary values are wrapped in b'' in CSV output

# Tests

  - [ ] Does it handle non-ASCII characters?
  - [ ] How do we handle errors and warnings?
  - [ ] How do we close connections? Gracefully?
  - [ ] Does the plugin wait for the user to activate it before using any
    resources?
  - [ ] Confirm that new buffers in MySQL-enabled tabs work just like the
    first buffer
