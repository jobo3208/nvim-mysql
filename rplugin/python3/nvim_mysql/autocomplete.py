import logging

import sqlparse

import nvim_mysql.util


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_SENTINEL = 'NVIM_MYSQL_SENTINEL'


def _findstart(line_segment):
    """Find start of text to autocomplete.

    >>> _findstart("where x.pers")
    8
    >>> _findstart("from d.person, d.na")
    17
    >>> _findstart("    and x.")
    10
    """
    if '.' in line_segment:
        return line_segment.rindex('.') + 1
    else:
        return -1


def _get_namespace_for_autocomplete(query, row, col):
    """Get the namespace (database or table) that contains the autocomplete candidates."""
    class _TraversalContext(object):
        def __init__(self):
            self.scopes = [{'bindings': {}, 'level': 0}]
            self.rv = None

        @property
        def bindings(self):
            return self.scopes[-1]['bindings']

        @property
        def level(self):
            return self.scopes[-1]['level']

        @staticmethod
        def get_token_level(token):
            level = 0
            while token.parent is not None:
                level += 1
                token = token.parent
            return level

        @staticmethod
        def is_select(token):
            return token.ttype is sqlparse.tokens.DML and token.value.upper() == 'SELECT'

        @staticmethod
        def is_binding(token):
            return isinstance(token, sqlparse.sql.Identifier) and token.has_alias()

        @staticmethod
        def is_sentinel(token):
            return isinstance(token, sqlparse.sql.Identifier) and _SENTINEL in str(token)

        def opens_scope(self, token):
            return self.is_select(token)

        def closes_scope(self, token):
            level = self.get_token_level(token)
            return (
                (self.is_select(token) and level == self.level) or
                (level < self.level)
            )

        def open_scope(self, token):
            level = self.get_token_level(token)
            if level > self.level:
                self.scopes.append({'bindings': self.bindings.copy(), 'level': level})
            else:
                self.scopes.append({'bindings': {}, 'level': level})

        def close_scope(self):
            target_name = self.scopes[-1].get('target_name', None)
            if target_name is not None:
                if target_name in self.bindings:
                    self.rv = self.bindings[target_name]
                else:
                    self.rv = target_name
            del self.scopes[-1]

        def add_binding(self, token):
            if token.get_parent_name() is not None:
                self.bindings[token.get_alias()] = token.get_parent_name() + '.' + token.get_real_name()
            else:
                self.bindings[token.get_alias()] = token.get_real_name()

        def handle_sentinel(self, token):
            self.scopes[-1]['target_name'] = token.get_parent_name()

        def handle_token(self, token):
            if self.closes_scope(token):
                self.close_scope()
            if self.opens_scope(token):
                self.open_scope(token)
            if self.is_binding(token):
                self.add_binding(token)
            if self.is_sentinel(token):
                self.handle_sentinel(token)

        def close_all_scopes(self):
            while self.scopes:
                self.close_scope()


    def _traverse(token, ctx):
        ctx.handle_token(token)
        if hasattr(token, 'tokens'):
            for t in token.tokens:
                _traverse(t, ctx)

    # Insert sentinel to mark where we are autocompleting.
    lines = query.splitlines()
    lines[row] = lines[row][:col] + _SENTINEL + lines[row][col:]
    query = '\n'.join(lines)

    # Parse query and traverse.
    tree = sqlparse.parse(query)[0]
    ctx = _TraversalContext()
    _traverse(tree, ctx)
    ctx.close_all_scopes()
    return ctx.rv


def _complete(line_segment, base, vim, cursor):
    logger.debug('autocomplete: base: "{}"'.format(base))
    logger.debug('autocomplete: line segment is "{}"'.format(line_segment))

    row, col = vim.current.window.cursor[0] - 1, vim.current.window.cursor[1]
    query, row_in_query = nvim_mysql.util.get_query_under_cursor(vim.current.buffer, row, col)
    namespace = _get_namespace_for_autocomplete(query, row_in_query, col)
    logger.debug('autocomplete: namespace is "{}"'.format(namespace))

    cursor.execute("show databases")
    databases = [r[0] for r in cursor.fetchall()]
    if namespace in databases:
        # Assume table
        logger.debug("autocomplete: assuming we're completing a TABLE")
        cursor.execute("show tables from `{}`".format(namespace))
        words = [r[0] for r in cursor.fetchall() if r[0].lower().startswith(base.lower())]
    else:
        # Assume column
        logger.debug("autocomplete: assuming we're completing a COLUMN")
        cursor.execute("describe {}".format(namespace))
        words = [r[0] for r in cursor.fetchall() if r[0].lower().startswith(base.lower())]

    return [{'word': w, 'icase': 1} for w in words]


def complete(findstart, base, vim, cursor):
    col = vim.current.window.cursor[1]
    line_segment = vim.current.line[:col]
    if findstart:
        return _findstart(line_segment)
    else:
        return _complete(line_segment, base, vim, cursor)
