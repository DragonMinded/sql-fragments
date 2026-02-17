from abc import ABC, abstractmethod
from enum import StrEnum, Enum, auto
from string import ascii_letters, digits
from typing import Dict, Final, Iterable, List, LiteralString, Optional, Sequence, Tuple


class Specifier(StrEnum):
    TABLE = "%table"
    COLUMN = "%column"
    COLUMN_LIST = "%columnlist"
    VALUE = "%value"
    VALUE_LIST = "%valuelist"
    FRAGMENT = "%fragment"
    FRAGMENT_LIST = "%fragmentlist"
    STATEMENT = "%statement"
    STATEMENT_LIST = "%statementlist"
    AND_LIST = "%andlist"
    OR_LIST = "%orlist"
    IN_LIST = "%inlist"

    def __contains__(self, item: object) -> bool:
        try:
            Specifier(str(item))
            return True
        except ValueError:
            return False


# What we accept in our table and column values.
VALID_IDENTIFIER_CHARS: Final[str] = ascii_letters + digits + "._"

# What we see as specifier name or value.
VALID_SPECIFIER_CHARS: Final[str] = ascii_letters + digits


class FragmentException(Exception):
    pass


class ParseException(FragmentException):
    pass


class InvalidSpecifier(ParseException):
    pass


class InvalidName(ParseException):
    pass


class ArgumentException(FragmentException):
    pass


class MissingArgument(ArgumentException):
    pass


class InvalidArgument(ArgumentException):
    pass


class TokenType(Enum):
    # Raw SQL
    RAW = auto()
    # A specifier from the above valid types.
    SPECIFIER = auto()


class Token:
    def __init__(self, ttype: TokenType, idx: int, value: str, name: Optional[str]) -> None:
        self.type = ttype
        self.idx = idx
        self.value = value
        self.name = name

    @staticmethod
    def raw(value: str, idx: int) -> "Token":
        return Token(TokenType.RAW, idx - len(value), value, None)

    @staticmethod
    def specifier(specifier: str, idx: int) -> "Token":
        # For error printing.
        pos = idx - len(specifier)

        # Split to specifier and name if needed.
        if ':' in specifier:
            specifier, name = specifier.split(':', 1)
        else:
            name = None

        # Double check that the specifier is valid.
        specifier = specifier.lower()
        if specifier not in Specifier:
            raise InvalidSpecifier(f"Unexpected specifier {specifier!r} encountered in position {pos + 1} of fragment!")

        # Double check that the name is valid.
        if name is not None:
            # Location of name is past the specifier and colon.
            npos = pos + len(specifier) + 1

            if not name:
                raise InvalidName(f"Invalid name encountered in position {npos + 1} of fragment!")

            if not name[0].isalpha():
                raise InvalidName(f"Invalid name {name!r} encountered in position {npos + 1} of fragment!")

        return Token(TokenType.SPECIFIER, pos, specifier, name)


class TokenState(Enum):
    # We're accumulating string characters.
    STRING = auto()
    # We're accumulating a specifier, but have not hit an optional name yet.
    SPECIFIER_VALUE = auto()
    # We're accumulating a specifier, and have hit the optional name.
    SPECIFIER_NAME = auto()


