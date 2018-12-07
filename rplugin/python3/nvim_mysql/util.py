import itertools
import re


def get_query_under_cursor(buffer, row, col):
    r"""
    >>> buf = ['select count(*)', 'from test;']
    >>> get_query_under_cursor(buf, 0, 0)
    'select count(*)\nfrom test;'
    >>> buf = ['select count(*) from test;', '', 'select count(*) from blah;']
    >>> get_query_under_cursor(buf, 0, 3)
    'select count(*) from test;'
    >>> get_query_under_cursor(buf, 2, 1)
    'select count(*) from blah;'
    >>> buf = ['select count(*)', 'from test', 'where x = 1;', '', 'select * from x;']
    >>> get_query_under_cursor(buf, 0, 4)
    'select count(*)\nfrom test\nwhere x = 1;'
    >>> get_query_under_cursor(buf, 1, 4)
    'select count(*)\nfrom test\nwhere x = 1;'
    >>> get_query_under_cursor(buf, 2, 4)
    'select count(*)\nfrom test\nwhere x = 1;'
    >>> get_query_under_cursor(buf, 4, 4)
    'select * from x;'
    """
    before = reversed(list(itertools.takewhile(bool, reversed(buffer[:row]))))
    after = itertools.takewhile(bool, buffer[row:])
    return '\n'.join(itertools.chain(before, after))


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


def table_exists(conn, table):
    if '.' in table:
        db, table = table.split('.')
    else:
        db = None
    cursor = conn.cursor()
    if db is not None:
        cursor.execute("show databases")
        databases = {r[0] for r in cursor.fetchall()}
        if db in databases:
            cursor.execute("show tables from `{}`".format(db))
        else:
            return False
    else:
        cursor.execute("show tables")
    tables = {r[0] for r in cursor.fetchall()}
    return table in tables
