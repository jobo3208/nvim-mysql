# -*- coding: utf-8 -*-

import csv
import io
import logging
import os
import threading
import time

import cxnstr
import greenlet
import pymysql
import pymysql.constants.FIELD_TYPE as FT
import pynvim
import six

import nvim_mysql.autocomplete
import nvim_mysql.util


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

NUMERIC_TYPES = [
    FT.DECIMAL,
    FT.TINY,
    FT.SHORT,
    FT.LONG,
    FT.FLOAT,
    FT.DOUBLE,
    FT.LONGLONG,
    FT.INT24,
    FT.NEWDECIMAL,
]

DATE_TYPES = [
    FT.TIMESTAMP,
    FT.DATE,
    FT.TIME,
    FT.DATETIME,
    FT.YEAR,
    FT.NEWDATE,
]

OPTION_DEFAULTS = {
    'aliases': None,
    'auto_close_results': 0,
    'aux_window_pref': 'results',
    'use_spinner': 1,
}

KEYMAPS = {
    'MySQLExecQueryUnderCursor': {'buffers': ['query'], 'mode': 'n', 'key': '<leader>x'},
    'MySQLExecQueriesInRange': {'buffers': ['query'], 'mode': 'v', 'key': '<leader>x'},
    'MySQLCountTableUnderCursor': {'buffers': ['query', 'tree'], 'mode': 'n', 'key': '<leader>c'},
    'MySQLShowCreateTableFromTableUnderCursor': {'buffers': ['query', 'tree'], 'mode': 'n', 'key': '<leader>C'},
    'MySQLDescribeTableUnderCursor': {'buffers': ['query', 'tree'], 'mode': 'n', 'key': '<leader>d'},
    'MySQLShowIndexesFromTableUnderCursor': {'buffers': ['query', 'tree'], 'mode': 'n', 'key': '<leader>i'},
    'MySQLSampleTableUnderCursor': {'buffers': ['query', 'tree'], 'mode': 'n', 'key': '<leader>s'},
    'MySQLSelectAllFromTableUnderCursor': {'buffers': ['query', 'tree'], 'mode': 'n', 'key': '<leader>S'},
    'MySQLShowResults': {'buffers': ['query', 'results', 'tree'], 'mode': 'n', 'key': 'R'},
    'MySQLShowTree': {'buffers': ['query', 'results', 'tree'], 'mode': 'n', 'key': 'T'},
    'MySQLKillQuery': {'buffers': ['query', 'results', 'tree'], 'mode': 'n', 'key': 'K'},

    'MySQLShowResults csv': {'buffers': ['results'], 'mode': 'n', 'key': '<leader>c'},
    'MySQLShowResults raw_column': {'buffers': ['results'], 'mode': 'n', 'key': '<leader>1'},
    'MySQLShowResults table': {'buffers': ['results'], 'mode': 'n', 'key': '<leader>t'},
    'MySQLShowResults vertical': {'buffers': ['results'], 'mode': 'n', 'key': '<leader>G'},
    'MySQLFreezeResultsHeader': {'buffers': ['results'], 'mode': 'n', 'key': '<leader>f'},

    'MySQLTreeToggleDatabase': {'buffers': ['tree'], 'mode': 'n', 'key': '<space>'},
}

SPINNER_CHARS = u"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class NvimMySQLError(Exception):
    pass


def _reconnect_on_failure(db, f, *args, **kwargs):
    """Run f(*args, **kwargs). If the call fails due to the connection having
    been lost, reconnect to db, then try again."""
    try:
        return f(*args, **kwargs)
    except pymysql.err.OperationalError as e:
        if e.args[0] in [2006, 2013]:
            logger.warning("disconnected! trying to reconnect...")
            db.connect()
            logger.warning("successfully reconnected!")
            return f(*args, **kwargs)
        else:
            raise


class ReconnectingCursor(pymysql.cursors.Cursor):
    """A cursor whose execute and executemany methods automatically try to
    reconnect to the db if the connection has been lost."""
    def execute(self, *args, **kwargs):
        return _reconnect_on_failure(self.connection, super(ReconnectingCursor, self).execute, *args, **kwargs)

    def executemany(self, *args, **kwargs):
        return _reconnect_on_failure(self.connection, super(ReconnectingCursor, self).executemany, *args, **kwargs)


