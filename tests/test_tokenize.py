import pytest
from sqlfragments._fragments import _tokenize, Token, InvalidSpecifier, InvalidName


class TestTokenize:
    def test_empty(self) -> None:
        tokens = _tokenize("")
        assert tokens == []

    def test_basic(self) -> None:
        tokens = _tokenize("SELECT * FROM table")
        assert tokens == [Token.raw("SELECT * FROM table", 0)]

    def test_escape(self) -> None:
        tokens = _tokenize("SELECT %% FROM table")
        assert tokens == [Token.raw("SELECT % FROM table", 0)]

    def test_normal_specifier(self) -> None:
        # Beginning.
        tokens = _tokenize("%value SOME SQL")
        assert tokens == [Token.specifier("%value", 0), Token.raw(" SOME SQL", 6)]

        # Middle.
        tokens = _tokenize("SOME SQL %value SOME SQL")
        assert tokens == [Token.raw("SOME SQL ", 0), Token.specifier("%value", 9), Token.raw(" SOME SQL", 15)]

        # End.
        tokens = _tokenize("SOME SQL %value")
        assert tokens == [Token.raw("SOME SQL ", 0), Token.specifier("%value", 9)]

        # By itself.
        tokens = _tokenize("%value")
        assert tokens == [Token.specifier("%value", 0)]

        # Different capitalization
        tokens = _tokenize("%ColumnList")
        assert tokens == [Token.specifier("%columnlist", 0)]

        # Directly adjacent.
        tokens = _tokenize("%value%value")
        assert tokens == [Token.specifier("%value", 0), Token.specifier("%value", 6)]

        # Inside valid syntax.
        tokens = _tokenize("(%value)")
        assert tokens == [Token.raw("(", 0), Token.specifier("%value", 1), Token.raw(")", 7)]

    def test_named_specifier(self) -> None:
        # Beginning.
        tokens = _tokenize("%value:name SOME SQL")
        assert tokens == [Token.specifier("%value:name", 0), Token.raw(" SOME SQL", 11)]

        # Middle.
        tokens = _tokenize("SOME SQL %value:name SOME SQL")
        assert tokens == [Token.raw("SOME SQL ", 0), Token.specifier("%value:name", 9), Token.raw(" SOME SQL", 20)]

        # End.
        tokens = _tokenize("SOME SQL %value:name")
        assert tokens == [Token.raw("SOME SQL ", 0), Token.specifier("%value:name", 9)]

        # By itself.
        tokens = _tokenize("%value:name")
        assert tokens == [Token.specifier("%value:name", 0)]

        # Different capitalization
        tokens = _tokenize("%ColumnList:name")
        assert tokens == [Token.specifier("%columnlist:name", 0)]

        # Directly adjacent.
        tokens = _tokenize("%value:name%value:another")
        assert tokens == [Token.specifier("%value:name", 0), Token.specifier("%value:another", 11)]

        # Inside valid syntax.
        tokens = _tokenize("(%value:name)")
        assert tokens == [Token.raw("(", 0), Token.specifier("%value:name", 1), Token.raw(")", 12)]

    def test_invalid_specifier(self) -> None:
        # Not one of our valid specifiers.
        with pytest.raises(InvalidSpecifier, match="Unexpected specifier '%nonsense' encountered in position 1 of fragment!"):
            _tokenize("%nonsense")

        with pytest.raises(InvalidName, match="Invalid name encountered in position 8 of fragment!"):
            _tokenize("%value:")

        with pytest.raises(InvalidName, match="Invalid name '37' encountered in position 8 of fragment!"):
            _tokenize("%value:37")
