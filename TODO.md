# Core

  - Support connection strings
      - Allow presets in vimrc
  - Make keybindings customizable
  - Reconnect if connection is lost
  
# Features

  - Change format of results buffer (ASCII table, CSV, etc.)
  - Freeze panes in results buffer
  - Smoother autocomplete experience
      - Support Home and End keys in autocomplete menu
      - Choose top option by default?
      - Change search direction for autocomplete?
  - Allow running a series of queries
  - Shortcuts (e.g. copy a table) (maybe better implemented as snippets?)

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

# Tests

  - Does it handle non-ASCII characters?
  - How do we handle errors and warnings?
  - How do we close connections? Gracefully?
  - Does the plugin wait for the user to activate it before using any
    resources?
  - Confirm that new buffers in MySQL-enabled tabs work just like the
    first buffer