def render_map_command(command_name, vim=None):
    """
    >>> render_map_command('MySQLKillQuery')
    'nnoremap <buffer> K :MySQLKillQuery<cr>'
    """
    keymap_data = KEYMAPS[command_name].copy()
    if vim:
        user_keymaps = vim.vars.get('nvim_mysql#keymaps')
        if user_keymaps and command_name in user_keymaps:
            keymap_data['key'] = user_keymaps[command_name]
    return "{mode}noremap <buffer> {key} :{command_name}<cr>".format(command_name=command_name, **keymap_data)


def render_map_commands_for_buffer_type(buffer_type, vim=None):
    return [render_map_command(c, vim) for c, k in KEYMAPS.items() if buffer_type in k['buffers']]


def prepend_type_hints_to_header(header, types):
    for i, t in enumerate(types):
        if t in NUMERIC_TYPES:
            header[i] = '#' + header[i]
        elif t in DATE_TYPES:
            header[i] = '@' + header[i]


def display_value(v):
    """Return the value to display for one particular cell/value."""
    if v is None:
        v = u'NULL'
    elif isinstance(v, bytes):
        try:
            v = v.decode('utf-8')
            v = ' '.join(v.splitlines())
        except UnicodeDecodeError:
            if six.PY3:
                v = '0x' + v.hex()
            else:
                v = '0x' + v.encode('hex')
    else:
        v = six.text_type(v)
        v = ' '.join(v.splitlines())
    return v


def results_to_table(header, rows, types=None):
    """Format query result set as an ASCII table.

    If a list of field types is provided (from cursor.description), type hints
    will be added to the headers.

    Return a list of strings.
    """
    header = header[:]
    if types:
        prepend_type_hints_to_header(header, types)

    col_lengths = [max([len(display_value(r)) for r in col]) for col in zip(header, *rows)]

    # Table elements.
    horizontal_bar = '+' + '+'.join(['-' * (l + 2) for l in col_lengths]) + '+'
    def table_row(row):
        # Return a database row formatted as a table row.
        return '|' + '|'.join(
            [u' {:{}} '.format(display_value(v), l) for v, l in zip(row, col_lengths)]) + '|'

    return [
        horizontal_bar,
        table_row(header),
        horizontal_bar,
    ] + [table_row(r) for r in rows] + [
        horizontal_bar
    ]


def results_to_vertical(header, rows, types=None):
    """Format query result set as a series of field: value lines.

    Each row will span len(row) lines.

    If a list of field types is provided (from cursor.description), type hints
    will be added to the headers.

    Return a list of strings.
    """
    header = header[:]
    if types:
        prepend_type_hints_to_header(header, types)

    header_lengths = [len(h) for h in header]
    max_header_length = max(header_lengths)
    header_strs = ['{{:>{}}}'.format(max_header_length + 1).format(header[i]) for i in range(len(header))]

    output = []
    for i, row in enumerate(rows, 1):
        if len(rows) > 1:
            output.append('***** row {} *****'.format(i))

        for j, v in enumerate(row):
            output.append('{}: {}'.format(header_strs[j], display_value(v)))

        if len(rows) > 1 and i < len(rows):
            output.append('')

    return output


def results_to_csv(header, rows):
    """Format query result set as a CSV file.

    Note that CSV is a text format, so binary data that is not valid utf-8 will
    cause an error.
    """
    # In Python 2, the csv module can't accept unicode, so we have to give it UTF-8.
    # In Python 3, the csv module accepts unicode.
    def output_value(v):
        if six.PY3:
            if isinstance(v, bytes):
                return v.decode('utf-8')
        else:
            if isinstance(v, unicode):
                return v.encode('utf-8')
        return v

    f = six.StringIO()
    csv_out = csv.writer(f)
    csv_out.writerow([output_value(v) for v in header])
    for row in rows:
        csv_out.writerow([output_value(v) for v in row])
    return f.getvalue().splitlines()


