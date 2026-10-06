---
title: YAML
split: headings
sidebar_position: 8
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

SereneDB bundles the community [yaml extension](https://github.com/teaguesterling/duckdb_yaml)
and yaml-cpp. No extension installation is needed. `read_yaml` accepts a file path,
a glob such as `manifests/*.yaml`, or a list of paths.

<SqlLogicTest id="data_import_and_export/yaml/read_documents" />

Each non-null YAML document separated by `---` produces one row. Empty,
comment-only and explicit null documents are skipped. Mapping keys become columns.
Scalar and sequence documents are returned in a single `value` column. Use
`expand_root_sequence = true` to turn a root sequence of mappings into rows,
including files written with `COPY TO ... (FORMAT yaml, LAYOUT sequence)`.
Files are opened through DuckDB's filesystem, including configured remote stores.

## Scalars and JSON compatibility

Plain scalars follow the boolean and number spellings of the
[YAML 1.2 JSON schema](https://yaml.org/spec/1.2.2/#102-json-schema).
Unmatched scalars become strings, and yaml-cpp's null spellings also apply:

| YAML value | JSON representation |
| --- | --- |
| `true`, `false` | Boolean |
| `no`, `yes`, `on`, `off`, `y`, `True`, `TRUE` | String |
| `1`, `-12`, `-0`, `1.10`, `1e3` | Number |
| `~`, `null`, `Null`, `NULL`, an empty value | Null |
| `1:20`, `012`, `0x10`, `.inf`, `.nan` | String |
| `"true"`, `"1.10"`, `!!str 123`, `""` | String |

Quoted scalars and explicit `!!str` tags remain SQL strings during inference,
including compose ports such as `"22:22"` and quoted dates. Explicit `columns`
can still request a different SQL type. Unquoted strings can infer temporal or
UUID types: `1:20` becomes `TIME`, ISO dates become `DATE`, and timestamps ending
in `Z` become `TIMESTAMPTZ`. Regional dates such as `01/15/2024` stay strings.

JSON's schema inference determines SQL types across sampled documents, including
nested structures, lists, missing fields, numeric widening and JSON fallback for
incompatible types. A mixture of mapping and scalar documents produces one JSON
`value` column. A mapping with 200 or more keys can infer `MAP` and therefore a
single `value` column; field overrides in `columns` do not undo that collapse.

Use `columns` to preserve numeric source text such as `version: 1.10`, or to read
large integers as `HUGEINT` or `DECIMAL` without a floating-point conversion:

<SqlLogicTest id="data_import_and_export/yaml/preserve_version" />

<SqlLogicTest id="data_import_and_export/yaml/scalars" />

`sample_size` and `maximum_sample_files` control schema sampling. A type mismatch
after the sample raises an error by default. With `ignore_errors = true`, invalid
documents and rows that fail conversion are skipped; valid rows elsewhere in the
same file remain. Files that cannot be opened are skipped as a whole.

## Anchors and merge keys

Anchors and aliases are expanded, including in extraction and conversion functions.
An unquoted `<<` merges a mapping or a sequence of mappings. Explicit keys override
merged keys regardless of their position; earlier mappings in a merge sequence
take precedence. Quoted `"<<"` is a normal key. Repeated merge keys, null keys and
non-scalar mapping keys are rejected. Mapping keys must be unique ignoring case.
Keys that differ only in case across documents are also unsupported.

Cycles are rejected before expansion. The expanded tree is limited to one million
nodes and 64 MiB of payload, and to 64 times its distinct input payload (with a
64 KiB allowance for small documents). A depth limit also applies. These are
process-wide limits; SereneDB does not register the extension's SQL setters for
limits or default output style. These allocations are outside `memory_limit`.
Errors include source locations when available.

## Other functions and limitations

The bundled extension also provides `read_yaml_objects`, `parse_yaml`,
`read_yaml_frontmatter`, `yaml_extract`, `yaml_to_json`, and `COPY TO ... (FORMAT yaml)`.
`read_yaml_frontmatter` rejects malformed frontmatter by default; with
`ignore_errors = true`, it skips the affected file.

The community reader reads each file into memory and uses its existing globbing
implementation. It does not yet provide the JSON reader's `filename`,
`hive_partitioning`, `union_by_name`, or `file_row_number` parameters. A shared
MultiFileReader implementation and view-index fast path are separate follow-ups.
