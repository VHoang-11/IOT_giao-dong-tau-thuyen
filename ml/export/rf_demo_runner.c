/* Host runner (không phải firmware) cho parity Python vs C của RF demo từ ml/export/rf_c_export.py.
 * stdin: mỗi dòng các float (hex float, nhận nan/inf) phân cách dấu phẩy; số giá trị được truyền nguyên làm n_features.
 * stdout: "status,pred,score_hex" mỗi dòng. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include RF_DEMO_HEADER

#define MAX_VALUES 64

int main(void) {
    static char line[16384];
    float x[MAX_VALUES];
    while (fgets(line, sizeof line, stdin) != NULL) {
        size_t n = 0;
        char *cursor = line;
        RF_DEMO_OUTPUT out;
        int status;
        line[strcspn(line, "\r\n")] = '\0';
        while (*cursor != '\0' && n < MAX_VALUES) {
            char *end;
            x[n++] = strtof(cursor, &end);
            if (end == cursor) { return 2; }
            cursor = (*end == ',') ? end + 1 : end;
        }
        status = RF_DEMO_PREDICT(x, n, &out);
        printf("%d,%d,%a\n", status, out.pred, (double)out.score);
    }
    return 0;
}
