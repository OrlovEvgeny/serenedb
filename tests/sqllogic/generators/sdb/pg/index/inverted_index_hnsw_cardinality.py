from sqllogic_gen import Test

t = Test("HNSW returns the requested number of rows when quantized vectors coincide.")

for quant in ("none", "sq8", "usq8", "sq4", "usq4"):
    t.part()
    t.table("hnsw_count", "id INTEGER PRIMARY KEY, emb FLOAT[2]")
    t.statement(f"CREATE INDEX hnsw_count_idx ON hnsw_count USING inverted "
                f"(id, emb hnsw(metric = 'l2', quant = '{quant}')) "
                "WITH (refresh_interval = 0, compaction_interval = 0)")
    t.statement("INSERT INTO hnsw_count VALUES (0, NULL)")
    t.statement("INSERT INTO hnsw_count SELECT i, [i, i + 1]::FLOAT[2] FROM range(1, 201) r(i)")
    t.statement("INSERT INTO hnsw_count VALUES "
                "(203, [1e17, 0]::FLOAT[2]), (204, [-1e17, 0]::FLOAT[2])")
    t.refresh("hnsw_count")
    for width in (0, 4):
        t.statement(f"SET sdb_ann_rescore_width = {width}")
        for k in (100, 202, 300):
            t.expect("SELECT count(*) AS n, count(DISTINCT id) AS unique_ids, "
                     "count(*) FILTER (WHERE id = 0) AS null_vectors "
                     "FROM (SELECT id FROM hnsw_count_idx "
                     f"ORDER BY emb <-> [0, 0]::FLOAT[2] LIMIT {k}) q",
                     ["n", "unique_ids", "null_vectors"], [[min(k, 202), min(k, 202), 0]])
    t.statement("SET sdb_ann_force_exact = true")
    t.expect("SELECT count(*) AS n FROM (SELECT id FROM hnsw_count_idx "
             "ORDER BY emb <-> [0, 0]::FLOAT[2] LIMIT 300) q", ["n"], [[202]])
    t.statement("RESET sdb_ann_force_exact")
    t.statement("RESET sdb_ann_rescore_width")

for quant in ("none", "sq8", "usq8", "sq4", "usq4"):
    t.part()
    t.table("hnsw_equal", "id INTEGER PRIMARY KEY, emb FLOAT[2]")
    t.statement(f"CREATE INDEX hnsw_equal_idx ON hnsw_equal USING inverted "
                f"(id, emb hnsw(metric = 'l2', quant = '{quant}')) "
                "WITH (refresh_interval = 0, compaction_interval = 0)")
    t.statement("INSERT INTO hnsw_equal VALUES (0, NULL)")
    t.statement("INSERT INTO hnsw_equal SELECT i, [1, 1]::FLOAT[2] FROM range(1, 601) r(i)")
    t.refresh("hnsw_equal")
    for width in (0, 4):
        t.statement(f"SET sdb_ann_rescore_width = {width}")
        for k in (100, 300, 700):
            t.expect("SELECT count(*) AS n, count(DISTINCT id) AS unique_ids, "
                     "count(*) FILTER (WHERE id = 0) AS null_vectors "
                     "FROM (SELECT id FROM hnsw_equal_idx "
                     f"ORDER BY emb <-> [0, 0]::FLOAT[2] LIMIT {k}) q",
                     ["n", "unique_ids", "null_vectors"], [[min(k, 600), min(k, 600), 0]])
    t.statement("DELETE FROM hnsw_equal WHERE id BETWEEN 1 AND 20")
    t.refresh("hnsw_equal")
    t.expect("SELECT count(*) AS n, count(*) FILTER (WHERE id <= 20) AS deleted FROM "
             "(SELECT id FROM hnsw_equal_idx ORDER BY emb <-> [0, 0]::FLOAT[2] LIMIT 700) q",
             ["n", "deleted"], [[580, 0]])
    t.statement("RESET sdb_ann_rescore_width")

t.part()
t.table("hnsw_segments", "id INTEGER PRIMARY KEY, emb FLOAT[2]")
t.statement("CREATE INDEX hnsw_segments_idx ON hnsw_segments USING inverted "
            "(id, emb hnsw(metric = 'l2', quant = 'none')) "
            "WITH (refresh_interval = 0, compaction_interval = 0)")
t.statement("INSERT INTO hnsw_segments SELECT i, [i, 0]::FLOAT[2] FROM range(1, 601) r(i)")
t.refresh("hnsw_segments")
t.statement("INSERT INTO hnsw_segments VALUES (1000, NULL)")
t.refresh("hnsw_segments")
t.statement("SET sdb_hnsw_ef_search = 1")
t.expect("SELECT count(*) AS n, min(id) AS first, max(id) AS last FROM "
         "(SELECT id FROM hnsw_segments_idx ORDER BY emb <-> [0, 0]::FLOAT[2] LIMIT 100) q",
         ["n", "first", "last"], [[100, 1, 100]])
t.expect("SELECT count(*) AS n, min(id) AS first, max(id) AS last FROM "
         "(SELECT id FROM hnsw_segments_idx ORDER BY emb <-> [0, 0]::FLOAT[2] "
         "LIMIT 50 OFFSET 100) q", ["n", "first", "last"], [[50, 101, 150]])
t.statement("RESET sdb_hnsw_ef_search")

for metric, operator in (("l2", "<->"), ("l1", "<+>"), ("ip", "<#>"), ("cosine", "<=>")):
    t.part()
    t.table("hnsw_metric", "id INTEGER PRIMARY KEY, grp INTEGER, carried INTEGER, "
            "lookup INTEGER, emb FLOAT[2]")
    t.statement(f"CREATE INDEX hnsw_metric_idx ON hnsw_metric USING inverted "
                f"(id, grp, emb hnsw(metric = '{metric}', quant = 'none')) INCLUDE (carried) "
                "WITH (refresh_interval = 0, compaction_interval = 0)")
    nearest = f"SELECT id FROM hnsw_metric_idx ORDER BY emb {operator} [1, 0]::FLOAT[2]"
    t.expect(f"SELECT count(*) AS n FROM ({nearest} LIMIT 100) q", ["n"], [[0]])
    t.statement("INSERT INTO hnsw_metric VALUES (0, 0, 0, 0, NULL)")
    t.refresh("hnsw_metric")
    t.expect(f"SELECT count(*) AS n FROM ({nearest} LIMIT 100) q", ["n"], [[0]])
    t.statement("INSERT INTO hnsw_metric SELECT i, i % 2, i % 3, i % 5, [1, 1]::FLOAT[2] "
                "FROM range(1, 201) r(i)")
    t.refresh("hnsw_metric")
    t.expect(f"SELECT count(*) AS n FROM ({nearest} LIMIT 1) q", ["n"], [[1]])
    t.expect(f"SELECT count(*) AS n FROM ({nearest} LIMIT 100) q", ["n"], [[100]])
    for predicate, expected in (("grp = 1", 100), ("carried = 1", 67), ("lookup = 1", 40)):
        t.expect("SELECT count(*) AS n, count(DISTINCT id) AS unique_ids FROM "
                 f"(SELECT id FROM hnsw_metric_idx WHERE {predicate} "
                 f"ORDER BY emb {operator} [1, 0]::FLOAT[2] LIMIT 100) q",
                 ["n", "unique_ids"], [[expected, expected]])

t.write()
