#include <cstdio>
#include <cstring>
#include "svmg_engine.h"
#include "svmg_testutil.h"
#include "msg.h"

int main() {
  svmg_config_t cfg;
  svmg_config_default(&cfg, SVMG_MODEL_BASELINE_B);
  svmg_engine_t e;
  svmg_engine_out_t out;
  svmg_engine_init(&e, &cfg);
  for (int i = 1; i <= 4000; ++i) {
    auto s = st_sample(i * .05, 0, 0, 0, 0);
    if ((i - 1) % 10 < 4) s.valid = 0;
    svmg_engine_push(&e, &s, i * 50, &out);
  }
  std::printf("DROP_40_PERCENT: invalid=%lu/%lu missing60=%.3f status=%d class=%d (OK=0 NORMAL=0)\n",
    (unsigned long)e.pipe.cnt_invalid, (unsigned long)e.pipe.cnt_in,
    (double)e.dec.feat.missing_ratio_60, e.dec.status, e.dec.cls_primary);

  svmg_engine_restart_signal(&e);
  svmg_alarm_out_t lights;
  svmg_alarm_outputs(&e.alarm, 200000, &lights);
  std::printf("MODE_RESET: decision_status=%d alarm_status=%d green=%d (UNKNOWN=1 ON=1)\n",
    e.dec.status, e.alarm.status, lights.led_g);

  svmg_alarm_cfg_t ac;
  svmg_alarm_default_cfg(&ac);
  svmg_alarm_t a;
  svmg_alarm_init(&a, &ac);
  svmg_event_t ev[SVMG_ALARM_MAX_EVENTS];
  svmg_alarm_in_t in = {};
  in.cls = SVMG_HIGH_ROLL; in.status = SVMG_ST_OK;
  svmg_alarm_update(&a, &in, ev);
  svmg_alarm_update(&a, &in, ev);
  in.cls = SVMG_UNKNOWN; in.status = SVMG_ST_UNKNOWN;
  for (int i = 0; i < 20; ++i) svmg_alarm_update(&a, &in, ev);
  in.cls = SVMG_HIGH_ROLL; in.status = SVMG_ST_OK;
  svmg_alarm_update(&a, &in, ev);
  std::printf("NONCONSECUTIVE: HIGH,HIGH,20xUNKNOWN,HIGH => level=%d streak=%u (WARNING=2)\n", a.level, a.streak);

  in.cls = SVMG_NORMAL; in.status = SVMG_ST_OK;
  for (int i = 0; i < 5; ++i) svmg_alarm_update(&a, &in, ev);
  in.cls = SVMG_UNKNOWN; in.status = SVMG_ST_UNKNOWN;
  for (int i = 0; i < 20; ++i) svmg_alarm_update(&a, &in, ev);
  in.cls = SVMG_NORMAL; in.status = SVMG_ST_OK;
  svmg_alarm_update(&a, &in, ev);
  std::printf("NONCONTINUOUS_CLEAR: 5xNORMAL,20xUNKNOWN,1xNORMAL => level=%d (NORMAL=0)\n", a.level);

  svmg_engine_init(&e, &cfg);
  svmg_imu_raw_t raw = {};
  raw.az = 16384; raw.gz = 32767;
  unsigned saturation = 0;
  for (int i = 1; i <= 4000; ++i) {
    svmg_motion_sample_t s = {};
    saturation += !!(svmg_imu_raw_to_si(&raw, &s) & SVMG_IMU_F_SATURATED);
    s.t = i * .05f;
    svmg_engine_push(&e, &s, i * 50, &out);
  }
  std::printf("GYRO_Z_SATURATED: flagged=%u status=%d class=%d invalid=%lu (OK=0 NORMAL=0)\n",
    saturation, e.dec.status, e.dec.cls_primary, (unsigned long)e.pipe.cnt_invalid);

  const char *j = "{\"cmd_id\":\"age-invalid\",\"cmd\":\"set_profile\",\"ttl_s\":30,\"age_s\":-1,\"params\":{\"profile\":\"SENSITIVE\"}}";
  svmg_cmd_t cmd;
  bool parsed = msg_parse_cmd(j, std::strlen(j), &cmd);
  std::printf("INVALID_COMMAND_AGE: parsed=%d age_s=%u ttl_s=%u\n", parsed, cmd.age_s, cmd.ttl_s);
  return 0;
}
