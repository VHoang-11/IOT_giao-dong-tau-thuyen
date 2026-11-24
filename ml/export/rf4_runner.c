/* Host runner (không phải firmware) cho parity Python vs C của RF bốn lớp (ml/export/rf_c_export.generate_model_h).
 * stdin: mỗi dòng các float (hex float, nhận nan/inf) phân cách dấu phẩy; số giá trị được truyền nguyên làm n.
 * stdout: "pred,p0,p1,p2,p3,pred_conf,conf" (xác suất ở dạng hex float). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include RF4_HEADER

#define MAX_VALUES 64

int main(void) {
    static char line[16384];
    float x[MAX_VALUES], p[SVMG_MODEL_N_CLASSES], conf;
    while (fgets(line, sizeof line, stdin) != NULL) {
        int n = 0, pred, pred_conf;
        char *cursor = line;
        line[strcspn(line, "\r\n")] = '\0';
        while (*cursor != '\0' && n < MAX_VALUES) {
            char *end;
            x[n++] = strtof(cursor, &end);
            if (end == cursor) { return 2; }
            cursor = (*end == ',') ? end + 1 : end;
        }
        pred = model_predict_proba(x, n, p);
        pred_conf = model_predict_conf(x, n, &conf);
        if (pred_conf != model_predict(x, n)) { return 3; }
        printf("%d,%a,%a,%a,%a,%d,%a\n", pred, (double)p[0], (double)p[1], (double)p[2], (double)p[3], pred_conf, (double)conf);
    }
    return 0;
}