def format_results(results, format_='table', metadata=None):
    if metadata is None:
        metadata = {}

    if results['type'] == 'read':
        if format_ == 'table':
            lines = results_to_table(results['header'], results['rows'], results['types'])
            lines.extend(["", "{} row(s) in set, {} col(s)".format(results['count'], len(results['header']))])
        elif format_ == 'csv':
            lines = results_to_csv(results['header'], results['rows'])
        elif format_ == 'raw_column':
            lines = '\n'.join([str(r[0]) for r in results['rows']]).splitlines()
        elif format_ == 'vertical':
            lines = results_to_vertical(results['header'], results['rows'], results['types'])
        else:
            raise ValueError("Invalid results format '{}'".format(format_))
    elif results['type'] == 'write':
        lines = ["", "{} row(s) affected".format(results['count'])]
    elif results['type'] == 'error':
        lines = results['message'].splitlines()

    if format_ == 'table':
        duration = metadata.get('duration')
        if duration is not None and results['type'] in ['read', 'write']:
            lines[-1] += " ({:.2f} sec)".format(duration)

        warnings = results.get('warnings')
        if warnings:
            lines.extend(['', '[warnings]:'])
            for warning in warnings:
                lines.append("({}) {}".format(warning[1], warning[2]))

        query = metadata.get('query')
        if query is not None:
            lines.extend(['', '---', ''] + query.splitlines())

    return lines


