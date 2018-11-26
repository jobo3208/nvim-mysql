# nvim-mysql

nvim-mysql is a plugin for Neovim that allows you to run MySQL queries
from the editor asynchronously. This means you can run a query, continue
working, and have the results shown to you as soon as the query is
finished. In this way, nvim-mysql is like a simpler, editor-based version
of MySQL Workbench/Navicat/HeidiSQL/etc.

nvim-mysql is under development and should be considered unstable.

## Usage

### Connecting and Running Queries

nvim-mysql uses a model of one database connection per tab.

To connect the current tab to a database, type

    :MySQLConnect <host>

Once connected, you can run the query under the cursor by hitting `Enter`
in normal mode. (Note that currently, queries must be separated by a blank
line for this to work.) This will run the query asynchronously,
immediately returning control to the editor while the query executes. Once
the query is done, a results window will be displayed. Press `R` to jump
to the results window. You can quickly close the results window by
pressing `q`.

If a query is taking too long, you can press `K` is normal mode to kill
it. Note that you can currently only run one query at a time per tab.

### Autocomplete

nvim-mysql can autocomplete table and column names. Use `Ctrl-X Ctrl-U` to
autocomplete.

## Installation

nvim-mysql is a Python 3 remote plugin for Neovim -- Python 2 is not
supported.

The easiest way to install is using
[vim-pathogen](https://github.com/tpope/vim-pathogen):

    $ cd ~/.vim/bundle
    $ git clone https://github.com/jobo3208/nvim-mysql
    $ cd nvim-mysql
    $ pip3 install -r requirements.txt

Then start `nvim` and run `:UpdateRemotePlugins`.

You may also want to add the keybindings from `script/vimrc` to your
personal `vimrc`.

## Development

When developing nvim-mysql, be sure to use the provided `vimrc` file:

    $ nvim -u script/vimrc

This will cause Neovim to use the plugin code in your current directory.

You can also use [tmuxinator](https://github.com/tmuxinator/tmuxinator)
with the provided `.tmuxinator.yml` file. This will give you a Neovim
editor in the first tab with logs, and a Neovim editor in the second tab
with a connected IPython shell (useful for experimenting with the API).
