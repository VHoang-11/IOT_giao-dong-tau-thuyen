// Đọc mỗi dòng stdin là một JSON, in CRC chuẩn tắc (4 hex) hoặc "ERR". Dùng bởi crosscheck_crc.py.
#include <cstdio>
#include <cstring>
#include "msg.h"

int main() {
  static char line[2048];
  while (std::fgets(line, sizeof line, stdin)) {
    size_t n = std::strlen(line);
    while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
    uint16_t crc;
    if (msg_config_canonical_crc(line, n, &crc)) std::printf("%04x\n", crc); else std::printf("ERR\n");
  }
  return 0;
}
