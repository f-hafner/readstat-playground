# DuckDB C API — Entry Points Summary

Two headers in `duckdb_capi/`:

- **`duckdb.h`** — the C API (functions named `duckdb_*`).
- **`duckdb_extension.h`** — same API as a `duckdb_ext_api` struct of function pointers + `#define duckdb_x duckdb_ext_api.duckdb_x`, version guards, and the load hook. Extensions use this because they have no link-time DuckDB symbols.

## Entry points by workflow

**Database / connection**
```c
duckdb_open(path, &db);              duckdb_open_ext(path,&db,cfg,&err);
duckdb_connect(db, &con);            duckdb_disconnect(&con);
duckdb_close(&db);
duckdb_interrupt(con);               duckdb_query_progress(con);
```

**Direct query** (materialized result)
```c
duckdb_query(con, "SELECT 42", &res);
duckdb_column_count(&res); duckdb_column_name(&res,0); duckdb_column_logical_type(&res,0);
duckdb_fetch_chunk(res);   // or duckdb_stream_fetch_chunk → duckdb_data_chunk
duckdb_destroy_result(&res);
```

**Prepare / bind / execute** (parameterized)
```c
duckdb_prepare(con, "SELECT $1", &stmt);
duckdb_nparams(stmt); duckdb_param_type(stmt,0); duckdb_bind_int32(stmt,1,7);
duckdb_bind_value/bind_varchar/.../bind_null;
duckdb_execute_prepared(stmt,&res);  duckdb_destroy_prepare(&stmt);
```

**Pending / task-based execution** (async, cancellable)
```c
duckdb_pending_prepared(stmt,&pending);
while (duckdb_pending_execute_task(pending) == DUCKDB_PENDING_RESULT_NOT_READY) {}
duckdb_execute_pending(pending,&res);  duckdb_destroy_pending(&pending);
```
Plus `duckdb_execute_tasks`, `duckdb_execute_n_tasks_state`, `duckdb_task_state_is_finished`.

**Arrow interop**
```c
duckdb_query_arrow(con,q,&ar);  duckdb_query_arrow_schema(ar,&schema);  duckdb_query_arrow_array(ar,&arr);
duckdb_arrow_scan(con,"t",...); duckdb_create_arrow(con,name,&sch,&arr);  duckdb_data_chunk_to_arrow(...);
```

**Value & type constructors / accessors** (`create_*`, `get_*`, `to_*/from_*`)
```c
duckdb_create_int32(5); duckdb_create_list_type(child); duckdb_create_struct_type(...);
duckdb_value_int32(&v); duckdb_get_value_type(v); duckdb_to_date(d);
```

**Appender** (bulk insert)
```c
duckdb_appender_create(con,schema,table,&app);
duckdb_append_int64(app, 1); duckdb_append_varchar(app,"x");
duckdb_appender_end_row(app);  duckdb_appender_flush(app); duckdb_appender_close(app);
```

**Extension registration** (the plugin surface)
```c
duckdb_register_scalar_function(con, fn);     // + scalar_function_* setters
duckdb_register_table_function(con, fn);      // + table_function_*, bind_*, init_*
duckdb_register_aggregate_function(_set);
duckdb_register_cast_function / register_copy_function / register_logical_type /
duckdb_register_config_option / duckdb_register_log_storage;
duckdb_register_replacement_scan(con, fn, extra);
duckdb_register_arrow(con, "name", &scan);
```

**File system / handles**
```c
duckdb_get_file_system(db,&fs); duckdb_file_system_open(fs,path,&fh);
duckdb_file_handle_read/seek/sync; duckdb_destroy_file_handle(&fh);
```

**Metadata / misc**
```c
duckdb_table_description_create(con,schema,table,&td);   // + _get_column_*
duckdb_get_table_names(con,q,qualified);
duckdb_get_profiling_info(con); duckdb_config_count(); duckdb_library_version();
```

## Extension entry hook (`duckdb_extension.h`)
```c
#define DUCKDB_EXTENSION_API_VERSION_MAJOR 1 / MINOR 5 / PATCH 6
DUCKDB_EXTENSION_MAIN   // generates the C++ init symbol
DUCKDB_EXTENSION_MAIN_C // generates the C  init symbol (DUCKDB_EXTENSION_API_INIT)
```
Load path: DuckDB resolves `<name>_init_c_api(info, access)` → fills `duckdb_ext_api` → all `duckdb_*` names alias into it.
