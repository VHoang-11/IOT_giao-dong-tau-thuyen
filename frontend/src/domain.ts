export type Role='Operator'|'Supervisor'|'Admin';
export type Scenario='S0'|'S0b'|'S1'|'S2'|'S3'|'H1'|'OFFLINE'|'SENSOR_FAULT';
export type RFClass='NORMAL'|'HIGH_ROLL'|'PERSISTENT_OFFSET'|'AMPLITUDE_GROWTH'|'UNKNOWN'|'FAULT';
export type AlarmLevel='NORMAL'|'CAUTION'|'WARNING'|'CRITICAL';
export type AlarmStatus='RAISED'|'ACKED'|'CLEARED';
export type CommandStatus='SENT'|'DELIVERED'|'APPLIED'|'REJECTED'|'TIMEOUT';
export type Page='overview'|'motion'|'alarms'|'control'|'reports'|'report-detail'|'replay'|'health'|'model'|'more';
export interface Session{username:string;role:Role;displayName:string}
export interface Telemetry{
 device_id:string;boot_id:string;seq:number;t_sim_s:number;uptime_ms:number;timewarp:number;
 source_mode:'SIMULATION'|'SENSOR';synthetic:boolean;scenario_id:string;voyage_id:string;
 roll_deg:number; pitch_deg:number;rms_roll_deg:number;heel_offset_deg:number;trend_rms_deg_per_min:number;
 class_rf:RFClass;class_baseline_b:RFClass;mai:number;alarm_level:AlarmLevel;
 model_version:string;config_version:number;sensor_ok:boolean;
}
export interface Alarm{id:string;title:string;level:AlarmLevel;status:AlarmStatus;raisedAt:string;ackedAt?:string;mutedUntil?:string;review?:'TRUE'|'FALSE'|'UNCERTAIN';}
export interface Command{id:string;name:string;status:CommandStatus;detail:string;issuedAt:string;version:number;issued_by?:string;reason?:string;is_test_utility?:boolean}
export interface MotionSnapshot{snapshot_id:string;timestamp:string;window_s:number;sample_count:number;roll_min:number;roll_max:number;pitch_min:number;pitch_max:number;rms_roll_deg:number;mai:number;triggered_by:string}
export interface ZeroCalibration{roll_offset_deg:number;pitch_offset_deg:number;std_dev_roll:number;duration_s:number;calibrated_at:string}
export interface Voyage{id:string;name:string;route:string;durationMinutes:number;durationHours:number;startTime:string;endTime:string;sourceMode:'SIMULATION'|'SENSOR';deviceId:string;modelVersion:string;configVersion:number;sampleCount:number;maxAbsRollDeg:number;rmsRollDeg:number;p95AbsRollDeg:number;maxAbsPitchDeg:number;rmsPitchDeg:number;maiMax:number;maiAvg:number;maiCautionMinutes:number;alarms:number;mttaSeconds:number;rfDistribution:{normalPct:number;highRollPct:number;persistentOffsetPct:number;amplitudeGrowthPct:number};agreementPercent:number}
export interface ReplayPoint{seq:number;t_sim_s:number;roll:number;pitch:number;class_rf:RFClass;class_baseline_b:RFClass;mai:number;alarm_level:AlarmLevel;alarm_id?:string;source_mode:'SIMULATION';synthetic:true}
export interface DeviceHealth{
 sensor:'OK'|'FAULT'|'UNKNOWN';sensorOk:boolean;i2cErrors:number;lastI2cError?:string;rssiDbm:number|null;
 uptimeS:number;uptimeMinutes:number;freeHeapKb:number;minFreeHeapKb:number;heapFragmentationPct:number;
 inferenceMs:number;mqttReconnects:number;bufferUsed:number;bufferCapacity:number;bufferStatus:'EMPTY'|'BUFFERING'|'OVERFLOW';
 queueLatencyMs:number;lastPacketUtc:string;packetGapS:number;healthScore:number;healthStatus:'HEALTHY'|'DEGRADED'|'CRITICAL';
}
export interface ModelInfo{
 active:string;activeModelId:'RF'|'BASELINE_B';baseline:string;baselineModelId:'RF'|'BASELINE_B';
 version:string;algorithm:string;featuresCount:number;features:string[];inferenceMs:number;flashKb:number;ramKb:number;
 agreementPercent:number;psi:number|null;psiStatus:string;
 concordanceBreakdown:{normal:number;highRoll:number;persistentOffset:number;amplitudeGrowth:number};
}
