import itertools


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
