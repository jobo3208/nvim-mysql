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

    :MySQLConnect <target>

`<target>` can be a hostname, connection string, or an alias defined in
the `g:nvim_mysql#aliases` map.

Once connected, you can run the query under the cursor by hitting
`<Leader>x` (`<Leader>` is typically backslash) in normal mode. (Note that
currently, queries must be separated by a blank line for this to work.)
This will run the query asynchronously, immediately returning control to
the editor while the query executes. Once the query is done, a results
window will be displayed. Press `R` to jump to the results window. You can
quickly close the results window by pressing `q`.

You can also sequentially run all queries in the currently selected range
by typing `<Leader>x` in visual mode.

If a query is taking too long, you can press `K` in normal mode to kill
it. Note that you can currently only run one query (or sequence of
queries) at a time per tab.

### Tree View

Press `T` to open a tree-view window. This view shows databases at
a glance. Press the spacebar to open/close databases and see the tables
inside.

### Autocomplete

nvim-mysql can autocomplete table and column names. Use `Ctrl-X Ctrl-U` to
autocomplete.

## Installation

nvim-mysql is a Python 3 remote plugin for Neovim. Currently Python 3.7+
is required. Python 2 is not supported.

The easiest way to install is using Neovim's built-in package support:

    $ mkdir -p ~/.local/share/nvim/site/pack/nvim-mysql/start
    $ cd !$
    $ git clone https://github.com/jobo3208/nvim-mysql
    $ cd nvim-mysql
    (recommended: create/activate virtualenv that Neovim will use)
    $ pip install -r requirements.txt

Then start Neovim, run `:UpdateRemotePlugins`, exit, and restart Neovim. The
plugin should now be ready for use.

## Development

When developing nvim-mysql, be sure to use the provided `vimrc` file:

    $ nvim -u script/vimrc

This will cause Neovim to use the plugin code in your current directory.

You can also use [tmuxinator](https://github.com/tmuxinator/tmuxinator)
with the provided `.tmuxinator.yml` file. This will give you a Neovim
editor in the first tab with logs, and a Neovim editor in the second tab
with a connected IPython shell (useful for experimenting with the API).

## Tests

Run the tests with `pytest`.
