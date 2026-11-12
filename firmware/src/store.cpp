#include "store.h"
#include <Preferences.h>
#include <string.h>
#include <stddef.h>

namespace {
struct Blob {
  uint32_t magic;
  svmg_config_t cfg;
  uint16_t crc;
  uint16_t pad;
};
const uint32_t MAGIC = 0x53564D47u;   // "SVMG"
const char *NS = "svmg";

uint16_t blob_crc(const Blob &b) { return svmg_crc16_ccitt(&b, offsetof(Blob, crc)); }
}  // namespace

bool store_load(svmg_config_t *out, svmg_model_t def) {
  svmg_config_default(out, def);
  Preferences p;
  if (!p.begin(NS, true)) return false;
  Blob b; memset(&b, 0, sizeof b);
  size_t n = p.getBytes("cfg", &b, sizeof b);
  p.end();
  if (n != sizeof b || b.magic != MAGIC || b.crc != blob_crc(b)) return false;
  if (svmg_config_validate(&b.cfg) != SVMG_R_OK) return false;          // cấu hình hỏng/ngoài biên -> không dùng
  *out = b.cfg;
  return true;
}

bool store_save(const svmg_config_t *cfg) {
  Blob b; memset(&b, 0, sizeof b);
  b.magic = MAGIC; b.cfg = *cfg; b.crc = blob_crc(b);
  Preferences p;
  if (!p.begin(NS, false)) return false;
  size_t n = p.putBytes("cfg", &b, sizeof b);                            // một khóa NVS = ghi nguyên tử
  p.end();
  return n == sizeof b;
}

uint32_t store_next_boot_count() {
  Preferences p;
  if (!p.begin(NS, false)) return 0;
  uint32_t c = p.getUInt("boots", 0) + 1;
  p.putUInt("boots", c);
  p.end();
  return c;
}