def _tokenize(sql: LiteralString) -> List[Token]:
    tokens: List[Token] = []
    accum: str = ""
    state: TokenState = TokenState.STRING

    for idx, c in enumerate(sql):
        if state == TokenState.STRING:
            # Check if we're starting a format specifier or continuing to accumulate
            # characters from a string.
            if c == '%':
                # Only add a previous token if the accumulator has anything in it.
                if accum:
                    tokens.append(Token.raw(accum, idx))

                # This is the beginning of accumulating a specifier value.
                accum = "%"
                state = TokenState.SPECIFIER_VALUE
            else:
                # This is just continuing to accumulate characters to a string.
                accum += c

        elif state == TokenState.SPECIFIER_VALUE:
            # Check if we've encountered an optional name in the format of %specifier:name
            if c == ':':
                # This is a continuation of the current token, but we've moved on
                # to accumulating the specifier name itself.
                accum += c
                state = TokenState.SPECIFIER_NAME
            elif c == '%':
                # This is either an escaped percent or the start of a new specifier.
                if accum == "%":
                    # This is just an escaped character. It already equals what we want it to.
                    state = TokenState.STRING
                else:
                    # This is a new specifier that is directly adjacent to the current one.
                    tokens.append(Token.specifier(accum, idx))
                    accum = "%"
            elif c.isalnum():
                # This is a continuation of the specifier.
                accum += c
            else:
                # This is most likely a paren, comma, bracket or semicolon, indicating that the
                # specifier is finished accumulating and we should go back to string accum.
                tokens.append(Token.raw(accum, idx))
                accum = c
                state = TokenState.STRING

        elif state == TokenState.SPECIFIER_NAME:
            # We should not encounter a second colon, so at this point we know this is a problem.
            if c == ':':
                raise ParseException(f"Unexpected colon encountered in position {idx + 1} of fragment!")
            elif c == '%':
                # We know this is the start of a new specifier, since we only get to this state if
                # we've encountered a ":" in the specifier.
                tokens.append(Token.specifier(accum, idx))
                accum = "%"
                state = TokenState.SPECIFIER_VALUE
            elif c.isalnum():
                # This is a continuation of the specifier.
                accum += c
            else:
                # This is most likely a paren, comma, bracket or semicolon, indicating that the
                # specifier is finished accumulating and we should go back to string accum.
                tokens.append(Token.raw(accum, idx))
                accum = c
                state = TokenState.STRING

    if accum:
        if state == TokenState.STRING:
            tokens.append(Token.raw(accum, len(sql)))
        elif state in {TokenState.SPECIFIER_VALUE, TokenState.SPECIFIER_NAME}:
            tokens.append(Token.specifier(accum, len(sql)))
        else:
            raise FragmentException("Logic error, encountered unexpected token in tokenizer!")

    return _combine(tokens)


def _combine(tokens: List[Token]) -> List[Token]:
    combined: List[Token] = []

    for token in tokens:
        if token.type == TokenType.SPECIFIER:
            # Just add this.
            combined.append(token)

        elif combined and token.type == TokenType.RAW and combined[-1].type == TokenType.RAW:
            # Combine the previous and current token together as one raw token.
            combined = [
                *combined[:-1],
                Token(TokenType.RAW, combined[-1].idx, combined[-1].value + token.value, None),
            ]

        else:
            # This can't be combined, just add it.
            combined.append(token)

    return combined


