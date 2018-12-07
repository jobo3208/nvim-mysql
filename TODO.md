# Core

  - Support connection strings
      - Allow presets in vimrc
  - Make keybindings customizable
  - Reconnect if connection is lost
  
# Features

  - Freeze panes in results buffer
  - Smoother autocomplete experience
      - Support Home and End keys in autocomplete menu
      - Choose top option by default?
      - Change search direction for autocomplete?
  - Allow running a series of queries
  - Shortcuts (e.g. copy a table) (maybe better implemented as snippets?)

  - ~~Change format of results buffer (ASCII table, CSV, etc.)~~

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
  - Custom tabline appears to remove/hide modified flag

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

# Tests

  - Does it handle non-ASCII characters?
  - How do we handle errors and warnings?
  - How do we close connections? Gracefully?
  - Does the plugin wait for the user to activate it before using any
    resources?
  - Confirm that new buffers in MySQL-enabled tabs work just like the
    first buffer
