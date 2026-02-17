SQL fragments are a way to keep chunks of SQL and any parameterized arguments together when building queries without an ORM. They take advantage of Python's ability to specify a literal string as an argument to ensure that any potential injection is flagged by the type checker. They include logically consistent ways of creating AND and OR filters for data fetching, sidestep the problem in MySQL and Postgres where an empty list in an IN query causes a syntax error, and provide an easy way to optionally provide fragments to a larger SQL statement. They also allow you to keep parameters local to the fragment of SQL that you are building.

Originally inspired by a similar library in PHP/Hack, I've used or built a version of this at the last several jobs I've worked at in various languages. Unfortunately, `mypy` does not currently support `LiteralString` type checking so this library cannot enable lint-time checks against possible SQL injection when using `mypy` as your type checking system. It's on you to only provide literal strings to the first parameter of `fragment()` in this case, but this is no different than using `text()` in sqlalchemy.

### API

```python
def statement(sql: LiteralString, *args: object, **kwargs: object) -> "Statement":
   ...
```

Parses a SQL query with optional specifiers, binding those specifiers to the arguments presented. Returns a `Statement` which can be used with the `%statement` or `%statementlist` specifiers in another statement or fragment. The `Statement` class also has a `to_sqlalchemy()` method which returns a tuple of SQLAlchemy-compatible SQL and a dictionary of bind parameters, suitable for passing to SQLAlchemy's `execute()` function.

```python
def fragment(sql: LiteralString, *args: object, **kwargs: object) -> "Fragment":
   ...
```

Parses a fragment of SQL with optional specifiers, binding those specifiers to the arguments presented. Returns a `Fragment` which can be used with the `%fragment`, `%fragmentlist`, `%andlist` or `%orlist` specifiers in another statement or fragment. Fragments and Statements both support the full gamut of format specifiers.

```python
class FragmentException(Exception):
    ...
```

Base exception type that all exceptions thrown when parsing SQL will originate from. Various exceptions exist for parsing exceptions that are nested underneath `ParseException` which is itself a subclass of `FragmentException`. Various exceptions exist for argument exceptions that are nested underneath `ArgumentException` which is itself a subclass of `FragmentException`. You should expect to get a subclass of `ParseException` if you provide SQL to either `statement()` or `fragment()` that contains an invalid or unparseable format specifier or specifier name. You should expect to get a subclass of `ArgumentException` if you provide invalid arguments for the given specifier, either as positional arguments or as kwargs to either `statement()` or `fragment()`.

### Format Specifiers

 - `%table` - A table name. For simplicity, this expects the associated argument to be a string containing only alphanumeric characters and the characters `.` and `_`. Results in SQL that contains the table name escaped in back ticks.
 - `%column` - A column name. For simplicity, this expects the associated argument to be a string containing only alphanumeric characters and the characters `.` and `_`. Results in SQL that contains the column name escaped in back ticks.
 - `%columnlist` - A sequence of column names. Each entry in the sequence must conform to the same rules as `%column`. Note that since SQL is order-sensitive when specifying column names, this only takes sequence types, such as a list. Often used in tandem with `%valuelist` in insert statements.
 - `%value` - A value, meant to be passed to the underlying SQL engine as a bind parameter. Can contain any valid python type that the underlying engine knows how to serialize, or `None`.
 - `%valuelist` - A sequence of values. Each entry in the sequence must conform to the same rules as `%value`. Note that since SQL is order-sensitive when specifying lists of values, this only takes sequence types, such as a list. Often used in tandem with `%columnlist` in insert statements.
 - `%fragment` - A `Fragment` obtained from a call to `fragment()`. Use this to compose SQL statements or fragments based on smaller fragments that were composed elsewhere. Note that the specifiers and arguments given to the fragment are respected, so this can be a way of decomposing large queries while still keeping locality of arguments to SQL fragments. Note that this format specifier can also accept `None` in which case it will output nothing. Use this for composing SQL statements with optional fragments.
 - `%fragmentlist` - A sequence of fragments. Each entry in the sequence must conform to the same rules as `%fragment`. Note that much like individual fragments, an entry in this sequence can be `None` which means it will be skipped over when constructing the final SQL. Note that the argument itself cannot be `None`. Instead, use an empty list.
 - `%statement` - A `Statement` obtained from a call to `statement()`. Use this to compose SQL statements or fragments based on complete inner statements that were composed elsewhere. Note that the specifiers and arguments given to the statement are respected, so this can be a way of decomposing large queries while still keeping locality of arguments to SQL statements. Note that this format specifier can also accept `None` in which case it will output nothing. Use this for composing SQL statements with optional inner statements. Note that if the statement itself is not `None`, the resulting SQL will get a semicolon appended to the end of the statement automatically.
 - `%statementlist` - A sequence of statements. Each entry in the sequence must conform to the same rules as `%statement`. Note that much like individual statements, an entry in this sequence can be `None` which means it will be skipped over when constructing the final SQL. Note that the argument itself cannot be `None`. Instead, use an empty list. Note that each valid statement that gets inserted into the final SQL will have a semicolon appended to the end of the statement automatically.
 - `%inlist` - An iterable of values intended to be used in `IN` queries. SQL `IN` queries are not order-specific, so this specifier takes any iterable, such as a list or a set. The values are passed to the underlying SQL engine as bind parameters. Note that if an empty iterable is provided, the SQL keyword `NULL` is instead emitted. This means it is safe to write queries such as `WHERE id IN (%inlist)` without checking to see if the list contains at least one element. **WARNING**: Substituting `NULL` can have the side effect of matching `NULL` in columns that are nullable, so it is best to use this to query groups of IDs or other columns that are not nullable.
 - `%andlist` - An iterable of fragments that will be joined together with the SQL `AND` keyword. Each entry in the iterable must conform to the same rules as `%fragment`. SQL boolean logic is not order-specific so this specifier takes any iterable, such as a list of a set. Order is however respected for iterables that have a defined order. Much like `%fragment` individual entries can be `None` in which case they are filtered out before emitting the final SQL. If the resulting filtered iterable has no entries, the SQL keyword `TRUE` will instead be emitted. Use this to construct narrowing queries such as `SELECT * FROM table WHERE %andlist` where each fragment filters out one or more rows. Each additional fragment added to the list will further constrain the rows found, so for logical consistency specifying zero fragments should result in all rows being selected. The resulting SQL will parenthesize all fragments, so it is safe to use this in conjunction with fragments that include `%andlist` or `%orlist` specifiers or their own.
 - `%orlist` - An iterable of fragments that will be joined together with the SQL `OR` keyword. Each entry in the iterable must conform to the same rules as `%fragment`. SQL boolean logic is not order-specific so this specifier takes any iterable, such as a list of a set. Order is however respected for iterables that have a defined order. Much like `%fragment` individual entries can be `None` in which case they are filtered out before emitting the final SQL. If the resulting filtered iterable has no entries, the SQL keyword `FALSE` will instead be emitted. Use this to construct widening queries such as `SELECT * FROM table WHERE %orlist` where each fragment matches one or more rows. Each additional fragment added to the list will further include rows, so for logical consistency specifying zero fragments should result in no rows being selected. The resulting SQL will parenthesize all fragments, so it is safe to use this in conjunction with fragments that include `%andlist` or `%orlist` specifiers of their own.