def fragment(sql: LiteralString, *args: object, **kwargs: object) -> "Fragment":
    # First, tokenize the SQL into raw tokens. This is done without arg substitution or converting
    # into pieces so that the tokenization itself can be cached in the future.
    tokens = _tokenize(sql)

    # Now go through and assign arguments to all specifier tokens. Consume positional args, but
    # don't consume kwargs because it's perfectly valid to use the same argument more than once
    # when using named arguments.
    pieces: List[Piece] = []

    for token in tokens:
        if token.type == TokenType.RAW:
            # Just a string piece of SQL.
            pieces.append(String(token.value))

        elif token.type == TokenType.SPECIFIER:
            # A specifier, we need to look up the actual value.
            spec = token.value
            name = token.name
            pos = token.idx

            if name is None:
                if not args:
                    # There is no argument for this.
                    raise MissingArgument(f"{spec} in position {pos + 1} is missing positional argument.")

                # Grab the first argument, consuming it.
                arg = args[0]
                args = args[1:]

            else:
                if name not in kwargs:
                    # There is no argument for this.
                    raise MissingArgument(f"{spec} in position {pos + 1} is missing named argument {name!r}.")

                # Grab the argument, do not consume it.
                arg = kwargs[name]

            # This is safe because we previously checked for valid values in the tokenizer.
            specifier = Specifier(spec)
            actual: object

            # Validate parameter types and auto-conversion for things like Set to List.
            if specifier in {Specifier.TABLE, Specifier.COLUMN}:
                # Ensure valid identifiers, very strict because this is our own sanitization so we
                # simply do not allow any shenanigans.
                actual = str(arg)
                if any(a not in VALID_IDENTIFIER_CHARS for a in actual):
                    raise InvalidArgument(f"{spec} in position {pos + 1} requires a string-like with valid identifier characters.")

            elif specifier == Specifier.COLUMN_LIST:
                # Makes no sense for a column list to be anything but an ordered sequence type.
                if not isinstance(arg, Sequence):
                    raise InvalidArgument(f"{spec} in position {pos + 1} requires a sequence of valid identifiers.")

                actual = [str(a) for a in arg]
                if not actual:
                    raise InvalidArgument(f"{spec} in position {pos + 1} expected to be a non-empty sequence.")

                for val in actual:
                    # Ensure valid identifiers, very strict because this is our own sanitization so we
                    # simply do not allow any shenanigans.
                    if any(a not in VALID_IDENTIFIER_CHARS for a in actual):
                        raise InvalidArgument(
                            f"{spec} in position {pos + 1} individual entries require a string-like with valid " +
                            "identifier characters."
                        )

            elif specifier == Specifier.VALUE_LIST:
                # Makes no sense for a value list to be anything but an ordered sequence type.
                if not isinstance(arg, Sequence):
                    raise InvalidArgument(f"{spec} in position {pos + 1} requires a sequence of values.")

                actual = [a for a in arg]
                if not actual:
                    raise InvalidArgument(f"{spec} in position {pos + 1} expected to be a non-empty sequence.")

            elif specifier == Specifier.IN_LIST:
                # In list is often used for ID checks, so it can be empty, and in any order, but
                # it makes no sense for a value to be None.
                if not isinstance(arg, Iterable):
                    raise InvalidArgument(f"{spec} in position {pos + 1} requires an iterable of values.")

                actual = [a for a in arg]
                if any(a is None for a in actual):
                    raise InvalidArgument(
                        f"{spec} in position {pos + 1} cannot accept None values for individual entries."
                    )

            elif specifier in {Specifier.FRAGMENT, Specifier.STATEMENT}:
                # These must either be None or a Fragment. None gets skipped because we simply don't render it out.
                if arg is None:
                    continue

                if not isinstance(arg, Fragment):
                    raise InvalidArgument(f"{spec} in position {pos + 1} requires a Fragment.")

                actual = arg

            elif specifier in {Specifier.FRAGMENT_LIST, Specifier.STATEMENT_LIST}:
                # These are ordered, so must be a sequence. They can contain either Fragments or None to filter out.
                if not isinstance(arg, Sequence):
                    raise InvalidArgument(f"{spec} in position {pos + 1} requires a sequence of Fragment.")

                actual = [a for a in arg if a is not None]
                if any(not isinstance(a, Fragment) for a in actual):
                    raise InvalidArgument(f"{spec} in position {pos + 1} individual entries require a Fragment.")

            elif specifier in {Specifier.FRAGMENT_LIST, Specifier.STATEMENT_LIST}:
                # These are unordered, so can be any iterable. They can contain either Fragments or None to filter out.
                if not isinstance(arg, Iterable):
                    raise InvalidArgument(f"{spec} in position {pos + 1} requires an iterable of Fragment.")

                actual = [a for a in arg if a is not None]
                if any(not isinstance(a, Fragment) for a in actual):
                    raise InvalidArgument(f"{spec} in position {pos + 1} individual entries require a Fragment.")

            pieces.append(Parameter(specifier, actual))

        else:
            raise FragmentException(f"Logic error, encountered unrecognized token in position {token.idx} during fragment parsing!")

    return Fragment(pieces)


class Piece(ABC):
    @abstractmethod
    def raw(self) -> Optional[str]:
        ...

    @abstractmethod
    def specifier(self) -> Optional[Specifier]:
        ...

    @abstractmethod
    def value(self) -> object:
        ...


class String(Piece):
    # A bit of SQL that doesn't need any additional mangling.
    def __init__(self, value: str) -> None:
        self._value = value

    def raw(self) -> Optional[str]:
        return self._value

    def specifier(self) -> Optional[Specifier]:
        return None

    def value(self) -> object:
        return None


class Parameter(Piece):
    # A parameter, either named or unnamed.
    def __init__(self, specifier: Specifier, value: object) -> None:
        self._specifier = specifier
        self._value = value

    def raw(self) -> Optional[str]:
        return None

    def specifier(self) -> Optional[Specifier]:
        return self._specifier

    def value(self) -> object:
        return self._value


