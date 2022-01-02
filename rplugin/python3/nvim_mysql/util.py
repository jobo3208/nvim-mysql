# -*- coding: utf-8 -*-

import itertools
import re


def get_query_under_cursor(buffer, row, col):
    r"""Return (query, row_in_query).

    >>> buf = ['select count(*)', 'from test;']
    >>> get_query_under_cursor(buf, 0, 0)
    ('select count(*)\nfrom test;', 0)
    >>> buf = ['select count(*) from test;', '', 'select count(*) from blah;']
    >>> get_query_under_cursor(buf, 0, 3)
    ('select count(*) from test;', 0)
    >>> get_query_under_cursor(buf, 2, 1)
    ('select count(*) from blah;', 0)
    >>> buf = ['select count(*)', 'from test', 'where x = 1;', '', 'select * from x;']
    >>> get_query_under_cursor(buf, 0, 4)
    ('select count(*)\nfrom test\nwhere x = 1;', 0)
    >>> get_query_under_cursor(buf, 1, 4)
    ('select count(*)\nfrom test\nwhere x = 1;', 1)
    >>> get_query_under_cursor(buf, 2, 4)
    ('select count(*)\nfrom test\nwhere x = 1;', 2)
    >>> get_query_under_cursor(buf, 3, 0)
    (None, 0)
    >>> get_query_under_cursor(buf, 4, 4)
    ('select * from x;', 0)
    """
    if buffer[row].strip() == '':
        return (None, 0)
    else:
        before = list(reversed(list(itertools.takewhile(bool, reversed(buffer[:row])))))
        after = list(itertools.takewhile(bool, buffer[row:]))
        return '\n'.join(before + after), len(before)


def get_queries_in_range(buffer, start_row, end_row):
    r"""Return a list of queries in the given range.

    The list will include queries that are partially in the range.

    >>> buf = ['', 'select count(*) from blah;', '', 'update bloo', 'set a = 1;', '', '']
    >>> get_queries_in_range(buf, 0, 0)
    []
    >>> get_queries_in_range(buf, 1, 1)
    ['select count(*) from blah;']
    >>> get_queries_in_range(buf, 0, 2)
    ['select count(*) from blah;']
    >>> get_queries_in_range(buf, 0, 3)
    ['select count(*) from blah;', 'update bloo\nset a = 1;']
    >>> get_queries_in_range(buf, 1, 4)
    ['select count(*) from blah;', 'update bloo\nset a = 1;']
    >>> get_queries_in_range(buf, 4, 6)
    ['update bloo\nset a = 1;']
    >>> get_queries_in_range(buf, 5, 6)
    []
    """
    if buffer[start_row].strip():
        before = list(reversed(list(itertools.takewhile(bool, reversed(buffer[:start_row])))))
    else:
        before = []
    if buffer[end_row].strip():
        after = list(itertools.takewhile(bool, buffer[end_row:]))
    else:
        after = []

    queries = []
    query = ''
    for line in before + buffer[start_row:end_row] + after:
        if line.strip():
            if query:
                query += '\n'
            query += line
        elif query:
            queries.append(query)
            query = ''
    if query:
        queries.append(query)

    return queries


def get_word_under_cursor(buffer, row, col):
    """
    >>> buf = ['select count(*) from db.test;', '', '    ']
    >>> get_word_under_cursor(buf, 0, 3)
    'select'
    >>> get_word_under_cursor(buf, 0, 6)
    'select'
    >>> get_word_under_cursor(buf, 0, 7)
    'count(*)'
    >>> get_word_under_cursor(buf, 0, 23)
    'db.test;'
    >>> get_word_under_cursor(buf, 1, 0)
    ''
    >>> get_word_under_cursor(buf, 2, 0)
    ''
    """
    line = buffer[row]
    for word in re.finditer(r'\S+', line):
        if col >= word.start() and col <= word.end():
            return word.group(0)
    return ''


def word_to_table(word):
    return word.rstrip(',;')


def get_parent_database_in_tree(buffer, row):
    """Return the parent database of the table at the given row.

    The return value is a 3-tuple: (database, expanded, row_of_db)

    If the given row contains a database, return that database.

    >>> buf = [u'a ▸', u'b ▾', u'  x', u'c ▸']
    >>> get_parent_database_in_tree(buf, 0)
    ('a', False, 0)
    >>> get_parent_database_in_tree(buf, 1)
    ('b', True, 1)
    >>> get_parent_database_in_tree(buf, 2)
    ('b', True, 1)
    >>> get_parent_database_in_tree(buf, 3)
    ('c', False, 3)
    """
    for i, line in enumerate(reversed(buffer[:row + 1])):
        if line.endswith(u'▾'):
            return (line[:-1].strip(), True, row - i)
        elif line.endswith(u'▸'):
            return (line[:-1].strip(), False, row - i)


class Table(object):
    """Object for representing a MySQL table and properly formatting it.

    Any of these work:

    >>> t = Table('table')
    >>> t = Table('db.table')
    >>> t = Table('`db`.`table`')
    >>> t = Table('db', 'table')

    Usage:

    >>> t = Table('db.table')
    >>> t.db
    'db'
    >>> t.table
    'table'
    >>> print(t)
    `db`.`table`
    """
    def __init__(self, *args):
        args = [a.replace('`', '') for a in args]
        if len(args) == 1:
            if '.' in args[0]:
                self.db, self.table = args[0].split('.')
            else:
                self.db, self.table = None, args[0]
        elif len(args) == 2:
            self.db, self.table = args
        else:
            raise ValueError('too many arguments')

    def __str__(self):
        if self.db:
            return '`{0}`.`{1}`'.format(self.db, self.table)
        else:
            return '`{0}`'.format(self.table)


def table_exists(conn, table):
    t = Table(table)
    cursor = conn.cursor()
    if t.db is not None:
        cursor.execute("show databases")
        databases = {r[0] for r in cursor.fetchall()}
        if t.db in databases:
            cursor.execute("show tables from `{}`".format(t.db))
        else:
            return False
    else:
        cursor.execute("show tables")
    tables = {r[0] for r in cursor.fetchall()}
    return t.table in tables
