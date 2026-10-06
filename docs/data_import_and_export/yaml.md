---
title: YAML
sidebar_position: 8
---

SereneDB bundles the community [yaml extension](https://github.com/teaguesterling/duckdb_yaml)
and yaml-cpp. No extension installation is needed.

```sql
SELECT * FROM read_yaml('config.yaml');
SELECT * FROM read_yaml('manifests/*.yaml');
SELECT * FROM read_yaml(['config.yaml', 'overrides.yml']);
```

Each YAML document separated by `---` produces one row. Mapping keys become
columns. Scalar and sequence documents are returned in a single `value` column.
Use `expand_root_sequence = true` to turn a root sequence of mappings into rows.
Files are opened through DuckDB's filesystem, including configured remote stores.

## Scalars and JSON compatibility

The reader uses a JSON-compatible scalar rule, rather than YAML 1.1 implicit
boolean and numeric resolution:

| YAML value | JSON representation |
| --- | --- |
| `true`, `false` | Boolean |
| `no`, `yes`, `on`, `off`, `NO` | String |
| `1`, `-12`, `1.10`, `1e3` | Number |
| `~`, `null`, `Null`, `NULL`, an empty value | Null |
| `1:20`, `012`, `0x10`, `.inf`, `.nan` | String |
| `"true"`, `"1.10"`, `!!str 123`, `""` | String |

Quoted scalars and explicit string tags preserve their string representation.
JSON's schema inference then determines SQL types across sampled documents,
including nested structures, lists, missing fields, numeric widening and JSON
fallback for incompatible types. The same JSON transformation code produces the
SQL values. As with JSON, strings can infer temporal or UUID SQL types. For example,
`1:20` becomes SQL `TIME` (`01:20:00`), never the YAML 1.1 base-60 integer `80`. Dates and
timestamps use strict casts; regional date-format guessing is disabled, so
`01/15/2024` and `15.01.2024` stay strings. ISO dates can infer `DATE`.

```sql
SELECT * FROM read_yaml('config.yaml', columns = {'version': 'VARCHAR'});
SELECT yaml_to_json('country: no'); -- {"country":"no"}
```

`sample_size` and `maximum_sample_files` control schema sampling. Types appearing
only after the sample may require explicit `columns`. `ignore_errors = true`
allows invalid input to be skipped.

## Anchors and merge keys

Anchors and aliases are expanded. An unquoted `<<` merges a mapping or a sequence
of mappings. Explicit keys override merged keys regardless of their position;
earlier mappings in a merge sequence take precedence. Quoted `"<<"` is a normal
key. Non-scalar mapping keys are rejected. As with JSON schema inference,
duplicate mapping keys are rejected when reading records.

Expansion has the extension's bounded depth and node budgets. Cyclic aliases and
excessive alias expansion fail with an error. Syntax and merge errors include the
file name and the parser's one-based line and column.

## Other functions and limitations

The bundled extension also provides `read_yaml_objects`, `parse_yaml`,
`read_yaml_frontmatter`, `yaml_extract`, `yaml_to_json`, and `COPY TO ... (FORMAT yaml)`.

The community reader reads each file into memory and uses its existing globbing
implementation. It does not yet provide the JSON reader's `filename`,
`hive_partitioning`, `union_by_name`, or `file_row_number` parameters. A shared
MultiFileReader implementation is a separate follow-up.
