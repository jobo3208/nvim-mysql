import pytest

from nvim_mysql.autocomplete import _get_namespace_for_autocomplete


GET_NAMESPACE_FOR_AUTOCOMPLETE_TEST_CASES = [
    (
        # One table, one alias
        """
        select s.!
        from student s
        """, 'student'
    ),
    (
        # One FQ table
        """
        select s.!
        from school.student s
        """, 'school.student'
    ),
    (
        # Database
        """
        select
        from school.stu!
        """, 'school'
    ),
    (
        # Subquery, no possible alias confusion
        """
        select
        from student
        where student_id in (
            select c.!
            from classroom c
        """, 'classroom'
    ),
    (
        # Subquery referencing outside alias, no possible confusion
        """
        select
        from student s
        where s.student_id in (
            select c.student_id
            from classroom c
            where s.!
        """, 'student'
    ),
    (
        # Subquery referencing local alias with possible confusion
        """
        select
        from student s
        where s.student_id in (
            select s.student_id
            from soccer_team s
            where s.!
        """, 'soccer_team'
    ),
    (
        # Two subqueries, plenty of possible confusion
        """
        select
        from student s
        where s.student_id in (
            select s.student_id
            from soccer_team s
            where s.position = 'GK'
        )
        and s.subject_id in (
            select s.!
            from subject s
        """, 'subject'
    ),
    (
        # Two subqueries, plenty of possible confusion
        """
        select s.!
        from student s
        where s.student_id in (
            select s.student_id
            from soccer_team s
            where s.position = 'GK'
        )
        and s.subject_id in (
            select s.subject_id
            from subject s
        """, 'student'
    ),
    (
        # Subquery with union
        """
        select s.first_name
        from student s
        where s.student_id in (
            select s.student_id
            from science_class s
            where s.desk_number < 10
            union
            select s.!
            from statistics_class s
        """, 'statistics_class'
    ),
    (
        # Triple union
        """
        select s.student_id
        from soccer_team s
        union
        select s.student_id
        from science_class s
        where s.!
        union
        select s.student_id
        from statistics_class s
        """, 'science_class'
    ),
    (
        # Subquery as table
        """
        select s.first_name
        from student s
        join (
            select s.!
            from soccer_team s
        ) x
        on s.student_id = x.student_id
        """, 'soccer_team'
    ),
]


@pytest.mark.parametrize('test_input,expected', GET_NAMESPACE_FOR_AUTOCOMPLETE_TEST_CASES)
def test_get_namespace_for_autocomplete(test_input, expected):
    for i, line in enumerate(test_input.splitlines()):
        if '!' in line:
            row, col = i, line.index('!')
            break
    query = test_input.replace('!', '')
    assert _get_namespace_for_autocomplete(query, row, col) == expected
