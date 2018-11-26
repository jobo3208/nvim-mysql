# Core

  - Support connection strings
      - Allow presets in vimrc
  - Make keybindings customizable
  
# Features

  - Change format of results buffer (ASCII table, CSV, etc.)
  - Freeze panes in results buffer

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

  - ~~Second nvim instance freezes when trying to MySQLConnect~~

# Tests

  - Does it handle non-ASCII characters?
  - How do we handle errors and warnings?
  - How do we close connections? Gracefully?
  - Does the plugin wait for the user to activate it before using any
    resources?
