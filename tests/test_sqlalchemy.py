from sqlfragments._fragments import fragment, statement


class TestSQLAlchemy:
    def test_empty(self) -> None:
        # Ensure that an empty statement passes checks.
        sql, params = statement("").to_sqlalchemy()
        assert sql == ""
        assert params == {}

    def test_basic(self) -> None:
        # Ensure that a basic statement passes checks.
        sql, params = statement("SELECT * FROM table").to_sqlalchemy()
        assert sql == "SELECT * FROM table"
        assert params == {}

    def test_table(self) -> None:
        # Ensure basic table works.
        sql, params = statement("SELECT * FROM %table", "valid").to_sqlalchemy()
        assert sql == "SELECT * FROM `valid`"
        assert params == {}

        sql, params = statement(
            "SELECT * FROM %table:name", name="valid"
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM `valid`"
        assert params == {}

    def test_column(self) -> None:
        # Ensure basic column works.
        sql, params = statement("SELECT %column FROM table", "valid").to_sqlalchemy()
        assert sql == "SELECT `valid` FROM table"
        assert params == {}

        sql, params = statement(
            "SELECT %column:name FROM table", name="valid"
        ).to_sqlalchemy()
        assert sql == "SELECT `valid` FROM table"
        assert params == {}

    def test_columnlist(self) -> None:
        # Ensure basic column list works.
        sql, params = statement(
            "SELECT %columnlist FROM table", ["valid", "columns"]
        ).to_sqlalchemy()
        assert sql == "SELECT `valid`,`columns` FROM table"
        assert params == {}

        # Ensure basic column list works.
        sql, params = statement(
            "SELECT %columnlist:cols FROM table", cols=["valid", "columns"]
        ).to_sqlalchemy()
        assert sql == "SELECT `valid`,`columns` FROM table"
        assert params == {}

        # Ensure reuse of named params works.
        sql, params = statement(
            "SELECT %columnlist:cols FROM table ; SELECT %columnlist:cols FROM table",
            cols=["valid", "columns"],
        ).to_sqlalchemy()
        assert (
            sql
            == "SELECT `valid`,`columns` FROM table ; SELECT `valid`,`columns` FROM table"
        )
        assert params == {}

    def test_value(self) -> None:
        # Values are passed directly to underlying driver.
        sql, params = statement("WHERE x = %value", None).to_sqlalchemy()
        assert sql == "WHERE x = :v0"
        assert params == {"v0": None}

        sql, params = statement("WHERE x = %value", 15).to_sqlalchemy()
        assert sql == "WHERE x = :v0"
        assert params == {"v0": 15}

        sql, params = statement("WHERE x = %value", "abc").to_sqlalchemy()
        assert sql == "WHERE x = :v0"
        assert params == {"v0": "abc"}

        # Ensure that reused named variables don't get new params.
        sql, params = statement(
            "WHERE x = %value:val AND y = %value:val", val=None
        ).to_sqlalchemy()
        assert sql == "WHERE x = :v0 AND y = :v0"
        assert params == {"v0": None}

        sql, params = statement(
            "WHERE x = %value:val AND y = %value:val", val=15
        ).to_sqlalchemy()
        assert sql == "WHERE x = :v0 AND y = :v0"
        assert params == {"v0": 15}

        sql, params = statement(
            "WHERE x = %value:val AND y = %value:val", val="abc"
        ).to_sqlalchemy()
        assert sql == "WHERE x = :v0 AND y = :v0"
        assert params == {"v0": "abc"}

    def test_valuelist(self) -> None:
        # Most things are valid here, but the list does need to be ordered and non-empty.
        sql, params = statement(
            "INSERT INTO (x, y, z) VALUES (%valuelist)", [1, 2, 3]
        ).to_sqlalchemy()
        assert sql == "INSERT INTO (x, y, z) VALUES (:v0,:v1,:v2)"
        assert params == {"v0": 1, "v1": 2, "v2": 3}

        sql, params = statement(
            "INSERT INTO (x, y, z) VALUES (%valuelist)", ["a", None, 3]
        ).to_sqlalchemy()
        assert sql == "INSERT INTO (x, y, z) VALUES (:v0,:v1,:v2)"
        assert params == {"v0": "a", "v1": None, "v2": 3}

        # Ensure reused named variables don't get new params.
        sql, params = statement(
            "INSERT INTO (x, y, z, a, b, c) VALUES (%valuelist:vals, %valuelist:vals)",
            vals=[1, 2, 3],
        ).to_sqlalchemy()
        assert sql == "INSERT INTO (x, y, z, a, b, c) VALUES (:v0,:v1,:v2, :v0,:v1,:v2)"
        assert params == {"v0": 1, "v1": 2, "v2": 3}

        sql, params = statement(
            "INSERT INTO (x, y, z, a, b, c) VALUES (%valuelist:vals, %valuelist:vals)",
            vals=["a", None, 3],
        ).to_sqlalchemy()
        assert sql == "INSERT INTO (x, y, z, a, b, c) VALUES (:v0,:v1,:v2, :v0,:v1,:v2)"
        assert params == {"v0": "a", "v1": None, "v2": 3}

    def test_fragment(self) -> None:
        # Fragment type can be a fragment itself, or None.
        sql, params = statement(
            "SELECT * FROM table %fragment", fragment("WHERE x = 5")
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE x = 5"
        assert params == {}

        sql, params = statement(
            "SELECT * FROM table %fragment", fragment("WHERE x = %value", 5)
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE x = :v0"
        assert params == {"v0": 5}

        sql, params = statement("SELECT * FROM table %fragment", None).to_sqlalchemy()
        assert sql == "SELECT * FROM table"
        assert params == {}

    def test_statement(self) -> None:
        # Statement type can be a fragment itself, or None.
        sql, params = statement(
            "SELECT * FROM table; %statement",
            statement("SELECT * FROM table WHERE x = 5"),
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table; SELECT * FROM table WHERE x = 5;"
        assert params == {}

        sql, params = statement("SELECT * FROM table; %statement", None).to_sqlalchemy()
        assert sql == "SELECT * FROM table;"
        assert params == {}

    def test_fragmentlist(self) -> None:
        # Fragment list type can be a list of fragments or None. They can't be iterables
        # because fragments and statements often matter in what order you execute them.
        sql, params = statement(
            "SELECT * FROM table %fragmentlist",
            [fragment("WHERE x = 5"), fragment("AND y = 10")],
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE x = 5 AND y = 10"
        assert params == {}

        sql, params = statement(
            "SELECT * FROM table %fragmentlist",
            [fragment("WHERE x = %value", 5), fragment("AND y = %value", 10)],
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE x = :v0 AND y = :v1"
        assert params == {"v0": 5, "v1": 10}

        sql, params = statement(
            "SELECT * FROM table %fragmentlist", [None]
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table"
        assert params == {}

        sql, params = statement("SELECT * FROM table %fragmentlist", []).to_sqlalchemy()
        assert sql == "SELECT * FROM table"
        assert params == {}

    def test_statementlist(self) -> None:
        # Statement list type can be a list of fragments or None. They can't be iterables
        # because fragments and statements often matter in what order you execute them.
        sql, params = statement(
            "SELECT * FROM table; %statementlist",
            [statement("SELECT id FROM table"), statement("SELECT val FROM table")],
        ).to_sqlalchemy()
        assert (
            sql == "SELECT * FROM table; SELECT id FROM table; SELECT val FROM table;"
        )
        assert params == {}

        sql, params = statement(
            "SELECT * FROM table; %statementlist", [None]
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table;"
        assert params == {}

        sql, params = statement(
            "SELECT * FROM table; %statementlist", []
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table;"
        assert params == {}

    def test_inlist(self) -> None:
        # In list allows any iterable of any values, including an empty list, but does not allow
        # None values.
        sql, params = statement(
            "SELECT * FROM table WHERE x IN (%inlist)", [1, 2, 3]
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE x IN (:i0,:i1,:i2)"
        assert params == {"i0": 1, "i1": 2, "i2": 3}

        sql, params = statement(
            "SELECT * FROM table WHERE x IN (%inlist)", {1, 2, 3}
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE x IN (:i0,:i1,:i2)"
        assert len(params) == 3
        assert params.keys() == {"i0", "i1", "i2"}
        assert set(params.values()) == {1, 2, 3}

        sql, params = statement(
            "SELECT * FROM table WHERE x IN (%inlist)", []
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE x IN (NULL)"
        assert params == {}

    def test_andlist(self) -> None:
        # And list type can be an iterable of fragments or None.
        sql, params = statement(
            "SELECT * FROM table WHERE %andlist",
            [fragment("x = 5"), fragment("y = 10")],
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE (x = 5) AND (y = 10)"
        assert params == {}

        sql, params = statement(
            "SELECT * FROM table WHERE %andlist", {fragment("x = %value", 5)}
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE (x = :v0)"
        assert params == {"v0": 5}

        sql, params = statement(
            "SELECT * FROM table WHERE %andlist", [None]
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE TRUE"
        assert params == {}

        sql, params = statement(
            "SELECT * FROM table WHERE %andlist", []
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE TRUE"
        assert params == {}

    def test_orlist(self) -> None:
        # Or list type can be an iterable of fragments or None.
        sql, params = statement(
            "SELECT * FROM table WHERE %orlist", [fragment("x = 5"), fragment("y = 10")]
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE (x = 5) OR (y = 10)"
        assert params == {}

        sql, params = statement(
            "SELECT * FROM table WHERE %orlist", {fragment("x = %value", 5)}
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE (x = :v0)"
        assert params == {"v0": 5}

        sql, params = statement(
            "SELECT * FROM table WHERE %orlist", [None]
        ).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE FALSE"
        assert params == {}

        sql, params = statement("SELECT * FROM table WHERE %orlist", []).to_sqlalchemy()
        assert sql == "SELECT * FROM table WHERE FALSE"
        assert params == {}

    def test_andorlist(self) -> None:
        # And list of or should still logically operate.
        sql, params = statement(
            "SELECT * FROM table WHERE %andlist",
            [
                fragment("%orlist", [fragment("x = 5"), fragment("x = 7")]),
                fragment("%orlist", [fragment("y = 10"), fragment("y = 15")]),
            ],
        ).to_sqlalchemy()
        assert (
            sql
            == "SELECT * FROM table WHERE ((x = 5) OR (x = 7)) AND ((y = 10) OR (y = 15))"
        )
        assert params == {}