class MySQLTab(object):
    """Represents a MySQL-connected tabpage.

    Each tab has one (primary) connection to a single server.
    """
    AUTOID = 1

    def __init__(self, mysql, vim, tabpage):
        self.vim = vim
        self.mysql = mysql
        self.tabpage = tabpage
        self.autoid = MySQLTab.AUTOID; MySQLTab.AUTOID += 1
        self.conn = None
        self.connection_string = None
        self.server_name = None
        self.status = {
            'executing': False,
            'killing': False,
            'results_pending': False,
        }
        self.results = None
        self.query = None
        self.query_start = None
        self.query_end = None
        self.results_buffer = self._initialize_results_buffer()
        self.results_format = None
        self.tree = Tree(self)
        self.tree_buffer = self._initialize_tree_buffer()

    def _initialize_results_buffer(self):
        cur_buf = self.vim.current.buffer

        # Create
        buf_name = "Results{}".format(self.autoid)
        self.vim.command("badd {}".format(buf_name))

        # Set up
        results_buffer = list(self.vim.buffers)[-1]
        self.vim.command("b! {}".format(results_buffer.number))
        self.vim.command("setl buftype=nofile bufhidden=hide nowrap nonu noswapfile nostartofline")
        self.vim.command("nnoremap <buffer> <S-Left> zH")
        self.vim.command("nnoremap <buffer> <S-Right> zL")
        # close window and go to previous
        self.vim.command("nnoremap <buffer> <silent> q :let nr = winnr() <Bar> :wincmd p <Bar> :exe nr . \"wincmd c\"<CR>")
        for map_command in render_map_commands_for_buffer_type('results', self.vim):
            self.vim.command(map_command)

        # Switch back
        self.vim.command("b! {}".format(cur_buf.number))

        return results_buffer

    def _initialize_tree_buffer(self):
        cur_buf = self.vim.current.buffer

        # Create
        buf_name = "Tree{}".format(self.autoid)
        self.vim.command("badd {}".format(buf_name))

        # Set up
        tree_buffer = list(self.vim.buffers)[-1]
        self.vim.command("b! {}".format(tree_buffer.number))
        self.vim.command("setl buftype=nofile bufhidden=hide nowrap nonu noswapfile")
        self.vim.command("nnoremap <buffer> <silent> q :let nr = winnr() <Bar> :wincmd p <Bar> :exe nr . \"wincmd c\"<CR>")
        for map_command in render_map_commands_for_buffer_type('tree', self.vim):
            self.vim.command(map_command)
        self.vim.command("syn match Directory /^[^ ].*/")

        # Switch back
        self.vim.command("b! {}".format(cur_buf.number))

        return tree_buffer

    def set_connection(self, conn, connection_string, server_name):
        """Set this MySQL tab's database connection to conn."""
        if self.conn:
            self.conn.close()
        self.conn = conn
        self.connection_string = connection_string
        self.server_name = server_name
        self.tabpage.vars['MySQLServer'] = server_name

        self.tree = Tree(self)
        self.tree.refresh_data()
        self.tree_buffer[:] = self.tree.render()

    def update_status(self, **kwargs):
        """Set one or more status flags for this tab.

        Use keyword arguments to do this. Example:

            self.update_status(executing=False, results_pending=True)
        """
        for k, v in kwargs.items():
            if k not in self.status:
                raise KeyError
            self.status[k] = v

        # In case multiple flags are set, the first listed below is the one
        # that shows in vim.
        status_flag = ''
        if self.status['killing']:
            status_flag = 'k'
        elif self.status['executing']:
            status_flag = 'e'
        elif self.status['results_pending']:
            status_flag = 'r'
        logger.debug("status flag: {}".format(status_flag))
        self.tabpage.vars['MySQLStatusFlag'] = status_flag

        self.mysql.refresh_tabline()

    def execute_queries(self, queries, combine_results):
        """Sequentially execute the given queries in this tab.

        If there is an error, execution will stop and the error will be
        displayed.

        Assuming all queries succeed, if combine_results is True,
        aggregate counts will be shown after the last query. (Note that
        these counts pertain only to "write" queries.) If
        combine_results is False, the results of the last query are
        shown.
        """
        # Ignore if a query is already running.
        if self.status['executing']:
            return

        gr = greenlet.getcurrent()
        cursor = self.conn.cursor()

        def query_done():
            logger.debug("query_done called")
            gr.parent = greenlet.getcurrent()
            gr.switch()

        def run_query(query, result):
            logger.debug("run_query called")
            try:
                cursor.execute(query)
                result['description'] = cursor.description
                result['rowcount'] = cursor.rowcount
                result['rows'] = cursor.fetchall()

                cursor.execute("show warnings")
                result['warnings'] = cursor.fetchall()
            except Exception as e:
                result['error'] = "Error: " + repr(e)
            else:
                result['error'] = None

            self.vim.async_call(query_done)

        if combine_results:
            self.query = ''
            self.results = {'type': 'write', 'count': 0, 'warnings': []}

        self.update_status(executing=True)
        self.query_start = time.time()
        for query in queries:
            if combine_results:
                if self.query:
                    self.query += '\n\n'
                self.query += query
            else:
                self.query = query

            query_result = {}

            logger.debug("executing query: {}".format(query))
            threading.Thread(target=run_query, args=[query, query_result]).start()
            gr.parent.switch()

            # Query is done.
            if query_result['error']:
                self.results = {'type': 'error', 'message': query_result['error']}
                break

            if combine_results:
                # for "write" queries, add to count
                if not query_result['description']:
                    self.results['count'] += query_result['rowcount']
                self.results['warnings'].extend(query_result['warnings'])
            else:
                if not query_result['description']:
                    self.results = {
                        'type': 'write',
                        'count': query_result['rowcount'],
                        'warnings': query_result['warnings'],
                    }
                else:
                    header = [f[0] for f in query_result['description']]
                    types = [f[1] for f in query_result['description']]
                    rows = query_result['rows']
                    self.results = {
                        'type': 'read',
                        'header': header,
                        'types': types,
                        'rows': rows,
                        'count': query_result['rowcount'],
                        'warnings': query_result['warnings'],
                    }

        self.query_end = time.time()
        cursor.close()
        self.update_status(executing=False, killing=False)

        # TODO: Differentiate results pending from error pending?
        self.update_status(results_pending=True)

        self.vim.command('MySQLShowResults table {}'.format(self.autoid))

    def execute_query(self, query):
        """Execute the given query in this tab.

        Results will be displayed if appropriate when the query finishes.
        """
        self.execute_queries([query], False)

    def complete(self, findstart, base):
        create_new_conn = self.status['executing']
        if create_new_conn:
            logger.debug("query is executing, so creating new connection for autocomplete")
            db_params = cxnstr.to_dict(self.connection_string)
            conn = pymysql.connect(use_unicode=True, **db_params)
        else:
            logger.debug("using existing connection for autocomplete")
            conn = self.conn

        result = nvim_mysql.autocomplete.complete(findstart, base, self.vim, conn.cursor())

        if create_new_conn:
            logger.debug("closing autocomplete connection")
            conn.close()

        return result

    def get_aux_window(self, target):
        target_buffer = self.results_buffer if target == 'results' else self.tree_buffer
        for window in self.vim.current.tabpage.windows:
            if window.buffer == target_buffer:
                return window
        return None

    def get_results_window(self):
        return self.get_aux_window('results')

    def get_tree_window(self):
        return self.get_aux_window('tree')

    def open_aux_window(self, target):
        # If target window is already open, jump to it.
        target_window = self.get_aux_window(target)
        if target_window is not None:
            logger.debug("{} window is already open in this tab".format(target))
            self.vim.command('{}wincmd w'.format(target_window.number))
            return

        # If not, open it.

        # First, check to see if we'll need to give the other window precedence.
        other = 'tree' if target == 'results' else 'results'
        other_window = self.get_aux_window(other)
        reopen_other_window = other_window is not None and self.mysql.get_option('aux_window_pref') == other
        if reopen_other_window:
            # If so, close for now (then we'll re-open).
            self.vim.command("{}wincmd c".format(other_window.number))

        # Open target window.
        if target == 'results':
            result_win_height = int(self.vim.current.window.height * 0.35)
            split_command = "botright {} split".format(result_win_height)
        else:
            tree_win_width = int(self.vim.current.window.width * 0.17)
            split_command = "vertical topleft {} split".format(tree_win_width)

        logger.debug("split command: {}".format(split_command))
        self.vim.command(split_command)
        target_buffer = self.results_buffer if target == 'results' else self.tree_buffer
        self.vim.command("b! {}".format(target_buffer.number))

        if reopen_other_window:
            self.open_aux_window(other)
            # switch back to our window
            self.vim.command("{}wincmd w".format(self.get_aux_window(target).number))

    def open_results_window(self):
        self.open_aux_window('results')

    def open_tree_window(self):
        self.open_aux_window('tree')

    def close(self):
        try:
            self.conn.close()
        except:
            pass
        self.vim.command("bd! {}".format(self.results_buffer.number))
        self.vim.command("bd! {}".format(self.tree_buffer.number))


