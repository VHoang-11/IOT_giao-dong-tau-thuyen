#include "motion_source.h"
#include "mpu6050.h"
#include "sim_iface.h"
#include "svmg_filter.h"

static double s_sim_abs = 0.0;       // giây mô phỏng tuyệt đối
static bool s_present = false;
static uint32_t s_sat = 0;
#ifdef SVMG_FAULT_INJECT
static char s_inj = 0;
void motion_inject(char c) { s_inj = (c == 'x') ? 0 : c; }
#endif
static const double WRAP_S = 8192.0; // giữ t của lõi nhỏ để float không mất độ phân giải (lõi xử lý quấn vòng)

void motion_init() {
  s_present = mpu_begin();
  sim_init(0xC0FFEE);
}

bool motion_sensor_present() { return s_present; }
uint32_t motion_saturation_count() { return s_sat; }
double motion_sim_time_abs() { return s_sim_abs; }
void motion_sim_clock_reset() { s_sim_abs = 0.0; sim_restart(); }

svmg_motion_sample_t acquireMotionSample(svmg_source_t mode) {
  svmg_motion_sample_t s;
  memset(&s, 0, sizeof s);
  s.source_mode = (uint8_t)mode;
  if (mode == SVMG_SRC_SIMULATION) {
    s_sim_abs += 1.0 / 20.0;
    sim_next(1.0f / 20.0f, &s);
    s.t = (float)fmod(s_sim_abs, WRAP_S);
    s.valid = 1;
  } else {
    svmg_imu_raw_t raw;
    // Thời gian thực từ millis() (đã quấn vòng); khi loop bị đứng > 0.5 s lõi sẽ phát hiện khoảng trống và khởi động lại cửa sổ.
    s.t = (float)fmod((double)millis() / 1000.0, WRAP_S);
    if (mpu_read(&raw)) {
      if (svmg_imu_raw_to_si(&raw, &s) & SVMG_IMU_F_SATURATED) s_sat++;   // bão hòa -> s.valid = 0 (đặt bởi lõi), không ghi đè
      s.t = (float)fmod((double)millis() / 1000.0, WRAP_S);
    } else {
      s.valid = 0;                    // lỗi I2C: vẫn đẩy mẫu thiếu vào lõi để đếm tỉ lệ thiếu
    }
    s.source_mode = SVMG_SRC_SENSOR;
  }
#ifdef SVMG_FAULT_INJECT      // T07/T13: chèn lỗi cảm biến khi đang chạy (chỉ có trong env esp32dev_inject)
  switch (s_inj) {
    case 'i': s.valid = 0; break;                                                   // mất I2C
    case 'z': s.ax = s.ay = s.az = s.gx = s.gy = s.gz = 0; break;                   // bus chết trả 0
    case 'n': s.ay = NAN; break;                                                    // giá trị hỏng
    case 'd': if (random(100) < 30) s.valid = 0; break;                             // mất 30 % mẫu
    case 's': s.ax = s.ay = s.az = -19.6133f; s.gx = s.gy = s.gz = -4.3633f; break; // bão hòa ±2 g / ±250 °/s
    default: break;
  }
#endif
  return s;
}

#ifdef SVMG_ACQ_TASK
#include <esp_task_wdt.h>
#include "svmg_build.h"
static QueueHandle_t s_q = nullptr;
static SemaphoreHandle_t s_i2c = nullptr;
static volatile bool s_acq_on = true;
static volatile uint32_t s_acq_overflow = 0, s_acq_qmax = 0;
static const UBaseType_t ACQ_QUEUE_LEN = 64;   // 3,2 s ở 20 Hz: dư cho một lần tính đặc trưng dài trên Wokwi (~0,35 s ở n=1800)

void motion_i2c_lock() { if (s_i2c) xSemaphoreTake(s_i2c, portMAX_DELAY); }
void motion_i2c_unlock() { if (s_i2c) xSemaphoreGive(s_i2c); }

static void acq_task(void *) {
  esp_task_wdt_add(nullptr);   // cùng watchdog 8 s như loop: task lấy mẫu treo -> khởi động lại, không để engine đứng ở trạng thái cũ
  TickType_t last = xTaskGetTickCount();
  for (;;) {
    vTaskDelayUntil(&last, pdMS_TO_TICKS(SVMG_TICK_MS));
    esp_task_wdt_reset();
    if (!s_acq_on) continue;
    motion_i2c_lock();
    svmg_motion_sample_t s = acquireMotionSample(SVMG_SRC_SENSOR);   // timestamp thật lúc đọc I2C
    motion_i2c_unlock();
    if (xQueueSend(s_q, &s, 0) != pdTRUE) s_acq_overflow = s_acq_overflow + 1;          // bỏ mẫu, không bịa: khoảng trống lộ ở mẫu kế tiếp
    UBaseType_t depth = uxQueueMessagesWaiting(s_q);
    if (depth > s_acq_qmax) s_acq_qmax = depth;
  }
}

void motion_acq_start() {
  s_i2c = xSemaphoreCreateMutex();
  s_q = xQueueCreate(ACQ_QUEUE_LEN, sizeof(svmg_motion_sample_t));
  // Cùng core với loop nhưng ưu tiên cao hơn: lấy mẫu chen ngang lúc loop đang tính đặc trưng; engine chỉ chạy ở loop.
  xTaskCreatePinnedToCore(acq_task, "svmg_acq", 4096, nullptr, 3, nullptr, ARDUINO_RUNNING_CORE);
}
void motion_acq_enable(bool on) { s_acq_on = on; if (s_q) xQueueReset(s_q); }
bool motion_acq_pop(svmg_motion_sample_t *s) { return s_q && xQueueReceive(s_q, s, 0) == pdTRUE; }
void motion_acq_stats(uint32_t *overflow, uint32_t *queue_max) { *overflow = s_acq_overflow; *queue_max = s_acq_qmax; }
#endif
