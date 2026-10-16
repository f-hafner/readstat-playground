#include "readstat.h"
#include <stdio.h>
#include <string.h>

// Adapted from: https://github.com/WizardMac/ReadStat/blob/dev/README.md

#define MAX_SKIP_VARS 5

struct MyConfig {
    const char *skip_vars[MAX_SKIP_VARS];
    int skip_var_count;
};

static int should_skip(const char *name, const struct MyConfig *cfg) {
    for (int i = 0; i < cfg->skip_var_count; i++) {
        if (strcmp(name, cfg->skip_vars[i]) == 0) {
            return 1;
        }
    }
    return 0;
}

int handle_variable(int index, readstat_variable_t *variable, 
    const char *val_labels, void *ctx) {
    struct MyConfig *my_config = (struct MyConfig *)ctx;

    const char *var_name = readstat_variable_get_name(variable); 

    if (should_skip(var_name, my_config)) {
        return READSTAT_HANDLER_SKIP_VARIABLE;
    }
    int var_index = readstat_variable_get_index_after_skipping(variable);

    if (var_index > 0) {
        printf("\t");
    }
    printf("%s", var_name);

    return READSTAT_HANDLER_OK;
}

int handle_value(int obs_index, readstat_variable_t *variable, readstat_value_t value, void *ctx) {
    struct MyConfig *my_config = (struct MyConfig *)ctx;
    
    int var_index = readstat_variable_get_index_after_skipping(variable);
    if (var_index == 0) {
        printf("\n");
    } else {
        printf("\t");
    }

    readstat_type_t type = readstat_value_type(value);
    if (!readstat_value_is_system_missing(value)) { // print the value to console
        if (type == READSTAT_TYPE_STRING) {
            printf("%s", readstat_string_value(value));
        } else if (type == READSTAT_TYPE_INT8) {
            printf("%hhd", readstat_int8_value(value));
        } else if (type == READSTAT_TYPE_INT16) {
            printf("%hd", readstat_int16_value(value));
        } else if (type == READSTAT_TYPE_INT32) {
            printf("%d", readstat_int32_value(value));
        } else if (type == READSTAT_TYPE_FLOAT) {
            printf("%f", readstat_float_value(value));
        } else if (type == READSTAT_TYPE_DOUBLE) {
            printf("%lf", readstat_double_value(value));
        }
    }

    return READSTAT_HANDLER_OK;
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        printf("Usage: %s <filename>\n", argv[0]);
        return 1;
    }

    struct MyConfig myconfig = {
        .skip_vars = {"sector", "wage"}, 
        .skip_var_count = 2,
        //.skip_vars = {"sector", "null_col", "wage", "person_id"}, 
        //.skip_var_count = 4,
    };
    readstat_error_t error = READSTAT_OK;
    readstat_parser_t *parser = readstat_parser_init();
    readstat_set_variable_handler(parser, &handle_variable);
    readstat_set_value_handler(parser, &handle_value);
    readstat_set_row_limit(parser, 10);
    //readstat_set_row_limit(parser, 1000000);

    error = readstat_parse_dta(parser, argv[1], &myconfig);
    printf("\n");

    readstat_parser_free(parser);

    if (error != READSTAT_OK) {
        printf("Error processing %s: %d\n", argv[1], error);
        return 1;
    }
    return 0;
}