class Fragment:
    def __init__(self, parts: Iterable[Piece]) -> None:
        self._parts = parts

    def __repr__(self) -> str:
        # Just spit out the sqlalchemy raw SQL string for now.
        sql, _ = self.to_sqlalchemy()
        return sql

    def to_sqlalchemy(self) -> Tuple[str, Dict[str, object]]:
        return self._to_sqlalchemy(0)

    def _to_sqlalchemy(self, start: int) -> Tuple[str, Dict[str, object]]:
        # Convert to a tuple that can be passed to sqlalchemy's session execute function
        # using the text() SQL construct and a dictionary of params.
        params: Dict[str, object] = {}
        sql: str = ""

        def _paramname(specifier: Specifier) -> str:
            return f"{str(specifier)[1]}{len(params) + start}"

        for part in self._parts:
            # First, the easy part, just append any raw SQL we have.
            raw = part.raw()
            if raw:
                sql += raw

            # Now, the hard part. Create parameter substitutions, respecting column and table rules.
            specifier = part.specifier()
            value = part.value()
            if specifier:
                if specifier in {Specifier.TABLE, Specifier.COLUMN}:
                    # Just output it escaped. We already validated the argument to ensure it was
                    # only containing alphanumeric or safe characters.
                    sql += f"`{value}`"

                elif specifier == Specifier.COLUMN_LIST:
                    # Output each escaped. We already verified it was a list and contained alphanumeric
                    # or safe characters only.
                    if isinstance(value, list):
                        sql += ",".join(f"`{v}`" for v in value)
                    else:
                        raise FragmentException(f"Logic error, expected list type for {specifier}!")

                elif specifier == Specifier.VALUE:
                    # Just use sqlalchemy's support for named parameters.
                    param = _paramname(specifier)
                    sql += f":{param}"
                    params[param] = value

                elif specifier in {Specifier.VALUE_LIST, Specifier.IN_LIST}:
                    if isinstance(value, list):
                        if not value:
                            if specifier == Specifier.IN_LIST:
                                sql += "NULL"
                            else:
                                raise FragmentException(f"Logic error, expected non-zero list length for {specifier}!")
                        else:
                            # Just use sqlalchemy's support for named parameters.
                            param = _paramname(specifier)
                            sql += f":{param}"
                            params[param] = value

                    else:
                        raise FragmentException("Logic error, expected list type for {specifier}!")

                elif specifier in {Specifier.FRAGMENT, Specifier.STATEMENT}:
                    if isinstance(value, Fragment):
                        # Convert the fragment itself.
                        subsql, subparams = value._to_sqlalchemy(len(params))
                        sql += subsql
                        params = {
                            **params,
                            **subparams,
                        }

                        if specifier == Specifier.STATEMENT:
                            sql += ";"

                    else:
                        raise FragmentException("Logic error, expected Fragment type for {specifier}!")

                elif specifier in {Specifier.FRAGMENT_LIST, Specifier.STATEMENT_LIST, Specifier.AND_LIST, Specifier.OR_LIST}:
                    if isinstance(value, list):
                        sqls: List[str] = []

                        # First get all the parameters and the raw sql pieces.
                        for chunk in value:
                            if isinstance(value, Fragment):
                                # Convert the fragment itself.
                                subsql, subparams = value._to_sqlalchemy(len(params))

                                if specifier in {Specifier.AND_LIST, Specifier.OR_LIST}:
                                    # Make sure that sub-filters are evaluated in correct logical order.
                                    sqls.append(f"({subsql})")
                                elif specifier == Specifier.STATEMENT_LIST:
                                    # Make sure all entries, including the last, has a semicolon on it.
                                    sqls.append("{subsql};")
                                else:
                                    sqls.append(subsql)

                                params = {
                                    **params,
                                    **subparams,
                                }

                            else:
                                raise FragmentException("Logic error, expected Fragment type for {specifier} item!")

                        # Now, stick 'em all together and put the raw text in the output.
                        if sqls:
                            concat = {
                                Specifier.FRAGMENT_LIST: " ",
                                Specifier.STATEMENT_LIST: " ",
                                Specifier.AND_LIST: " AND ",
                                Specifier.OR_LIST: " OR ",
                            }[specifier]
                            sql += concat.join(sqls)
                        else:
                            if specifier == Specifier.AND_LIST:
                                # A list of no and statements should mean logically that all things
                                # should be let through.
                                sql += " TRUE "
                            elif specifier == Specifier.OR_LIST:
                                sql += " FALSE "

                    else:
                        raise FragmentException("Logic error, expected list type for {specifier}!")

        return (sql, params)