@pynvim.plugin
class MySQL(object):
    """Plugin interface to neovim."""
    def __init__(self, vim):
        self.vim = vim
        self.tabs = {}
        self.initialized = False
        logger.debug("plugin loaded by host")

    def get_option(self, name):
        return self.vim.vars.get('nvim_mysql#{}'.format(name), OPTION_DEFAULTS[name])

    @pynvim.command('MySQLConnect', nargs=1, sync=True)
    def connect(self, args):
        """Use the given connection_string to connect the current tabpage to a MySQL server."""
        target = args[0]
        aliases = self.get_option('aliases')
        if aliases is not None and target in aliases:
            logger.debug("'{}' is an alias for '{}'".format(target, aliases[target]))
            connection_string = aliases[target]
            server_name = target
        else:
            connection_string = target
            server_name = None
        db_params = cxnstr.to_dict(connection_string)
        if server_name is None:
            server_name = db_params['host']
        logger.debug("connecting to {}".format(connection_string))
        conn = pymysql.connect(use_unicode=True, cursorclass=ReconnectingCursor, **db_params)
        conn.autocommit(True)
        logger.debug("connection succeeded")

        tabpage = self.vim.current.tabpage
        if tabpage in self.tabs:
            logger.debug("this tab is already MySQL-connected, will replace connection")
            tab = self.tabs[tabpage]
        else:
            logger.debug("this tab is not MySQL-connected, will initialize")
            tab = self.tabs[tabpage] = MySQLTab(self, self.vim, tabpage)
        tab.set_connection(conn, connection_string, server_name)

        if self.vim.current.buffer.name == '' and 'current_syntax' not in self.vim.current.buffer.vars:
            self.vim.command('set ft=mysql')

        if not self.initialized:
            self._initialize()

        self.refresh_tabline()

    @pynvim.command('MySQLExecQueryUnderCursor', sync=False)
    def exec_query_under_cursor(self):
        """Execute the query under the cursor.

        This command assumes that all queries are separated by at least one
        blank line.
        """
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        query, _ = nvim_mysql.util.get_query_under_cursor(
            self.vim.current.buffer,
            self.vim.current.window.cursor[0] - 1,
            self.vim.current.window.cursor[1]
        )
        if query is not None:
            current_tab.execute_query(query)

    @pynvim.command('MySQLExecQueriesInRange', range='', sync=False)
    def exec_queries_in_range(self, range):
        """Execute the queries in the visual selection.

        Results of individual queries are not shown.

        This command assumes that all queries are separated by at least one
        blank line.
        """
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        queries = nvim_mysql.util.get_queries_in_range(self.vim.current.buffer, range[0] - 1, range[1] - 1)
        current_tab.execute_queries(queries, len(queries) > 1)

    def _run_query_on_table_under_cursor(self, query_fmt):
        """Run a query on the table under the cursor."""
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        # Special handling for tables in the tree buffer.
        if self.vim.current.buffer == current_tab.tree_buffer:
            # Ignore if we're on a database row.
            if not self.vim.current.line.startswith(' '):
                return
            table = self.vim.current.line.strip()
            database, _, _ = nvim_mysql.util.get_parent_database_in_tree(
                self.vim.current.buffer,
                self.vim.current.window.cursor[0] - 1
            )
            table = database + '.' + table
        else:
            word = nvim_mysql.util.get_word_under_cursor(
                self.vim.current.buffer,
                self.vim.current.window.cursor[0] - 1,
                self.vim.current.window.cursor[1]
            )
            table = nvim_mysql.util.word_to_table(word)

        if nvim_mysql.util.table_exists(current_tab.conn, table):
            query = query_fmt.format(table)
            current_tab.execute_query(query)
        else:
            raise NvimMySQLError("Table '{}' does not exist".format(table))

    @pynvim.command('MySQLDescribeTableUnderCursor', sync=False)
    def describe_table_under_cursor(self):
        """Describe the table under the cursor."""
        self._run_query_on_table_under_cursor("describe {}")

    @pynvim.command('MySQLShowIndexesFromTableUnderCursor', sync=False)
    def show_indexes_from_table_under_cursor(self):
        """Show indexes from the table under the cursor."""
        self._run_query_on_table_under_cursor("show indexes from {}")

    @pynvim.command('MySQLShowCreateTableFromTableUnderCursor', sync=False)
    def show_create_table_from_table_under_cursor(self):
        """Show create table from the table under the cursor."""
        self._run_query_on_table_under_cursor("show create table {}")

    @pynvim.command('MySQLSampleTableUnderCursor', sync=False)
    def sample_table_under_cursor(self):
        """Select a sampling of rows from the table under the cursor."""
        self._run_query_on_table_under_cursor("select * from {} limit 100")

    @pynvim.command('MySQLSelectAllFromTableUnderCursor', sync=False)
    def select_all_from_table_under_cursor(self):
        """Select all rows from the table under the cursor."""
        self._run_query_on_table_under_cursor("select * from {}")

    @pynvim.command('MySQLCountTableUnderCursor', sync=False)
    def count_table_under_cursor(self):
        """Select count(*) from the table under the cursor."""
        self._run_query_on_table_under_cursor("select count(*) from {}")

    @pynvim.command('MySQLKillQuery', sync=True)
    def kill_query(self):
        """Kill the query currently executing in the current tabpage.

        This command creates an additional connection to the server to
        kill the query.
        """
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        # If there's no running query, ignore.
        if not current_tab.status['executing']:
            raise NvimMySQLError("No query is currently running in this tab")

        current_tab.update_status(killing=True)
        query_id = current_tab.conn.thread_id()
        logger.debug("thread id: {}".format(query_id))

        db_params = cxnstr.to_dict(current_tab.connection_string)
        conn = pymysql.connect(use_unicode=True, **db_params)
        try:
            cursor = conn.cursor()
            cursor.execute("kill query {}".format(query_id))
        finally:
            conn.close()

        logger.debug("done killing query")

    @pynvim.command('MySQLShowResults', nargs='*', sync=True)
    def show_results(self, args):
        """Display the results buffer.

        :MySQLShowResults <format> <tab_autoid>

        Both arguments are optional, but format must be specified if tab_autoid
        is specified.

        format can be one of 'table' (the default), 'csv', or 'raw_column'.

        'table' is an ASCII table format, similar to the standard MySQL client.

        'csv' formats the result set as a CSV file.

        'raw_column' is a raw view of a single column (the first column, if the
        result set contains more than one). For a 1x1 result set, this format
        lets you see the raw data of a single data point, which can be helpful
        for long text fields and/or text fields with newlines. It's also useful
        for quickly extracting a list of field names from DESCRIBE output.

        If tab_autoid is specified, only show the results if we are currently
        in the MySQLTab with the given autoid. If tab_autoid is not specified,
        show the results no matter what.
        """
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        logger.debug("show_results args: {}".format(args))

        if len(args) > 1:
            tab_autoid = int(args[1])
        else:
            tab_autoid = None

        if len(args) > 0:
            format_ = args[0]
            if format_ not in ['table', 'csv', 'raw_column', 'vertical']:
                raise NvimMySQLError("Invalid results format '{}'".format(format_))
        else:
            format_ = 'table'

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            if tab_autoid is None:
                raise NvimMySQLError("This is not a MySQL-connected tabpage")
            else:
                return

        # If we were called with a specific tab number and we're not in
        # that tab, ignore.
        if tab_autoid is not None and tab_autoid != current_tab.autoid:
            return

        current_tab.open_results_window()

        if current_tab.query and (current_tab.status['results_pending'] or format_ != current_tab.results_format):
            metadata = {
                'query': current_tab.query,
                'duration': current_tab.query_end - current_tab.query_start,
            }
            current_tab.results_buffer[:] = format_results(current_tab.results, format_, metadata)
            current_tab.results_format = format_
            self.vim.command("normal gg0")

        current_tab.update_status(results_pending=False)

        # If this was done automatically, switch back to wherever the user was.
        if tab_autoid is not None:
            self.vim.command('wincmd p')

    @pynvim.command('MySQLFreezeResultsHeader', sync=True)
    def freeze_results_header(self):
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        if current_tab.results_buffer != self.vim.current.buffer:
            raise NvimMySQLError("This command can only be run in results buffer")

        self.vim.feedkeys("""gg^:=winheight('%')-4spL3jH^:se scbk:se scb:se sbo=horj""")

    @pynvim.command('MySQLShowTree', sync=True)
    def show_tree(self):
        """Display the tree buffer."""
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        current_tab.open_tree_window()

        current_tab.tree.refresh_data()
        current_tab.tree_buffer[:] = current_tab.tree.render()

    @pynvim.command('MySQLTreeToggleDatabase', sync=True)
    def tree_toggle_database(self):
        """Open or close the nearest database in the tree."""
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        if current_tab.tree_buffer != self.vim.current.buffer:
            raise NvimMySQLError("This command can only be run in tree buffer")

        database, expanded, row = nvim_mysql.util.get_parent_database_in_tree(
            self.vim.current.buffer,
            self.vim.current.window.cursor[0] - 1
        )
        if expanded:
            current_tab.tree.close(database)
        else:
            current_tab.tree.open(database)

        current_tab.tree.refresh_data()
        current_tab.tree_buffer[:] = current_tab.tree.render()
        self.vim.current.window.cursor = [row + 1, 0]

    @pynvim.function('MySQLComplete', sync=True)
    def complete(self, args):
        findstart, base = args

        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)

        # If this isn't a MySQL tab, ignore.
        if current_tab is None:
            return 0 if findstart else []

        return current_tab.complete(findstart, base)

    @pynvim.function('MySQLCleanupTabs', sync=True)
    def cleanup_tabs(self, args):
        if self.initialized:
            self._cleanup_tabs()

    def _cleanup_tabs(self):
        logger.debug("number of open tabs: {}".format(len(self.vim.tabpages)))
        for nvim_tab, mysql_tab in list(self.tabs.items()):
            if nvim_tab not in self.vim.tabpages:
                logger.debug("tab w/ handle {} is not longer open. closing.".format(nvim_tab.handle))
                mysql_tab.close()
                del self.tabs[nvim_tab]

    @pynvim.function('MySQLAutoCloseAuxWindows', sync=True)
    def auto_close_aux_windows(self, args):
        if self.initialized:
            def closeable(window):
                auto_close_results = bool(self.get_option('auto_close_results'))
                is_results_window = window.buffer == current_tab.results_buffer
                is_tree_window = window.buffer == current_tab.tree_buffer
                return (auto_close_results and is_results_window) or is_tree_window

            tabpage = self.vim.current.tabpage
            current_tab = self.tabs.get(tabpage, None)
            if current_tab is not None:
                if all(closeable(w) for w in tabpage.windows):
                    for _ in range(len(tabpage.windows)):
                        self.vim.command('q')

                    # We have to call this manually because the TabClosed
                    # autocommand doesn't appear to be called when using
                    # vim.command.
                    self._cleanup_tabs()

    @pynvim.function('MySQLInitializeQueryBuffer', sync=True)
    def initialize_query_buffer(self, args):
        self.vim.command('setlocal completefunc=MySQLComplete')
        for map_command in render_map_commands_for_buffer_type('query', self.vim):
            self.vim.command(map_command)

    def _initialize(self):
        logger.debug("initializing plugin")

        self.initialized = True
        tabline_file = os.path.join(os.path.dirname(__file__), 'tabline.vim')
        self.vim.command('source {}'.format(tabline_file))

        # Initialize all existing SQL buffers
        cur_buf = self.vim.current.buffer
        for buffer in self.vim.buffers:
            if buffer.options.get('filetype') in ['sql', 'mysql']:
                self.vim.command("buffer! {}".format(buffer.number))
                self.vim.command("call MySQLInitializeQueryBuffer()")
        self.vim.command("buffer! {}".format(cur_buf.number))

        # Set up autocommands
        self.vim.command('autocmd TabClosed * call MySQLCleanupTabs()')
        self.vim.command('autocmd WinEnter * call MySQLAutoCloseAuxWindows()')
        self.vim.command('autocmd FileType sql,mysql call MySQLInitializeQueryBuffer()')

        self.refresh_tabline()
        if self.get_option('use_spinner'):
            self.start_spinner()

        logger.debug("plugin initialized")


    def refresh_tabline(self, spinner_char=None):
        if spinner_char:
            self.vim.vars['nvim_mysql#spinner_char'] = spinner_char
        self.vim.command('set showtabline=2 tabline=%!MySQLTabLine()')

    def start_spinner(self):
        def spin():
            i = 0
            while True:
                i = i % len(SPINNER_CHARS)
                self.vim.async_call(self.refresh_tabline, SPINNER_CHARS[i])
                time.sleep(.1)
                i += 1
        t = threading.Thread(target=spin)
        t.daemon = True
        t.start()


class Tree(object):
    """Internal representation of tree view."""
    def __init__(self, tab):
        self.tab = tab
        self.data = {}  # {db: {expanded: bool, objects: [str]}}

    def refresh_data(self):
        cursor = self.tab.conn.cursor()
        cursor.execute("show databases")
        databases = [r[0] for r in cursor.fetchall()]

        # Remove databases that are no longer listed
        for database in self.data:
            if database not in databases:
                del self.data[database]

        # Add new databases
        for database in databases:
            if database not in self.data:
                self.data[database] = {'expanded': False, 'objects': []}

        # Update objects for expanded databases
        for database in self.data:
            if self.data[database]['expanded']:
                cursor.execute("show tables from {}".format(database))
                tables = [r[0] for r in cursor.fetchall()]
                self.data[database]['objects'] = tables

    def open(self, database):
        self.data[database]['expanded'] = True

    def close(self, database):
        self.data[database]['expanded'] = False

    def render(self):
        s = ''
        for database in sorted(self.data):
            s += database
            s += u' ▾' if self.data[database]['expanded'] else u' ▸'
            s += '\n'
            if self.data[database]['expanded']:
                s += '  ' + '\n  '.join(self.data[database]['objects']) + '\n'
        return s.splitlines()
