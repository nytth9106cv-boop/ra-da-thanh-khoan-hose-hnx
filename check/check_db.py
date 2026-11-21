import sqlite3

con = sqlite3.connect("data/liquidity.db")
for (t,) in con.execute("select name from sqlite_master where type='table'").fetchall():
    cols = [r[1] for r in con.execute(f"pragma table_info({t})")]
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    print(t, n, "dòng:", cols)