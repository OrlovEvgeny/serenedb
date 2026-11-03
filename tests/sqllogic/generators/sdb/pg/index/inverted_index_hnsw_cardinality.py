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

t.write()