### Usage Examples

First up, we have a simple statement.

```python
from sqlfragments import statement

sql, params = statement("SELECT * FROM table").to_sqlalchemy()
```

As you might expect, this results in an identical SQL statement being emitted with an empty param object. These are suitable for passing to SQLAlchemy's `execute()` function similar to `session.execute(text(sql), params)`. On its own, this is fairly useless, but if your type checker supports `LiteralString` this will at least type check okay and prevent future modifications from introducing potential injection exploits.

Then, we have a slightly more complex query.

```python
from sqlfragments import statement

def insert(name: str) -> None:
    sql, params = statement(
        "INSERT INTO table (`name`) VALUES (%value)",
        name,
    ).to_sqlalchemy()
    session.execute(text(sql), params)
```

This does exactly what it looks like as well. Note that we have a `%value` specifier. Under the hood, this will convert the SQL to a parameterized query and the name variable will be set as the parameter. Any type that is supported by SQLAlchemy can be used here as the parameter to the `%value` specifier. Because this uses bind parameters under the hood it is safe from various classes of SQL exploits.

Alternatively, you can use named specifiers.

```python
from sqlfragments import statement

def insert(name: str) -> None:
    sql, params = statement(
        "INSERT INTO table (`name`) VALUES (%value:val)",
        val=name,
    ).to_sqlalchemy()
    session.execute(text(sql), params)
```

This doesn't have many clear advantages in the simple example presented. However, it allows you to re-use arguments for multiple specifier positions. Note that all specifiers can take an optional name, not just value specifiers.

Next, we have an example of an optional fragment.

```python
from sqlfragments import statement

def lookup(
    name: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Dict[str, object]]:
    namequery = None
    limitfragment = None
    offsetfragment = None

    if name:
        namequery = fragment("WHERE name = %value", name)
    if limit and limit > 0:
        limitfragment = fragment("LIMIT %value", limit)
    if offset and offset >= 0:
        offsetfragment = fragment("OFFSET %value", offset)

    sql, params = statement(
        "SELECT * FROM table %fragment:name %fragment:limit %fragment:offset",
        name=namequery,
        limit=limitfragment,
        offset=offsetfragment,
    )
    return list(session.execute(text(sql), params).mappings())
```

Note that while this is slightly contrived, it still shows off the power of optional fragments as well as format specifier names. Callers to lookup can pass as many or as few arguments as they want and the resulting SQL will be correct in all cases. You do not need to keep a separate SQL string and parameter map to pass to `session.execute()` and you don't have to worry about what order to concatenate SQL in. Bind parameters are still used under the hood for all values, meaning that this function is user-input safe.

Finally, we show off an example of building a more complex query from optional filters.

```python
from sqlfragments import statement

def filter(
    *,
    name: Optional[str] = None,
    ids: Optional[Iterable[int]] = None,
    minAge: Optional[int] = None,
    maxAge: Optional[int] = None,
) -> Statement:
    filters: List[Fragment] = []

    if name:
        filters.append(fragment("name = %value", name))
    if ids:
        filters.append(fragment("id IN (%inlist)", ids))
    if minAge is not None:
        filters.append(fragment("age >= %value", minAge))
    if maxAge is not None:
        filters.append(fragment("age <= %value", maxAge))

    return statement("SELECT * FROM user WHERE %andlist", filters)
```

This constructs a `filter()` function which returns a valid SQL statement that will select all rows which are constrained by zero or more of the provided filters. Note that this is logically consistent. If you specify no filters, you would expect no rows to be filtered out. Under the hood this makes a SQL statement like `SELECT * FROM user WHERE TRUE`. Each additional filter supplies additional constraints. You could select users from a list of IDs who are at least 18 years old, select users who are at most 16 with the name "John", or any other combination. Note also that when given, the ID list is inclusive, meaning if you passed a list of no IDs you would expect to get back no rows when you run the query.
