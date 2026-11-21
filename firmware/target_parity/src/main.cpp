#include <Arduino.h>
#include <esp_task_wdt.h>
#include <esp_timer.h>
#include <math.h>
#include <limits>
#include <string.h>
#include "svmg_features.h"

static_assert(sizeof(float) == 4, "HV01 requires IEEE-754 float32");
static_assert(std::numeric_limits<float>::is_iec559, "HV01 requires IEEE-754 floats");
static_assert(SVMG_N_FEATURES == 23, "HV01 requires the 23-feature schema");
#if !defined(__BYTE_ORDER__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "HV01 wire transport requires a little-endian target"
#endif

namespace {
constexpr uint8_t VERSION = 1, SYNC0 = 0x53, SYNC1 = 0x56;
constexpr uint16_t MAX_PAYLOAD = 384;
constexpr uint8_t MAX_BATCH = 32, MAX_ENDPOINTS = 32;
constexpr uint32_t MAX_SAMPLES = 4096, FRAME_TIMEOUT_MS = 5000;
constexpr const char *SEMANTIC_VERSION = "svmg-angle23-semantics-1.0.0";
constexpr const char *VALIDITY_VERSION = "svmg-angle23-validity-1.0.0";
constexpr const char *PARITY_SCHEMA = "svmg-angle23-0.2.0-proposal";
enum Type : uint8_t { RUN_BEGIN=1, CASE_BEGIN, SAMPLES, CASE_END, RUN_END,
                      HELLO=0x80, ACK, RESULT, CASE_DONE, RUN_DONE, ERROR_FRAME=0x8f };
enum Error : uint8_t { BAD_FRAME=1, BAD_CRC, BAD_VERSION, BAD_SEQUENCE, BAD_LENGTH,
                       BAD_STATE, BAD_PAYLOAD, BAD_SAMPLE_INDEX, BAD_CASE_CRC,
                       INCOMPLETE_CASE, FRAME_TIMEOUT };
struct Frame { uint8_t version, type; uint32_t seq; uint16_t len; uint8_t data[MAX_PAYLOAD]; };
enum State : uint8_t { WAIT_RUN, IN_RUN, IN_CASE, FINISHED, FAILED };

static svmg_window_t window_state;
static svmg_features_t features;
static float feature_values[SVMG_N_FEATURES];
static Frame frame;
static uint8_t tx_data[MAX_PAYLOAD], header[8];
static uint32_t rx_seq=0, tx_seq=0, samples_received=0, case_sample_count=0, case_count=0, cases_done=0;
static uint32_t expected_samples_crc=0, sample_crc=0, input_sha[8], manifest_sha[8];
static uint32_t endpoints[MAX_ENDPOINTS];
static uint8_t endpoint_count=0, endpoint_pos=0;
static uint16_t expected_cases=0;
static char run_id[33], case_id[49];
static State state=WAIT_RUN;
static uint32_t last_hello_ms=0;

uint32_t get32(const uint8_t *p) { return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24); }
uint16_t get16(const uint8_t *p) { return (uint16_t)(p[0]|((uint16_t)p[1]<<8)); }
void put32(uint8_t *p,uint32_t v) { for(int i=0;i<4;i++) p[i]=(uint8_t)(v>>(8*i)); }
void put16(uint8_t *p,uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
uint32_t crc_step(uint32_t c,uint8_t b) {
  c^=b; for(int k=0;k<8;k++) c=(c>>1)^((c&1)?0xedb88320u:0); return c;
}
uint32_t crc_bytes(uint32_t c,const uint8_t *p,size_t n) { while(n--) c=crc_step(c,*p++); return c; }
uint32_t crc_done(uint32_t c) { return c^0xffffffffu; }
uint32_t feature_order_crc() {
  uint32_t c=0xffffffffu;
  for(int i=0;i<SVMG_N_FEATURES;i++) { const char *p=SVMG_FEATURE_NAMES[i]; while(*p)c=crc_step(c,(uint8_t)*p++); c=crc_step(c,0); }
  return crc_done(c);
}
bool id_ok(const uint8_t *p,uint8_t n,uint8_t cap) {
  if(!n||n>cap)return false;
  for(uint8_t i=0;i<n;i++) if(!((p[i]>='A'&&p[i]<='Z')||(p[i]>='a'&&p[i]<='z')||
      (p[i]>='0'&&p[i]<='9')||p[i]=='_'||p[i]=='-'||p[i]=='.')) return false;
  return true;
}
uint16_t put_string(uint8_t *p,const char *s) {
  size_t n=strlen(s); if(n>250)n=250; p[0]=(uint8_t)n; memcpy(p+1,s,n); return (uint16_t)(n+1);
}
void send_frame(uint8_t type,const uint8_t *p,uint16_t n) {
  if(n>MAX_PAYLOAD){state=FAILED;return;}
  uint8_t h[8]; h[0]=VERSION; h[1]=type; put32(h+2,tx_seq++); put16(h+6,n);
  uint32_t c=crc_done(crc_bytes(0xffffffffu,h,sizeof h)); c=crc_done(crc_bytes(c^0xffffffffu,p,n));
  Serial.write(SYNC0); Serial.write(SYNC1); Serial.write(h,sizeof h); if(n)Serial.write(p,n);
  uint8_t cb[4]; put32(cb,c); Serial.write(cb,sizeof cb);
}
void send_ack(uint32_t host_seq,uint8_t code) {
  put32(tx_data,host_seq); tx_data[4]=code; put32(tx_data+5,samples_received); send_frame(ACK,tx_data,9);
}
void fail(uint8_t code,uint32_t host_seq) {
  if(state==FAILED)return;
  send_ack(host_seq,code); tx_data[0]=code; tx_data[1]=1; send_frame(ERROR_FRAME,tx_data,2); state=FAILED;
}
bool read_byte(uint8_t *v) {
  uint32_t start=millis();
  while(!Serial.available()) {
    esp_task_wdt_reset(); delay(1);
    if((uint32_t)(millis()-start)>=FRAME_TIMEOUT_MS)return false;
  }
  int b=Serial.read(); if(b<0)return false; *v=(uint8_t)b; return true;
}
bool receive_frame(uint8_t *err) {
  uint8_t b;
  if(!read_byte(&b)){*err=FRAME_TIMEOUT;return false;}
  if(b!=SYNC0||!read_byte(&b)||b!=SYNC1){*err=BAD_FRAME;return false;}
  for(int i=0;i<8;i++)if(!read_byte(header+i)){*err=FRAME_TIMEOUT;return false;}
  frame.version=header[0]; frame.type=header[1]; frame.seq=get32(header+2); frame.len=get16(header+6);
  if(frame.len>MAX_PAYLOAD){*err=BAD_LENGTH;return false;}
  for(uint16_t i=0;i<frame.len;i++)if(!read_byte(frame.data+i)){*err=FRAME_TIMEOUT;return false;}
  uint8_t cb[4]; for(int i=0;i<4;i++)if(!read_byte(cb+i)){*err=FRAME_TIMEOUT;return false;}
  uint32_t c=crc_done(crc_bytes(0xffffffffu,header,8)); c=crc_done(crc_bytes(c^0xffffffffu,frame.data,frame.len));
  if(c!=get32(cb)){*err=BAD_CRC;return false;}
  if(frame.version!=VERSION){*err=BAD_VERSION;return false;}
  if(frame.seq!=rx_seq){*err=BAD_SEQUENCE;return false;}
  rx_seq++; return true;
}
void send_hello() {
  uint16_t n=0; tx_data[n++]=VERSION; tx_data[n++]=SVMG_N_FEATURES; put32(tx_data+n,feature_order_crc()); n+=4;
  n+=put_string(tx_data+n,SVMG_FEATURE_SCHEMA_VERSION);
  n+=put_string(tx_data+n,SEMANTIC_VERSION);
  n+=put_string(tx_data+n,VALIDITY_VERSION);
  n+=put_string(tx_data+n,PARITY_SCHEMA);
  n+=put_string(tx_data+n,"hv01-a-1 / esp32dev / Arduino");
  n+=put_string(tx_data+n,"-std=gnu++17 -Wall -Wextra -Wno-unused-parameter");
  n+=put_string(tx_data+n,__VERSION__);
  n+=put_string(tx_data+n,ESP.getSdkVersion());
  n+=put_string(tx_data+n,ESP.getChipModel());
  put16(tx_data+n,(uint16_t)ESP.getChipRevision()); n+=2;
  put16(tx_data+n,(uint16_t)ESP.getCpuFreqMHz()); n+=2;
  send_frame(HELLO,tx_data,n); last_hello_ms=millis();
}
void begin_run() {
  const uint8_t *p=frame.data; uint16_t n=frame.len;
  if(state!=WAIT_RUN||n<35||!id_ok(p+1,p[0],32)||n!=(uint16_t)(35+p[0])){fail(BAD_PAYLOAD,frame.seq);return;}
  memcpy(run_id,p+1,p[0]); run_id[p[0]]=0; expected_cases=get16(p+1+p[0]);
  if(!expected_cases||expected_cases>64){fail(BAD_PAYLOAD,frame.seq);return;}
  memcpy(manifest_sha,p+3+p[0],32); cases_done=case_count=0; state=IN_RUN; send_ack(frame.seq,0);
}
void begin_case() {
  const uint8_t *p=frame.data; uint16_t n=frame.len; uint8_t idn;
  if(state!=IN_RUN||n<42){fail(BAD_STATE,frame.seq);return;}
  idn=p[0]; if(!id_ok(p+1,idn,48)||n<(uint16_t)(42+idn)){fail(BAD_PAYLOAD,frame.seq);return;}
  uint16_t off=(uint16_t)(1+idn); uint32_t count=get32(p+off); off+=4;
  uint8_t ec=p[off++]; if(!count||count>MAX_SAMPLES||!ec||ec>MAX_ENDPOINTS||n!=(uint16_t)(off+4*ec+36)) {fail(BAD_PAYLOAD,frame.seq);return;}
  memcpy(case_id,p+1,idn); case_id[idn]=0; endpoint_count=ec; endpoint_pos=0;
  for(uint8_t i=0;i<ec;i++){endpoints[i]=get32(p+off);off+=4;if(endpoints[i]>=count||(i&&endpoints[i]<=endpoints[i-1])){fail(BAD_PAYLOAD,frame.seq);return;}}
  memcpy(input_sha,p+off,32);off+=32;expected_samples_crc=get32(p+off);case_sample_count=count;
  samples_received=0; sample_crc=0xffffffffu; svmg_window_clear(&window_state); memset(&features,0,sizeof features);
  case_count++; state=IN_CASE; send_ack(frame.seq,0);
}
void emit_result(uint32_t index) {
  uint8_t *p=tx_data; uint16_t n=0; uint8_t idn=(uint8_t)strlen(case_id);
  uint64_t t0=(uint64_t)esp_timer_get_time();
  /* Timing is measured around compute only; vector conversion and serial output are excluded. */
  svmg_features_compute(&window_state,&features);uint32_t elapsed=(uint32_t)((uint64_t)esp_timer_get_time()-t0);
  svmg_quality_cfg_t qc;svmg_quality_default(&qc);uint8_t reason=0;
  svmg_status_t st=svmg_features_status(&features,&qc,&reason);
  if(features.valid_mask&~SVMG_FEATURE_ALL_VALID){fail(BAD_PAYLOAD,rx_seq-1);return;}
  svmg_features_to_vector(&features,feature_values);
  for(int i=0;i<SVMG_N_FEATURES;i++)
    if((features.valid_mask&(1u<<i))&&!isfinite(feature_values[i])){fail(BAD_PAYLOAD,rx_seq-1);return;}
  p[n++]=idn;memcpy(p+n,case_id,idn);n+=idn;put32(p+n,index);n+=4;memcpy(p+n,input_sha,32);n+=32;
  put32(p+n,elapsed);n+=4;put32(p+n,features.valid_mask);n+=4;
  p[n++]=(uint8_t)((features.ready_short?1:0)|(features.ready_long?2:0));
  put16(p+n,features.n_valid_60);n+=2;put16(p+n,features.n_valid_180);n+=2;put16(p+n,features.consec_invalid);n+=2;
  memcpy(p+n,&features.data_quality_pct,4);n+=4;p[n++]=(uint8_t)st;p[n++]=reason;p[n++]=SVMG_N_FEATURES;
  for(int i=0;i<SVMG_N_FEATURES;i++){
    uint32_t bits=0x7fc00000u;
    if(features.valid_mask&(1u<<i))memcpy(&bits,&feature_values[i],4);
    put32(p+n,bits);n+=4;
  }
  send_frame(RESULT,p,n);
}
void samples() {
  const uint8_t *p=frame.data; uint16_t n=frame.len;
  if(state!=IN_CASE||n<5){fail(BAD_STATE,frame.seq);return;}
  uint32_t first=get32(p);uint8_t count=p[4];
  if(!count||count>MAX_BATCH||n!=(uint16_t)(5+10*count)||first!=samples_received||samples_received+count>case_sample_count){fail(BAD_SAMPLE_INDEX,frame.seq);return;}
  for(uint8_t i=0;i<count;i++){const uint8_t *s=p+5+10*i;if(s[8]>SVMG_RAW_PER_SAMPLE||s[9]>1){fail(BAD_PAYLOAD,frame.seq);return;}}
  sample_crc=crc_bytes(sample_crc,p+5,(size_t)count*10);
  for(uint8_t j=0;j<count;j++){
    const uint8_t *s=p+5+10*j;uint32_t rb=get32(s),pb=get32(s+4);float r,pitch;memcpy(&r,&rb,4);memcpy(&pitch,&pb,4);
    uint32_t index=samples_received++;
    svmg_window_push(&window_state,r,pitch,s[8],s[9]);
    if(endpoint_pos<endpoint_count&&index==endpoints[endpoint_pos]){emit_result(index);endpoint_pos++;if(state==FAILED)return;}
    esp_task_wdt_reset();
  }
  send_ack(frame.seq,0);
}
void case_end() {
  if(state!=IN_CASE||frame.len){fail(BAD_STATE,frame.seq);return;}
  if(samples_received!=case_sample_count||endpoint_pos!=endpoint_count){fail(INCOMPLETE_CASE,frame.seq);return;}
  if(crc_done(sample_crc)!=expected_samples_crc){fail(BAD_CASE_CRC,frame.seq);return;}
  send_ack(frame.seq,0);uint16_t n=0;uint8_t idn=(uint8_t)strlen(case_id);tx_data[n++]=idn;memcpy(tx_data+n,case_id,idn);n+=idn;
  put32(tx_data+n,samples_received);n+=4;tx_data[n++]=endpoint_pos;put32(tx_data+n,crc_done(sample_crc));n+=4;tx_data[n++]=0;
  send_frame(CASE_DONE,tx_data,n);cases_done++;state=IN_RUN;
}
void run_end() {
  if(state!=IN_RUN||frame.len||cases_done!=expected_cases||case_count!=expected_cases){fail(INCOMPLETE_CASE,frame.seq);return;}
  send_ack(frame.seq,0);uint16_t n=0;uint8_t idn=(uint8_t)strlen(run_id);tx_data[n++]=idn;memcpy(tx_data+n,run_id,idn);n+=idn;
  put16(tx_data+n,cases_done);n+=2;memcpy(tx_data+n,manifest_sha,32);n+=32;tx_data[n++]=0;send_frame(RUN_DONE,tx_data,n);state=FINISHED;
}
void dispatch() {
  switch(frame.type){case RUN_BEGIN:begin_run();break;case CASE_BEGIN:begin_case();break;case SAMPLES:samples();break;
    case CASE_END:case_end();break;case RUN_END:run_end();break;default:fail(BAD_FRAME,frame.seq);break;}
}
} // namespace

void setup() {
  Serial.begin(115200);delay(50);
  esp_task_wdt_config_t wc={8000,0,true};
  if(esp_task_wdt_init(&wc)==ESP_ERR_INVALID_STATE)esp_task_wdt_reconfigure(&wc);
  esp_task_wdt_add(nullptr);
  svmg_window_clear(&window_state);send_hello();
}
void loop() {
  esp_task_wdt_reset();
  if(state==WAIT_RUN&&!Serial.available()&&(uint32_t)(millis()-last_hello_ms)>=2000)send_hello();
  if(state==FINISHED||state==FAILED){delay(10);return;}
  if(!Serial.available()){delay(1);return;}
  uint8_t error=0;
  if(!receive_frame(&error)){fail(error,frame.seq);return;}
  dispatch();
}
