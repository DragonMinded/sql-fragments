import pytest
from sqlfragments._fragments import fragment, statement, InvalidArgument


class TestParams:
    def test_empty(self) -> None:
        # Ensure that an empty statement passes checks.
        statement("")

    def test_basic(self) -> None:
        # Ensure that a basic statement passes checks.
        statement("SELECT * FROM table")

    def test_table(self) -> None:
        # Ensure basic table works.
        statement("SELECT * FROM %table", "valid")

        # Ensure that invalid table name fails.
        with pytest.raises(
            InvalidArgument,
            match="%table in position 15 requires a string-like with valid identifier characters.",
        ):
            statement("SELECT * FROM %table", None)

        # Ensure that invalid table name fails.
        with pytest.raises(
            InvalidArgument,
            match="%table in position 15 requires a string-like with valid identifier characters.",
        ):
            statement("SELECT * FROM %table", [])

        # Ensure that invalid table name fails.
        with pytest.raises(
            InvalidArgument,
            match="%table in position 15 requires a string-like with valid identifier characters.",
        ):
            statement("SELECT * FROM %table", "` AND 1 = 1")

    def test_column(self) -> None:
        # Ensure basic column works.
        statement("SELECT %column FROM table", "valid")

        # Ensure that invalid column name fails.
        with pytest.raises(
            InvalidArgument,
            match="%column in position 8 requires a string-like with valid identifier characters.",
        ):
            statement("SELECT %column FROM table", None)

        # Ensure that invalid column name fails.
        with pytest.raises(
            InvalidArgument,
            match="%column in position 8 requires a string-like with valid identifier characters.",
        ):
            statement("SELECT %column FROM table", [])

        # Ensure that invalid column name fails.
        with pytest.raises(
            InvalidArgument,
            match="%column in position 8 requires a string-like with valid identifier characters.",
        ):
            statement("SELECT %column FROM table", "` AND 1 = 1")

    def test_columnlist(self) -> None:
        # Ensure basic column list works.
        statement("SELECT %columnlist FROM table", ["valid", "columns"])

        # Ensure that invalid column list fails.
        with pytest.raises(
            InvalidArgument,
            match="%columnlist in position 8 requires a sequence of valid identifiers.",
        ):
            statement("SELECT %columnlist FROM table", None)

        # Ensure that invalid column list fails.
        with pytest.raises(
            InvalidArgument,
            match="%columnlist in position 8 expected to be a non-empty sequence.",
        ):
            statement("SELECT %columnlist FROM table", [])

        # Ensure that invalid column list fails.
        with pytest.raises(
            InvalidArgument,
            match="%columnlist in position 8 individual entries expected to be string-like.",
        ):
            statement("SELECT %columnlist FROM table", [None])

        # Ensure that invalid column list fails.
        with pytest.raises(
            InvalidArgument,
            match="%columnlist in position 8 individual entries require a string-like with valid identifier characters.",
        ):
            statement("SELECT %columnlist FROM table", ["` AND 1 = 1"])

    def test_value(self) -> None:
        # Values are passed directly to underlying driver.
        statement("WHERE x = %value", None)
        statement("WHERE x = %value", 15)
        statement("WHERE x = %value", "abc")

    def test_valuelist(self) -> None:
        # Most things are valid here, but the list does need to be ordered and non-empty.
        statement("INSERT INTO (x, y, z) VALUES (%valuelist)", [1, 2, 3])
        statement("INSERT INTO (x, y, z) VALUES (%valuelist)", ["a", None, 3])

        # Check for invalid stuff.
        with pytest.raises(
            InvalidArgument,
            match="%valuelist in position 31 requires a sequence of values.",
        ):
            statement("INSERT INTO (x, y, z) VALUES (%valuelist)", None)

        with pytest.raises(
            InvalidArgument,
            match="%valuelist in position 31 requires a sequence of values.",
        ):
            statement("INSERT INTO (x, y, z) VALUES (%valuelist)", set())

        with pytest.raises(
            InvalidArgument,
            match="%valuelist in position 31 expected to be a non-empty sequence.",
        ):
            statement("INSERT INTO (x, y, z) VALUES (%valuelist)", [])

    def test_fragment(self) -> None:
        # Fragment type can be a fragment itself, or None.
        statement("SELECT * FROM table %fragment", fragment("WHERE x = 5"))
        statement("SELECT * FROM table %fragment", None)

        # Fragment type cannot be any other type, including raw strings, since we can't
        # verify that this isn't introducing a SQL injection.
        with pytest.raises(
            InvalidArgument,
            match="%fragment in position 21 requires a Fragment.",
        ):
            statement("SELECT * FROM table %fragment", "WHERE x = 5")

    def test_statement(self) -> None:
        # Statement type can be a fragment itself, or None.
        statement("SELECT * FROM table; %statement", statement("SELECT * FROM table WHERE x = 5"))
        statement("SELECT * FROM table; %statement", None)

        # Statement type cannot be any other type, including raw strings, since we can't
        # verify that this isn't introducing a SQL injection.
        with pytest.raises(
            InvalidArgument,
            match="%statement in position 22 requires a Statement.",
        ):
            statement("SELECT * FROM table; %statement", "WHERE x = 5")

    def test_fragmentlist(self) -> None:
        # Fragment list type can be a list of fragments or None. They can't be iterables
        # because fragments and statements often matter in what order you execute them.
        statement("SELECT * FROM table %fragmentlist", [fragment("WHERE x = 5"), fragment(" AND y = 10")])
        statement("SELECT * FROM table %fragmentlist", [None])
        statement("SELECT * FROM table %fragmentlist", [])

        # Fragment list type cannot be any other type, including raw strings, since we can't
        # verify that this isn't introducing a SQL injection.
        with pytest.raises(
            InvalidArgument,
            match="%fragmentlist in position 21 individual entries require a Fragment.",
        ):
            statement("SELECT * FROM table %fragmentlist", "WHERE x = 5")

        with pytest.raises(
            InvalidArgument,
            match="%fragmentlist in position 21 individual entries require a Fragment.",
        ):
            statement("SELECT * FROM table %fragmentlist", ["WHERE x = 5"])

        with pytest.raises(
            InvalidArgument,
            match="%fragmentlist in position 21 requires a sequence of Fragment.",
        ):
            statement("SELECT * FROM table %fragmentlist", {fragment("WHERE x = 5"), fragment(" AND y = 10")})

    def test_statementlist(self) -> None:
        # Statement list type can be a list of fragments or None. They can't be iterables
        # because fragments and statements often matter in what order you execute them.
        statement("SELECT * FROM table; %statementlist", [statement("SELECT id FROM table"), statement("SELECT val FROM table")])
        statement("SELECT * FROM table; %statementlist", [None])
        statement("SELECT * FROM table; %statementlist", [])

        # Statement list type cannot be any other type, including raw strings, since we can't
        # verify that this isn't introducing a SQL injection.
        with pytest.raises(
            InvalidArgument,
            match="%statementlist in position 21 individual entries require a Statement.",
        ):
            statement("SELECT * FROM table %statementlist", "WHERE x = 5")

        with pytest.raises(
            InvalidArgument,
            match="%statementlist in position 21 individual entries require a Statement.",
        ):
            statement("SELECT * FROM table %statementlist", ["WHERE x = 5"])

        with pytest.raises(
            InvalidArgument,
            match="%statementlist in position 21 requires a sequence of Statement.",
        ):
            statement("SELECT * FROM table %statementlist", {statement("WHERE x = 5"), statement(" AND y = 10")})

    def test_inlist(self) -> None:
        # In list allows any iterable of any values, including an empty list, but does not allow
        # None values.
        statement("SELECT * FROM table WHERE x IN (%inlist)", [1, 2, 3])
        statement("SELECT * FROM table WHERE x IN (%inlist)", {1, 2, 3})
        statement("SELECT * FROM table WHERE x IN (%inlist)", [])

        # Fragment list type cannot be any other type, including raw strings, since we can't
        # verify that this isn't introducing a SQL injection.
        with pytest.raises(
            InvalidArgument,
            match="%inlist in position 33 requires an iterable of values.",
        ):
            statement("SELECT * FROM table WHERE x IN (%inlist)", None)

        with pytest.raises(
            InvalidArgument,
            match="%inlist in position 33 requires an iterable of values.",
        ):
            statement("SELECT * FROM table WHERE x IN (%inlist)", 5)

        with pytest.raises(
            InvalidArgument,
            match="%inlist in position 33 requires an iterable of values.",
        ):
            statement("SELECT * FROM table WHERE x IN (%inlist)", "5")

        with pytest.raises(
            InvalidArgument,
            match="%inlist in position 33 cannot accept None values for individual entries.",
        ):
            statement("SELECT * FROM table WHERE x IN (%inlist)", [1, None, 3])

    def test_andlist(self) -> None:
        # And list type can be an iterable of fragments or None.
        statement("SELECT * FROM table WHERE %andlist", [fragment("x = 5"), fragment("y = 10")])
        statement("SELECT * FROM table WHERE %andlist", {fragment("x = 5"), fragment("y = 10")})
        statement("SELECT * FROM table WHERE %andlist", [None])
        statement("SELECT * FROM table WHERE %andlist", [])

        # Fragment list type cannot be any other type, including raw strings, since we can't
        # verify that this isn't introducing a SQL injection.
        with pytest.raises(
            InvalidArgument,
            match="%andlist in position 27 requires an iterable of Fragment.",
        ):
            statement("SELECT * FROM table WHERE %andlist", None)

        with pytest.raises(
            InvalidArgument,
            match="%andlist in position 27 individual entries require a Fragment.",
        ):
            statement("SELECT * FROM table WHERE %andlist", "x = 5")

        with pytest.raises(
            InvalidArgument,
            match="%andlist in position 27 individual entries require a Fragment.",
        ):
            statement("SELECT * FROM table WHERE %andlist", ["x = 5"])

    def test_orlist(self) -> None:
        # Or list type can be an iterable of fragments or None.
        statement("SELECT * FROM table WHERE %orlist", [fragment("x = 5"), fragment("y = 10")])
        statement("SELECT * FROM table WHERE %orlist", {fragment("x = 5"), fragment("y = 10")})
        statement("SELECT * FROM table WHERE %orlist", [None])
        statement("SELECT * FROM table WHERE %orlist", [])

        # Fragment list type cannot be any other type, including raw strings, since we can't
        # verify that this isn't introducing a SQL injection.
        with pytest.raises(
            InvalidArgument,
            match="%orlist in position 27 requires an iterable of Fragment.",
        ):
            statement("SELECT * FROM table WHERE %orlist", None)

        with pytest.raises(
            InvalidArgument,
            match="%orlist in position 27 individual entries require a Fragment.",
        ):
            statement("SELECT * FROM table WHERE %orlist", "x = 5")

        with pytest.raises(
            InvalidArgument,
            match="%orlist in position 27 individual entries require a Fragment.",
        ):
            statement("SELECT * FROM table WHERE %orlist", ["x = 5"])
