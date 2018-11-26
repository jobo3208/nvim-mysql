import logging

import sqlparse

import nvim_mysql.util


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_table_aliases(query):
    parsed_query = sqlparse.parse(query)[0]
    aliases = {}
    for t in parsed_query.tokens:
        if isinstance(t, sqlparse.sql.Identifier):
            if t.has_alias():
                full_name = '.'.join([t.get_parent_name() or '', t.get_real_name()])
                aliases[t.get_alias()] = full_name
    return aliases


def complete(findstart, base, vim, cursor):
    cursor.execute("show databases")
    databases = [r[0] for r in cursor.fetchall()]
    col = vim.current.window.cursor[1]
    line_segment = vim.current.line[:col]
    if findstart:
        if '.' in line_segment:
            return line_segment.rindex('.') + 1
        else:
            return -1
    else:
        logger.debug('autocomplete: base: "{}"'.format(base))
        logger.debug('autocomplete: line segment is "{}"'.format(line_segment))
        namespace = line_segment[line_segment.rindex(' ') + 1:line_segment.rindex('.')]  # TODO: make more robust
        logger.debug('autocomplete: namespace is "{}"'.format(namespace))
        if namespace in databases:
            # Assume table
            logger.debug("autocomplete: assuming we're completing a TABLE")
            cursor.execute("show tables from `{}`".format(namespace))
            return [r[0] for r in cursor.fetchall() if r[0].lower().startswith(base.lower())]
        else:
            # Assume column
            logger.debug("autocomplete: assuming we're completing a COLUMN")
            query = nvim_mysql.util.get_query_under_cursor(
                vim.current.buffer,
                vim.current.window.cursor[0] - 1,
                vim.current.window.cursor[1]
            )
            aliases = get_table_aliases(query)
            logger.debug("autocomplete: query aliases: {}".format(aliases))
            if namespace in aliases:
                table = aliases[namespace]
            else:
                table = namespace
            logger.debug("autocomplete: table: {}".format(table))
            cursor.execute("describe {}".format(table))
            return [r[0] for r in cursor.fetchall() if r[0].lower().startswith(base.lower())]
