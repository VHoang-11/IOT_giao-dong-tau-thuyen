import type {Alarm,AlarmLevel,RFClass,Scenario,Session,Telemetry,Voyage,ReplayPoint,DeviceHealth,ModelInfo} from './domain';
/** Tất cả dữ liệu dưới đây là DEMO. Không có suy luận ML trên frontend. */
export function hashPassword(password: string): string {
  let h1 = 0xdeadbeef ^ 0;
  let h2 = 0x41c6ce57 ^ 0;
  for (let i = 0; i < password.length; i++) {
    const ch = password.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return 'h_' + (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16);
}

export const DEMO_USERS: Record<string, { passwordHash: string; role: Session['role']; displayName: string }> = {
  operator: { passwordHash: hashPassword('demo123'), role: 'Operator', displayName: 'Bridge Operator' },
  supervisor: { passwordHash: hashPassword('demo123'), role: 'Supervisor', displayName: 'Shore Supervisor' },
  admin: { passwordHash: hashPassword('demo123'), role: 'Admin', displayName: 'Demo Administrator' }
};
export const SCENARIOS: {id:Scenario;name:string;className:string}[]=[
 {id:'S0',name:'Biển êm',className:'NORMAL'},
 {id:'S0b',name:'Nghiêng tạm thời',className:'NORMAL'},
 {id:'S1',name:'Lắc ngang lớn',className:'HIGH_ROLL'},
 {id:'S2',name:'Nghiêng lệch kéo dài',className:'PERSISTENT_OFFSET'},
 {id:'S3',name:'Biên độ tăng dần',className:'AMPLITUDE_GROWTH'},
 {id:'H1',name:'Tình huống kết hợp',className:'HIGH_ROLL'},
 {id:'OFFLINE',name:'Mất kết nối',className:'UNKNOWN'},
 {id:'SENSOR_FAULT',name:'Lỗi cảm biến',className:'FAULT'}
];
const labels:Record<Exclude<Scenario,'OFFLINE'|'SENSOR_FAULT'>,RFClass>={S0:'NORMAL',S0b:'NORMAL',S1:'HIGH_ROLL',S2:'PERSISTENT_OFFSET',S3:'AMPLITUDE_GROWTH',H1:'HIGH_ROLL'};
export function mockLogin(u:string,p:string):Session|null{
  const user=u.trim().toLowerCase(),a=DEMO_USERS[user];
  return a&&a.passwordHash===hashPassword(p)?{username:user,role:a.role,displayName:a.displayName}:null;
}
export function mockRegister(username:string,password:string,displayName:string):{success:boolean;message:string;error?:string}{
  const u=username.trim().toLowerCase();
  if(!u||!password){
    return {success:false,message:'',error:'Vui lòng điền đầy đủ Tên đăng nhập và Mật khẩu.'};
  }
  if(DEMO_USERS[u]){
    return {success:false,message:'',error:`Tài khoản "${u}" đã tồn tại trong danh bạ hệ thống.`};
  }
  DEMO_USERS[u]={
    passwordHash:hashPassword(password),
    role:'Operator', // Quyền cố định theo Bảng 3.1 Đề cương
    displayName:displayName.trim()||u
  };
  return {
    success:true,
    message:`[AUTH_SERVICE_PENDING] Đăng ký tài khoản nội bộ "${u}" thành công ở chế độ Mock. Quyền hạn: Sĩ quan trực ca (Operator / Bảng 3.1). Lưu ý: Dịch vụ xác thực và gửi email kích hoạt qua Backend TV3/SMTP đang chờ cấu hình, tài khoản có thể đăng nhập ngay trong phiên demo này.`
  };
}
export function mockForgotPassword(identifier:string):{success:boolean;message:string;error?:string}{
  const id=identifier.trim();
  if(!id){
    return {success:false,message:'',error:'Vui lòng nhập Tên đăng nhập hoặc Email sĩ quan.'};
  }
  return {
    success:true,
    message:`[AUTH_SERVICE_PENDING] Đã tiếp nhận yêu cầu đặt lại mật khẩu cho "${id}". Do Backend Auth Service / SMTP TV3 chưa được cấu hình ở môi trường Mock, email liên kết đặt lại mật khẩu thực tế chưa được gửi. Vui lòng liên hệ Quản trị viên để cấp phát lại mã thẻ phần cứng RSA.`
  };
}
export function waveform(s:Scenario,t:number){
 const base=Math.sin(t*.32);const growth=Math.min(15,2+(t%90)*.16);
 const roll=s==='S0'?base*2.2:s==='S0b'?(t%120<25?4.8:0)+base*2.3:s==='S1'?base*13.5:s==='S2'?8.2+base*1.8:s==='S3'?base*growth:s==='H1'?6+base*14.2:0;
 const pitch=Math.sin(t*.23+.7)*2.6;
 return {roll:+roll.toFixed(2),pitch:+pitch.toFixed(2)};
}
export function makeTelemetry(s:Scenario,tick:number,configVersion:number):Telemetry|null{
 if(s==='OFFLINE')return null;
 const faulty=s==='SENSOR_FAULT',scenario=faulty?'S0':s;
 const {roll,pitch}=waveform(scenario,tick);
 const label=faulty?'FAULT':labels[scenario as keyof typeof labels];
 const maiBase:Record<Scenario,number>={S0:12,S0b:25,S1:74,S2:63,S3:70,H1:85,OFFLINE:0,SENSOR_FAULT:0};
 const severity:Record<Scenario,AlarmLevel>={S0:'NORMAL',S0b:'NORMAL',S1:'WARNING',S2:'WARNING',S3:'WARNING',H1:'CRITICAL',OFFLINE:'NORMAL',SENSOR_FAULT:'CAUTION'};
 return {device_id:'vessel-demo-01',boot_id:'mock-boot-01',seq:tick,t_sim_s:tick*5,uptime_ms:tick*5000,timewarp:1,
 source_mode:'SIMULATION',synthetic:true,scenario_id:s,voyage_id:'V-2026-001',roll_deg:faulty?0:roll,pitch_deg:faulty?0:pitch,
 rms_roll_deg:faulty?0:Math.abs(roll)*.72,heel_offset_deg:s==='S2'?8.2:0,trend_rms_deg_per_min:s==='S3'?1.1:0,
 class_rf:label,class_baseline_b: faulty?'UNKNOWN':s==='S0b'?'HIGH_ROLL':label,mai:faulty?0:maiBase[s],
 alarm_level:severity[s],model_version:'RF-DEMO-v1',config_version:configVersion,sensor_ok:!faulty};
}
export const INITIAL_ALARMS:Alarm[]=[
 {id:'ALM-8492',title:'Biên độ dao động tăng (Amplitude Growth)',level:'CRITICAL',status:'RAISED',raisedAt:'2026-11-12T08:08:00Z'},
 {id:'ALM-8488',title:'Nghiêng lệch kéo dài (Persistent Offset)',level:'WARNING',status:'ACKED',raisedAt:'2026-11-12T08:05:20Z',ackedAt:'2026-11-12T08:06:10Z'},
 {id:'ALM-8450',title:'Lắc ngang lớn (High Roll)',level:'WARNING',status:'RAISED',raisedAt:'2026-11-12T08:02:30Z'},
 {id:'ALM-8441',title:'Dao động lắc ngang bất thường (MAI > 70)',level:'CAUTION',status:'CLEARED',raisedAt:'2026-11-12T08:01:00Z'}
];
export function samples(s:Scenario,tick:number,count=60){return Array.from({length:count},(_,i)=>({t:tick-count+i,...waveform(s,tick-count+i)}));}
export const MOCK_VOYAGES: Voyage[] = [
 {
  id: 'V-2026-001', name: 'Voyage Demo 01 (Chuyến kiểm thử T11/T15)',
  route: '10-minute monitoring window (S0 → S1 → S2 → S3 → S0)',
  durationMinutes: 10, durationHours: 10/60, startTime: '2026-11-12T08:00:00Z', endTime: '2026-11-12T08:10:00Z',
  sourceMode: 'SIMULATION', deviceId: 'vessel-demo-01', modelVersion: 'RF-DEMO-v1', configVersion: 7,
  sampleCount: 121, maxAbsRollDeg: 14.85, rmsRollDeg: 7.08, p95AbsRollDeg: 13.36,
  maxAbsPitchDeg: 2.60, rmsPitchDeg: 1.84, maiMax: 88, maiAvg: 46.2, maiCautionMinutes: 3.2,
  alarms: 4, mttaSeconds: 72,
  rfDistribution: { normalPct: 38.0, highRollPct: 24.8, persistentOffsetPct: 20.7, amplitudeGrowthPct: 16.5 },
  agreementPercent: 96.2
 },
 {
  id: 'V-2026-002', name: 'Voyage Demo 02 (Biển êm S0)',
  route: 'Hai Phong to Da Nang (Bình thường)',
  durationMinutes: 10, durationHours: 10/60, startTime: '2026-11-12T06:00:00Z', endTime: '2026-11-12T06:10:00Z',
  sourceMode: 'SIMULATION', deviceId: 'vessel-demo-01', modelVersion: 'RF-DEMO-v1', configVersion: 7,
  sampleCount: 121, maxAbsRollDeg: 2.20, rmsRollDeg: 1.56, p95AbsRollDeg: 2.15,
  maxAbsPitchDeg: 2.58, rmsPitchDeg: 1.80, maiMax: 14, maiAvg: 12.5, maiCautionMinutes: 0.0,
  alarms: 0, mttaSeconds: 0,
  rfDistribution: { normalPct: 100.0, highRollPct: 0.0, persistentOffsetPct: 0.0, amplitudeGrowthPct: 0.0 },
  agreementPercent: 100.0
 },
 {
  id: 'V-2026-003', name: 'Voyage Demo 03 (Sóng lớn kết hợp H1)',
  route: 'Vung Tau to Singapore (Thời tiết xấu)',
  durationMinutes: 10, durationHours: 10/60, startTime: '2026-11-11T22:00:00Z', endTime: '2026-11-11T22:10:00Z',
  sourceMode: 'SIMULATION', deviceId: 'vessel-demo-01', modelVersion: 'RF-DEMO-v1', configVersion: 7,
  sampleCount: 121, maxAbsRollDeg: 20.20, rmsRollDeg: 10.42, p95AbsRollDeg: 18.60,
  maxAbsPitchDeg: 2.60, rmsPitchDeg: 1.84, maiMax: 94, maiAvg: 68.4, maiCautionMinutes: 6.5,
  alarms: 5, mttaSeconds: 65,
  rfDistribution: { normalPct: 15.0, highRollPct: 55.0, persistentOffsetPct: 10.0, amplitudeGrowthPct: 20.0 },
  agreementPercent: 92.5
 }
];
export const MOCK_VOYAGE = MOCK_VOYAGES[0];
export const MOCK_HEALTH: DeviceHealth = {
 sensor: 'OK', sensorOk: true, i2cErrors: 0, rssiDbm: -62, uptimeS: 16500, uptimeMinutes: 275,
 freeHeapKb: 151, minFreeHeapKb: 114, heapFragmentationPct: 6.2, inferenceMs: 12.4, mqttReconnects: 0,
 bufferUsed: 0, bufferCapacity: 1000, bufferStatus: 'EMPTY', queueLatencyMs: 14,
 lastPacketUtc: '14:28:12 UTC', packetGapS: 1.2, healthScore: 100, healthStatus: 'HEALTHY'
};
export function computeHealth(scenario: Scenario, tick: number): DeviceHealth {
 const isOffline = scenario === 'OFFLINE';
 const isSensorFault = scenario === 'SENSOR_FAULT';
 const sensor: DeviceHealth['sensor'] = isSensorFault ? 'FAULT' : isOffline ? 'UNKNOWN' : 'OK';
 return {
  sensor, sensorOk: sensor === 'OK', i2cErrors: isSensorFault ? 3 : 0,
  lastI2cError: isSensorFault ? 'I2C NACK at 0x68 (MPU6050 timeout)' : undefined,
  rssiDbm: isOffline ? null : isSensorFault ? -65 : -62,
  uptimeS: 16500 + tick * 5, uptimeMinutes: Math.round((16500 + tick * 5) / 60),
  freeHeapKb: isOffline ? 146 : isSensorFault ? 150 : 151, minFreeHeapKb: 114,
  heapFragmentationPct: isOffline ? 8.4 : 6.2, inferenceMs: (isOffline || isSensorFault) ? 0 : 12.4,
  mqttReconnects: isOffline ? 2 : 0, bufferUsed: isOffline ? Math.min(1000, 24 + (tick % 50)) : 0,
  bufferCapacity: 1000, bufferStatus: isOffline ? 'BUFFERING' : 'EMPTY', queueLatencyMs: isOffline ? 450 : 14,
  lastPacketUtc: isOffline ? 'MẤT TÍN HIỆU (>30s)' : 'VỪA NHẬN (<2s)', packetGapS: isOffline ? 38 : 1.2,
  healthScore: isOffline ? 15 : isSensorFault ? 45 : 100,
  healthStatus: isOffline ? 'CRITICAL' : isSensorFault ? 'DEGRADED' : 'HEALTHY'
 };
}
export const MOCK_MODEL: ModelInfo = {
 active: 'Random Forest (Edge IMU)', activeModelId: 'RF', baseline: 'Baseline B (Shadow Engine)', baselineModelId: 'BASELINE_B',
 version: 'RF-Classifier-v2.4', algorithm: 'Ensemble 10 Decision Trees (C-transpiled TinyML)', featuresCount: 5,
 features: ['roll_rms_window_30s', 'roll_peak_abs', 'heel_offset_deg', 'trend_rms_deg_min', 'pitch_rms'],
 inferenceMs: 12.4, flashKb: 42.6, ramKb: 8.2, agreementPercent: 96.2, psi: 0.038,
 psiStatus: 'STABLE (< 0.10 - Không có sự dịch chuyển phân phối đáng kể)',
 concordanceBreakdown: { normal: 100.0, highRoll: 92.4, persistentOffset: 98.1, amplitudeGrowth: 94.3 }
};
export function computeModelInfo(activeModelId: 'RF' | 'BASELINE_B'): ModelInfo {
 const isRf = activeModelId === 'RF';
 return {
  active: isRf ? 'Random Forest (Edge IMU)' : 'Baseline B (Heuristic Rule-based)', activeModelId,
  baseline: isRf ? 'Baseline B (Shadow Engine)' : 'Random Forest (Shadow Engine)', baselineModelId: isRf ? 'BASELINE_B' : 'RF',
  version: isRf ? 'RF-Classifier-v2.4' : 'Baseline-B-v1.1',
  algorithm: isRf ? 'Ensemble 10 Decision Trees (C-transpiled TinyML)' : 'IMO Dynamic Kinematic Threshold Rules',
  featuresCount: 5, features: ['roll_rms_window_30s', 'roll_peak_abs', 'heel_offset_deg', 'trend_rms_deg_min', 'pitch_rms'],
  inferenceMs: isRf ? 12.4 : 1.8, flashKb: isRf ? 42.6 : 8.4, ramKb: isRf ? 8.2 : 1.5,
  agreementPercent: 96.2, psi: 0.038,
  psiStatus: 'STABLE (< 0.10 - Không có sự dịch chuyển phân phối đáng kể)',
  concordanceBreakdown: { normal: 100.0, highRoll: 92.4, persistentOffset: 98.1, amplitudeGrowth: 94.3 }
 };
}
/** Reproducible mock trip records (exact 121 points matching fixture telemetry_demo.csv). */
export const REPLAY_SAMPLES: ReplayPoint[] = Array.from({length:121},(_,i)=>{
 const s: Scenario = i<20?'S0':i<40?'S1':i<65?'S2':i<95?'S3':'S0';
 const {roll,pitch} = waveform(s,i);
 const class_rf: RFClass = i<20?'NORMAL':i<40?'HIGH_ROLL':i<65?'PERSISTENT_OFFSET':i<95?'AMPLITUDE_GROWTH':'NORMAL';
 const class_baseline_b: RFClass = i<20?'NORMAL':i<40?'HIGH_ROLL':i<65?'PERSISTENT_OFFSET':i<95?'HIGH_ROLL':'NORMAL';
 const mai = i<20?14:i<40?74:i<65?65:i<95?88:12;
 const alarm_level: AlarmLevel = i<20?'NORMAL':i<40?'WARNING':i<65?'WARNING':i<95?'CRITICAL':'NORMAL';
 const alarm_id = i===12?'ALM-8441':i===30?'ALM-8450':i===64?'ALM-8488':i===85?'ALM-8492':undefined;
 return {seq:i,t_sim_s:i*5,roll,pitch,class_rf,class_baseline_b,mai,alarm_level,alarm_id,source_mode:'SIMULATION' as const,synthetic:true as const};
});
