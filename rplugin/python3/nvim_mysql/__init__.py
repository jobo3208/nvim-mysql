import asyncio
import csv
import io
import logging
import os

import cxnstr
import greenlet
import pymysql
import pymysql.constants.FIELD_TYPE as FT
import pynvim

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


class NvimMySQLError(Exception):
    pass


def results_to_table(header, rows, types=None):
    """Format query result set as an ASCII table.

    If a list of field types is provided (from cursor.description), type hints
    will be added to the headers.

    Return a list of strings.
    """
    header = header[:]
    if types:
        for i, t in enumerate(types):
            if t in NUMERIC_TYPES:
                header[i] = '#' + header[i]
            elif t in DATE_TYPES:
                header[i] = '@' + header[i]

    def display_value(v):
        # Return the value to display for one particular cell/value.
        if v is None:
            v = u'NULL'
        elif isinstance(v, bytes):
            try:
                v = v.decode('utf-8')
                v = ' '.join(v.splitlines())
            except UnicodeDecodeError:
                v = '0x' + v.hex()
        else:
            v = str(v)
            v = ' '.join(v.splitlines())
        return v

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


def results_to_csv(header, rows):
    f = io.StringIO()
    csv_out = csv.writer(f)
    csv_out.writerow(header)
    csv_out.writerows(rows)
    return f.getvalue().splitlines()


def format_results(results, format_='table'):
    if results['type'] == 'read':
        if format_ == 'table':
            lines = results_to_table(results['header'], results['rows'], results['types'])
            lines.extend(["", "{} row(s) in set".format(results['count'])])
            return lines
        elif format_ == 'csv':
            return results_to_csv(results['header'], results['rows'])
        else:
            raise ValueError("Invalid results format '{}'".format(format_))
    elif results['type'] == 'write':
        return ["", "{} row(s) affected".format(results['count'])]
    elif results['type'] == 'error':
        return results['message'].splitlines()


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
        self.server = None
        self.conn = None
        self.status = {
            'executing': False,
            'killing': False,
            'results_pending': False,
        }
        self.results = []  # results from last query
        self.results_buffer = self._initialize_results_buffer()
        self.results_format = None

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
        self.vim.command("nnoremap <buffer> q :q<CR>")
        self.vim.command("nnoremap <buffer> <Leader>c :MySQLShowResults csv<CR>")
        self.vim.command("nnoremap <buffer> <Leader>f :MySQLFreezeResultsHeader<CR>")

        # Switch back
        self.vim.command("b! {}".format(cur_buf.number))

        return results_buffer

    def set_connection(self, conn, server):
        """Set this MySQL tab's database connection to conn.

        server is the server name.
        """
        if self.conn:
            self.conn.close()
        self.conn = conn
        self.server = server
        self.tabpage.vars['MySQLServer'] = server

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

    def execute_query(self, query):
        """Execute the given query in this tab.

        Results will be displayed if appropriate when the query finishes.
        """
        # Ignore if a query is already running.
        if self.status['executing']:
            return

        # python2 can't assign to the error variable from inside
        # run_query. If we migrate to py3, we should be able to use the
        # nonlocal keyword. For now, we'll use a mutable container.
        error = []
        gr = greenlet.getcurrent()
        cursor = self.conn.cursor()

        def run_query():
            logger.debug("run_query called")
            try:
                cursor.execute(query)
            except Exception as e:
                error.append("Error: " + repr(e))
            finally:
                cursor.close()

        def query_done(*args):
            logger.debug("query_done called")
            gr.switch()

        self.update_status(executing=True)
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, run_query)
        fut.add_done_callback(query_done)
        logger.debug("executing query: {}".format(query))
        gr.parent.switch()

        # Query is done.
        self.update_status(executing=False, killing=False)
        if error:
            self.results = {'type': 'error', 'message': error[0]}
        elif not cursor.description:
            self.results = {'type': 'write', 'count': cursor.rowcount}
        else:
            header = [f[0] for f in cursor.description]
            types = [f[1] for f in cursor.description]
            rows = cursor.fetchall()
            self.results = {'type': 'read', 'header': header, 'types': types, 'rows': rows, 'count': cursor.rowcount}

        # TODO: Differentiate results pending from error pending?
        self.update_status(results_pending=True)

        self.vim.command('MySQLShowResults table {}'.format(self.autoid))

    def complete(self, findstart, base):
        return nvim_mysql.autocomplete.complete(findstart, base, self.vim, self.conn.cursor())

    def close(self):
        try:
            self.conn.close()
        except:
            pass
        self.vim.command("bd! {}".format(self.results_buffer.number))


