import pytest
from psycopg3.adapt import Transformer, Format, Adapter, TypeCaster
from psycopg3.types.oids import builtins

TEXT_OID = builtins["text"].oid


@pytest.mark.parametrize(
    "data, format, result, type",
    [
        (None, Format.TEXT, None, "text"),
        (None, Format.BINARY, None, "text"),
        (1, Format.TEXT, b"1", "numeric"),
        ("hello", Format.TEXT, b"hello", "text"),
        ("hello", Format.BINARY, b"hello", "text"),
    ],
)
def test_adapt(data, format, result, type):
    t = Transformer()
    rv = t.adapt(data, format)
    if isinstance(rv, tuple):
        assert rv[0] == result
        assert rv[1] == builtins[type].oid
    else:
        assert rv == result


def test_adapt_connection_ctx(conn):
    Adapter.register(str, lambda s: s.encode("ascii") + b"t", conn)
    Adapter.register_binary(str, lambda s: s.encode("ascii") + b"b", conn)

    cur = conn.cursor()
    cur.execute("select %s, %b", ["hello", "world"])
    assert cur.fetchone() == ("hellot", "worldb")


def test_adapt_cursor_ctx(conn):
    Adapter.register(str, lambda s: s.encode("ascii") + b"t", conn)
    Adapter.register_binary(str, lambda s: s.encode("ascii") + b"b", conn)

    cur = conn.cursor()
    Adapter.register(str, lambda s: s.encode("ascii") + b"tc", cur)
    Adapter.register_binary(str, lambda s: s.encode("ascii") + b"bc", cur)

    cur.execute("select %s, %b", ["hello", "world"])
    assert cur.fetchone() == ("hellotc", "worldbc")

    cur = conn.cursor()
    cur.execute("select %s, %b", ["hello", "world"])
    assert cur.fetchone() == ("hellot", "worldb")


@pytest.mark.parametrize(
    "data, format, type, result",
    [
        (None, Format.TEXT, "text", None),
        (None, Format.BINARY, "text", None),
        (b"1", Format.TEXT, "int4", 1),
        (b"hello", Format.TEXT, "text", "hello"),
        (b"hello", Format.BINARY, "text", "hello"),
    ],
)
def test_cast(data, format, type, result):
    t = Transformer()
    rv = t.cast(data, builtins[type].oid, format)
    assert rv == result


def test_cast_connection_ctx(conn):
    TypeCaster.register(TEXT_OID, lambda b: b.decode("ascii") + "t", conn)
    TypeCaster.register_binary(
        TEXT_OID, lambda b: b.decode("ascii") + "b", conn
    )

    r = conn.cursor().execute("select 'hello'::text").fetchone()
    assert r == ("hellot",)
    r = conn.cursor(binary=True).execute("select 'hello'::text").fetchone()
    assert r == ("hellob",)


def test_cast_cursor_ctx(conn):
    TypeCaster.register(TEXT_OID, lambda b: b.decode("ascii") + "t", conn)
    TypeCaster.register_binary(
        TEXT_OID, lambda b: b.decode("ascii") + "b", conn
    )

    cur = conn.cursor()
    TypeCaster.register(TEXT_OID, lambda b: b.decode("ascii") + "tc", cur)
    TypeCaster.register_binary(
        TEXT_OID, lambda b: b.decode("ascii") + "bc", cur
    )

    r = cur.execute("select 'hello'::text").fetchone()
    assert r == ("hellotc",)
    cur.binary = True
    r = cur.execute("select 'hello'::text").fetchone()
    assert r == ("hellobc",)

    cur = conn.cursor()
    r = cur.execute("select 'hello'::text").fetchone()
    assert r == ("hellot",)
    cur.binary = True
    r = cur.execute("select 'hello'::text").fetchone()
    assert r == ("hellob",)


@pytest.mark.xfail
@pytest.mark.parametrize(
    "sql, obj",
    [("'{hello}'::text[]", ["helloc"]), ("row('hello'::text)", ("helloc",))],
)
@pytest.mark.parametrize("fmt_out", [Format.TEXT, Format.BINARY])
def test_cast_cursor_ctx_nested(conn, sql, obj, fmt_out):
    cur = conn.cursor(binary=fmt_out == Format.BINARY)
    TypeCaster.register(
        TEXT_OID, lambda b: b.decode("ascii") + "c", cur, format=fmt_out
    )
    cur.execute(f"select {sql}")
    res = cur.fetchone()[0]
    assert res == obj