@pynvim.plugin
class MySQL(object):
    """Plugin interface to neovim."""
    def __init__(self, vim):
        self.vim = vim
        self.tabs = {}
        self.initialized = False
        logger.debug("initialized plugin")

    @pynvim.command('MySQLConnect', nargs=1, sync=True)
    def connect(self, args):
        """Use the given connection_string to connect the current tabpage to a MySQL server."""
        target = args[0]
        aliases = self.vim.vars.get('nvim_mysql#aliases', None)
        if aliases is not None and target in aliases:
            logger.debug("'{}' is an alias for '{}'".format(target, aliases[target]))
            connection_string = aliases[target]
        else:
            connection_string = target
        db_params = cxnstr.to_dict(connection_string)
        server = db_params['host']
        logger.debug("connecting to {}".format(connection_string))
        conn = pymysql.connect(**db_params)
        conn.autocommit(True)
        logger.debug("connection succeeded")

        tabpage = self.vim.current.tabpage
        if tabpage in self.tabs:
            logger.debug("this tab is already MySQL-connected, will replace connection")
            tab = self.tabs[tabpage]
        else:
            logger.debug("this tab is not MySQL-connected, will initialize")
            tab = self.tabs[tabpage] = MySQLTab(self, self.vim, tabpage)
        tab.set_connection(conn, server)

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

    @pynvim.command('MySQLDescribeTableUnderCursor', sync=False)
    def describe_table_under_cursor(self):
        """Describe the table under the cursor."""
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        word = nvim_mysql.util.get_word_under_cursor(
            self.vim.current.buffer,
            self.vim.current.window.cursor[0] - 1,
            self.vim.current.window.cursor[1]
        )
        table = nvim_mysql.util.word_to_table(word)
        if nvim_mysql.util.table_exists(current_tab.conn, table):
            query = "describe {}".format(table)
            current_tab.execute_query(query)
        else:
            raise NvimMySQLError("Table '{}' does not exist".format(table))

    @pynvim.command('MySQLSampleTableUnderCursor', sync=False)
    def sample_table_under_cursor(self):
        """Select a sampling of rows from the table under the cursor."""
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        word = nvim_mysql.util.get_word_under_cursor(
            self.vim.current.buffer,
            self.vim.current.window.cursor[0] - 1,
            self.vim.current.window.cursor[1]
        )
        table = nvim_mysql.util.word_to_table(word)
        if nvim_mysql.util.table_exists(current_tab.conn, table):
            query = "select * from {} limit 100".format(table)
            current_tab.execute_query(query)
        else:
            raise NvimMySQLError("Table '{}' does not exist".format(table))

    @pynvim.command('MySQLCountTableUnderCursor', sync=False)
    def count_table_under_cursor(self):
        """Select count(*) from the table under the cursor."""
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)
        if current_tab is None:
            raise NvimMySQLError("This is not a MySQL-connected tabpage")

        word = nvim_mysql.util.get_word_under_cursor(
            self.vim.current.buffer,
            self.vim.current.window.cursor[0] - 1,
            self.vim.current.window.cursor[1]
        )
        table = nvim_mysql.util.word_to_table(word)
        if nvim_mysql.util.table_exists(current_tab.conn, table):
            query = "select count(*) from {}".format(table)
            current_tab.execute_query(query)
        else:
            raise NvimMySQLError("Table '{}' does not exist".format(table))

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

        conn = pymysql.connect(current_tab.server, read_default_file='~/.my.cnf')
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

        format can be one of 'table' (the default) or 'csv'.

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
            if format_ not in ['table', 'csv']:
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

        # If results buffer is already open, jump to it.
        results_buffer_windows = [(i, w) for (i, w) in enumerate(
            self.vim.current.tabpage.windows, 1) if w.buffer == current_tab.results_buffer]
        if results_buffer_windows:
            logger.debug("results buffer is already open in this tab")
            self.vim.command('{}wincmd w'.format(results_buffer_windows[0][0]))
        else:
            # If not, open it.
            result_win_height = int(self.vim.current.window.height * 0.35)
            split_command = "{}sp".format(result_win_height)
            logger.debug("split command: {}".format(split_command))
            self.vim.command(split_command)
            self.vim.command("b! {}".format(current_tab.results_buffer.number))

        if current_tab.status['results_pending'] or format_ != self.results_format:
            current_tab.results_buffer[:] = format_results(current_tab.results, format_)
            self.results_format = format_
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

    @pynvim.function('MySQLComplete', sync=True)
    def complete(self, args):
        if not self.initialized:
            raise NvimMySQLError("Use MySQLConnect to connect to a database first")

        current_tab = self.tabs.get(self.vim.current.tabpage, None)

        # If this isn't a MySQL tab, ignore.
        if current_tab is None:
            return []

        # If there's a running query, ignore.
        if current_tab.status['executing']:
            return []

        return current_tab.complete(*args)

    @pynvim.autocmd('TabClosed', sync=True)
    def cleanup_tabs_on_tabclosed(self):
        self.cleanup_tabs()

    def cleanup_tabs(self):
        logger.debug("number of open tabs: {}".format(len(self.vim.tabpages)))
        for nvim_tab, mysql_tab in list(self.tabs.items()):
            if nvim_tab not in self.vim.tabpages:
                logger.debug("tab w/ handle {} is not longer open. closing.".format(nvim_tab.handle))
                mysql_tab.close()
                del self.tabs[nvim_tab]

    @pynvim.autocmd('WinEnter', sync=True)
    def auto_close_results_on_winenter(self):
        if self.vim.vars.get('nvim_mysql#auto_close_results', 0):
            tabpage = self.vim.current.tabpage
            current_tab = self.tabs.get(tabpage, None)
            if current_tab is not None:
                if len(tabpage.windows) == 1:
                    window = tabpage.windows[0]
                    if window.buffer == current_tab.results_buffer:
                        self.vim.command('q')

                        # We have to call this manually because the TabClosed
                        # autocommand doesn't appear to be called when using
                        # vim.command.
                        self.cleanup_tabs()

    def _initialize(self):
        self.initialized = True
        tabline_file = os.path.join(os.path.dirname(__file__), 'tabline.vim')
        self.vim.command('source {}'.format(tabline_file))

        # Set up autocomplete
        self.vim.command('set completefunc=MySQLComplete')

        self.refresh_tabline()

    def refresh_tabline(self):
        self.vim.command('set showtabline=2 tabline=%!MySQLTabLine()')
