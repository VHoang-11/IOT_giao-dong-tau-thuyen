// 8 màn hình LIVE dùng chung khung (sidebar/topbar/theme) và thành phần giao diện với MOCK.
// Mọi số liệu lấy từ API thật; phần Backend/firmware chưa hỗ trợ hiển thị "Chưa khả dụng", không giả lập.
import {useEffect,useMemo,useState} from 'react';
import {apiDownload,apiRequest} from '../api';
import type {AckResult,AgreementStats,AlarmLabel,AlarmOut,CommandName,CommandOut,CommandStats,ConfigOut,DeviceHealthOut,DriftStatus,LiveTelemetry,ReplayResponse,ReportSummary,VoyageOut} from '../api';
import type {Page,Session} from '../domain';
import {Button,Metric,Panel,Pill} from '../ui';
import {ShipMotionVisualizer} from '../ShipMotionVisualizer';
import {getAlarmLevelNameVi,getRFClassNameVi,getRoleNameVi} from '../i18n/vi';
import {parseTime,useResource} from './useLive';
import type {LiveCore} from './useLive';

export interface LiveProps{page:Page;core:LiveCore;session:Session;token:string;notify:(msg:string)=>void;onUnauthorized:()=>void;goto:(p:Page)=>void;setDevice:(id:string)=>void}

const deg=(n:number|null|undefined)=>n==null||!Number.isFinite(n)?'—':`${n>0?'+':''}${n.toFixed(1)}°`;
const clock=(iso?:string|null)=>{const t=parseTime(iso);return Number.isFinite(t)?new Date(t).toLocaleString('vi-VN'):'—'};
const pct=(r?:number|null)=>r==null?'—':`${(r*100).toFixed(1)}%`;
const isSupervisor=(s:Session)=>s.role!=='Operator';
const levelTone=(l?:string|null)=>l==='CRITICAL'?'red':l==='WARNING'?'amber':l==='CAUTION'?'amber':'green';
const UNAVAILABLE='Chưa khả dụng';
const NO_AGREEMENT='Chưa đủ dữ liệu để đánh giá đồng thuận';
const CLASSIFIED=new Set(['NORMAL','HIGH_ROLL','PERSISTENT_OFFSET','AMPLITUDE_GROWTH']);
/** Chỉ so sánh khi CẢ HAI mô hình có lớp phân loại hợp lệ; UNKNOWN/FAULT không phải đồng thuận. */
const classifiedPair=(rf?:string|null,b?:string|null)=>!!rf&&!!b&&CLASSIFIED.has(rf)&&CLASSIFIED.has(b);

/** Biểu đồ đường SVG nhỏ cho dữ liệu thật (cùng class chart-holder/legend với MOCK). Giá trị null = khoảng trống, không nội suy. */
function LiveLineChart({series,height=220,empty,markers=[],cursor}:{series:{label:string;color:string;values:(number|null)[]}[];height?:number;empty?:string;markers?:number[];cursor?:number}){
 const n=Math.max(0,...series.map(s=>s.values.length));
 const vals=series.flatMap(s=>s.values.filter((v):v is number=>v!=null&&Number.isFinite(v)));
 if(n<2||vals.length<2)return <div className="chart-holder"><div className="chart-empty"><b>Chưa đủ dữ liệu thật để vẽ</b><small>{empty??'Cần ít nhất 2 mẫu hợp lệ'}</small></div></div>;
 const w=720,pad=14,lo=Math.min(0,...vals),hi=Math.max(0,...vals),span=Math.max(1,hi-lo)*1.15,mid=(hi+lo)/2;
 const x=(i:number)=>i/(n-1)*w,y=(v:number)=>height/2-(v-mid)*(height-2*pad)/span;
 const path=(v:(number|null)[])=>v.map((p,i)=>p==null||!Number.isFinite(p)?null:`${x(i)},${y(p)}`).reduce<string[][]>((acc,pt)=>{if(pt===null)acc.push([]);else acc[acc.length-1].push(pt);return acc},[[]]).filter(seg=>seg.length>1);
 return <div className="chart-holder" role="img" aria-label={`Biểu đồ dữ liệu thật: ${series.map(s=>s.label).join(', ')}`}>
  <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" width="100%" height={height} aria-hidden="true">
   <line x1="0" y1={y(0)} x2={w} y2={y(0)} stroke="var(--border-color, #183E65)" strokeWidth="1"/>
   {markers.map(i=><line key={`m${i}`} x1={x(i)} y1={0} x2={x(i)} y2={height} stroke="var(--status-red-text, #DC2626)" strokeDasharray="3 4" strokeWidth="1"/>)}
   {cursor!=null&&<line x1={x(cursor)} y1={0} x2={x(cursor)} y2={height} stroke="var(--text-muted, #64748B)" strokeWidth="1.5"/>}
   {series.map(s=>path(s.values).map((seg,k)=><polyline key={`${s.label}${k}`} points={seg.join(' ')} fill="none" stroke={s.color} strokeWidth="2.2" vectorEffect="non-scaling-stroke"/>))}
  </svg>
  <div className="legend">{series.map(s=><span key={s.label}><i className="dot" style={{background:s.color}}/>{s.label}</span>)}<span className="micro">Dữ liệu thật • thang {lo.toFixed(1)} … {hi.toFixed(1)}</span></div>
 </div>;
}

function ErrorNote({res,what}:{res:{error:string;status:number|null};what:string}){
 if(!res.error)return null;
 return <div className={`note ${res.status===403?'warning':'danger'}`}><b>{what}:</b> {res.error}{res.status===404?' (Backend chưa có dữ liệu này)':''}</div>;
}

/** Thực thi thao tác ghi sau khi người dùng xác nhận; báo kết quả thật từ Backend. */
async function confirmAndRun(message:string,run:()=>Promise<string>,notify:(m:string)=>void,after:()=>void){
 if(!window.confirm(message))return;
 try{notify(await run());}catch(e){notify(`Thất bại: ${e instanceof Error?e.message:String(e)}`);}
 after();
}

function sameBoot(rows:LiveTelemetry[]){const boot=rows[0]?.boot_id;return rows.filter(r=>r.boot_id===boot).slice().reverse()}

function LinkPills({core}:{core:LiveCore}){
 const f=core.link.fresh;
 return <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
  <Pill kind={core.link.kind}>{core.link.label}</Pill>
  {f&&<Pill kind={f.alarm_level}>{getAlarmLevelNameVi(f.alarm_level)}</Pill>}
  {f&&<Pill kind="caution">{f.source_mode==='SIMULATION'?'Nguồn: SIMULATION (ESP32)':'Nguồn: SENSOR (MPU6050)'}</Pill>}
 </div>;
}

function StaleNote({core}:{core:LiveCore}){
 const {state,latest,ageS,staleAfterS}=core.link;
 if(state==='ONLINE')return null;
 const text=state==='API_ERROR'?`Không đọc được Backend: ${core.telemetry.error}`
  :state==='NO_DATA'?'Backend chưa có telemetry cho thiết bị này. Kiểm tra ESP32/Wokwi và MQTT.'
  :state==='STALE'?`Không nhận telemetry mới trong ${ageS??'?'}s (ngưỡng ${staleAfterS}s). Giá trị cuối (${clock(latest?.server_rx_time)}) KHÔNG được hiển thị như thời gian thực.`
  :'Thiết bị vẫn gửi dữ liệu nhưng báo sensor_ok=false (lỗi cảm biến/I2C). Góc lắc không đáng tin cậy.';
 return <div className={`note ${state==='SENSOR_FAULT'?'warning':'offline'}`} style={{marginBottom:14}}><b>{core.link.label}:</b> {text}</div>;
}

/** Đồng bộ firmware (core/src/alarm_fsm.c svmg_alarm_mute) và Backend: chỉ WARNING, chưa ACK, cảnh báo của lần khởi động
 *  hiện tại, thiết bị trực tuyến đang ở WARNING. Trả lý do không cho tắt còi, hoặc null nếu được phép. */
function muteBlockReason(a:AlarmOut,liveLevel:string|null):string|null{
 if(a.boot_current===false)return 'Cảnh báo của lần khởi động trước: thiết bị không còn giữ cảnh báo này';
 if(a.level==='CRITICAL'||liveLevel==='CRITICAL')return 'Không tắt còi khi NGUY CẤP';
 if(a.state!=='ACTIVE')return a.state==='ACKED'?'Đã ACK: thiết bị không cho tắt còi nữa':'Cảnh báo đã kết thúc';
 if(a.level!=='WARNING')return 'Thiết bị chỉ cho tắt còi ở mức CẢNH BÁO (WARNING)';
 if(liveLevel===null)return 'Thiết bị không trực tuyến';
 if(liveLevel!=='WARNING')return `Mức hiện tại trên thiết bị là ${liveLevel}, không phải WARNING`;
 return null;
}
const DEVICE_ACK_TEXT:Record<string,string>={NOT_REQUESTED:'Chỉ ghi nhận trên Backend (không gửi xuống thiết bị)',PENDING:'Đang chờ thiết bị xác nhận',
 CONFIRMED:'Thiết bị đã xác nhận ACK',APPLIED_UNCONFIRMED:'Thiết bị nhận lệnh nhưng CHƯA xác nhận ACK cho cảnh báo này',REJECTED:'Thiết bị từ chối',TIMEOUT:'Hết hạn, thiết bị không phản hồi'};

function AlarmEntry({a,session,token,notify,reload,detail,onOpen,liveLevel}:{a:AlarmOut;session:Session;token:string;notify:(m:string)=>void;reload:()=>void;detail:boolean;onOpen?:()=>void;liveLevel:string|null}){
 const muteReason=muteBlockReason(a,liveLevel);
 const ack=()=>confirmAndRun(`Xác nhận (ACK) cảnh báo ${a.alarm_id}? ACK chỉ ghi nhận người trực đã biết, KHÔNG tắt cảnh báo cục bộ trên thiết bị.`,
  async()=>{const r=await apiRequest<AckResult>(token,`/api/v1/alarms/${a.id}/ack`,{method:'POST'});
   return r.already_acked?`${a.alarm_id} đã được ACK trước đó.`
    :r.device_ack==='sent'?`ACK ${a.alarm_id} đã ghi trên Backend; đã gửi lệnh ${r.device_ack_cmd_id??'ack_alarm'} — đang chờ thiết bị xác nhận (chưa phải ACK thiết bị).`
    :`ACK ${a.alarm_id} chỉ ghi trên Backend; không đồng bộ thiết bị (${r.device_ack??'—'}${r.device_ack_detail?`: ${r.device_ack_detail}`:''}).`},notify,reload);
 const mute=()=>confirmAndRun(`Gửi lệnh mute_alarm 300 s tới ${a.device_id}? Thiết bị chỉ cho tắt còi ở mức WARNING khi chưa ACK; lệnh không tắt đèn/LCD.`,
  async()=>{const c=await apiRequest<CommandOut>(token,`/api/v1/devices/${encodeURIComponent(a.device_id)}/commands`,{method:'POST',body:JSON.stringify({cmd:'mute_alarm',params:{duration_s:300}})});
   return `Lệnh ${c.cmd_id} (${c.cmd}) trạng thái ${c.state}; xem kết quả cuối ở Trung tâm điều khiển.`},notify,reload);
 const label=(l:AlarmLabel)=>confirmAndRun(`Gán nhãn thẩm định ${l} cho ${a.alarm_id}?`,
  async()=>{await apiRequest(token,`/api/v1/alarms/${a.id}/label`,{method:'PUT',body:JSON.stringify({label:l})});return `Đã lưu nhãn ${l} cho ${a.alarm_id}.`},notify,reload);
 return <div className={`alarm-entry ${a.level.toLowerCase()}`}>
  <div className="alarm-title"><div><b>{a.alarm_id}</b> <span className="muted">• {a.motion_class?getRFClassNameVi(a.motion_class):'—'} • đỉnh {getAlarmLevelNameVi(a.max_level)}{a.escalated?' • ĐÃ LEO THANG':''}</span></div><Pill kind={a.level}>{getAlarmLevelNameVi(a.level)}</Pill></div>
  <div className="data-line"><span className="micro">Mở {clock(a.opened_at)} · {a.state}{a.acked_by?` · ACK người trực: ${a.acked_by} (${a.time_to_ack_s??'—'}s)`:''}{a.cleared_at?` · kết thúc ${clock(a.cleared_at)}`:''}{a.label?` · nhãn ${a.label}`:''}</span></div>
  {a.device_ack&&<div className="data-line"><span className="micro">ACK trên thiết bị: <b>{DEVICE_ACK_TEXT[a.device_ack.state]??a.device_ack.state}</b>{a.device_ack.cmd_id?` · ${a.device_ack.cmd_id}`:''}{a.device_ack.reason&&a.device_ack.state!=='CONFIRMED'?` · ${a.device_ack.reason}`:''}</span></div>}
  {a.boot_current===false&&<div className="note offline" style={{margin:'6px 0'}}>Lần khởi động trước ({a.boot_id}): lịch sử, thiết bị không còn giữ cảnh báo này. Không tự coi là đã hết nguy hiểm; không chặn tắt còi của lần khởi động hiện tại.</div>}
  {detail?<div className="button-line">
   <Button kind="secondary" disabled={a.state!=='ACTIVE'} onClick={ack}>{a.state==='ACTIVE'?'Xác nhận (ACK)':'✓ Đã tiếp nhận'}</Button>
   <Button kind="ghost" disabled={muteReason!==null} title={muteReason??'Thiết bị đang ở WARNING, cảnh báo chưa ACK'} onClick={mute}>Tắt còi ≤300s</Button>
   {isSupervisor(session)&&(['TRUE_ALARM','FALSE_ALARM','UNCLEAR'] as AlarmLabel[]).map(l=><Button key={l} kind="ghost" onClick={()=>label(l)}>{l==='TRUE_ALARM'?'Đúng':l==='FALSE_ALARM'?'Báo nhầm':'Chưa rõ'}</Button>)}
  </div>:<Button kind="ghost" onClick={onOpen}>Xem chi tiết →</Button>}
 </div>;
}

function Overview({core,session,token,notify,goto,setDevice}:LiveProps){
 const f=core.link.fresh,latest=core.link.latest;
 const active=(core.alarms.data??[]).filter(a=>a.state==='ACTIVE'&&a.boot_current!==false);   // boot cũ: lịch sử, không tính là đang mở trên thiết bị
 const liveLevel=core.link.state==='ONLINE'?core.link.fresh?.alarm_level??null:null;
 const dev=core.devices.data?.find(d=>d.device_id===core.deviceId);
 const ok=core.link.state==='ONLINE';
 return <>
  <div className="page-hero"><div><span className="eyebrow">Buồng lái chỉ huy • LIVE</span><h1>Tổng quan vận hành</h1><p>Dữ liệu thật: ESP32/Wokwi → MQTT → FastAPI → SQLite, làm mới mỗi 5 giây.</p></div><LinkPills core={core}/></div>
  <StaleNote core={core}/>
  <div className="metrics">
   <Metric label="Mức cảnh báo tàu" value={f?getAlarmLevelNameVi(f.alarm_level):'—'} note={f?`Theo telemetry seq ${f.seq}`:'Không có dữ liệu tức thời'} tone={levelTone(f?.alarm_level)}/>
   <Metric label="Trạng thái thiết bị" value={ok?'Đang kết nối':core.link.state==='SENSOR_FAULT'?'Lỗi cảm biến':'Mất kết nối'} note={`Tuổi dữ liệu: ${core.link.ageS??'—'}s`} tone={ok?'green':core.link.state==='SENSOR_FAULT'?'amber':'red'}/>
   <Metric label="Chỉ số bất thường MAI" value={ok&&f?.mai!=null?`${f.mai} / 100`:'—'} note={f&&f.mai==null?'Thiết bị không gửi MAI':'Từ telemetry'} tone={(f?.mai??0)>=70?'red':(f?.mai??0)>=35?'amber':'green'}/>
   <Metric label="Cảnh báo ca trực" value={core.alarms.data?`${active.length} đang mở`:'—'} note={core.alarmStats.data?`${core.alarmStats.data.acked} đã ACK • ${core.alarmStats.data.total} tổng${core.alarmStats.data.open_previous_boot?` • ${core.alarmStats.data.open_previous_boot} mở của lần khởi động trước`:''}`:'Đang tải thống kê'} tone={active.length?'red':'green'}/>
  </div>
  <div className="columns">
   <div>
    <Panel title="Tóm tắt động học thân tàu" tag={f?`seq ${f.seq} • ${clock(f.server_rx_time)}`:'Không tức thời'}>
     <dl className="kv">
      <dt>Góc lắc ngang (Roll)</dt><dd className={ok?'text-info':'text-muted'} style={{fontWeight:600}}>{ok?deg(f?.roll_deg):'—'}</dd>
      <dt>Góc lắc dọc (Pitch)</dt><dd className={ok?'text-warning':'text-muted'} style={{fontWeight:600}}>{ok?deg(f?.pitch_deg):'—'}</dd>
      <dt>RMS Roll</dt><dd>{ok?deg(f?.rms_roll_deg):'—'}</dd>
      <dt>Baseline B (mô hình quyết định)</dt><dd style={{fontWeight:600}}>{f?.class_baseline_b?`${getRFClassNameVi(f.class_baseline_b)} (${f.class_baseline_b})`:'—'}</dd>
      <dt>Random Forest</dt><dd className="text-muted">{f?`${f.class_rf}${f.class_rf==='UNKNOWN'?' — RF chưa hoạt động trên firmware chính':''}`:'—'}</dd>
      <dt>Mực nước hầm hàng</dt><dd>{ok&&f?.cargo_water_pct!=null?`${f.cargo_water_pct.toFixed(1)}%`:'—'}</dd>
      <dt>Nhiệt độ / Độ ẩm hầm hàng</dt><dd>{ok&&(f?.cargo_temp_c!=null||f?.cargo_humidity_pct!=null)?`${f?.cargo_temp_c!=null?`${f.cargo_temp_c.toFixed(1)}°C`:'—'} / ${f?.cargo_humidity_pct!=null?`${f.cargo_humidity_pct.toFixed(1)}%`:'—'}`:'—'}</dd>
     </dl>
    </Panel>
    <Panel title="Thông số tàu & Kết nối thiết bị" tag={core.deviceId??'Chưa có thiết bị'}>
     {(core.devices.data?.length??0)>1&&<div className="filter-line"><label htmlFor="live-device">Thiết bị</label><select id="live-device" value={core.deviceId??''} onChange={e=>setDevice(e.target.value)}>{core.devices.data!.map(d=><option key={d.device_id} value={d.device_id}>{d.device_id} ({d.state})</option>)}</select></div>}
     <dl className="kv">
      <dt>Thiết bị / trạng thái Backend</dt><dd>{dev?`${dev.device_id} • ${dev.state}${dev.enabled===false?' • đã vô hiệu hóa':''}`:'—'}</dd>
      <dt>Nguồn dữ liệu</dt><dd>{latest?.source_mode??dev?.source_mode??'—'}</dd>
      <dt>Firmware / mô hình / cấu hình</dt><dd>{dev?`${dev.fw??'—'} • ${dev.model_version??'—'} • v${dev.config_version??'—'}`:'—'}</dd>
      <dt>Boot / t_sim</dt><dd>{latest?`${latest.boot_id} • T+${latest.t_sim_s.toFixed(1)}s`:'—'}</dd>
      <dt>Lần nhận cuối (server)</dt><dd>{clock(latest?.server_rx_time)} ({core.link.ageS??'—'}s trước)</dd>
      <dt>Sĩ quan đăng nhập</dt><dd>{session.username} ({getRoleNameVi(session.role)})</dd>
     </dl>
    </Panel>
   </div>
   <div>
    <Panel title="Cảnh báo đang mở & Cần xử lý" tag={active.length?`${active.length} chờ xử lý`:'Không có cảnh báo mở'}>
     <ErrorNote res={core.alarms} what="Cảnh báo"/>
     {active.length?active.slice(0,3).map(a=><AlarmEntry key={a.id} a={a} session={session} token={token} notify={notify} reload={core.reloadAll} detail liveLevel={liveLevel}/>)
      :core.alarms.data&&<div className="note success"><b>✓ Không có cảnh báo ACTIVE</b> theo Backend.</div>}
     <Button kind="ghost" onClick={()=>goto('alarms')}>Tất cả cảnh báo →</Button>
    </Panel>
    <Panel title="Sẵn sàng hệ thống" tag="LIVE">
     <dl className="kv">
      <dt>Telemetry API</dt><dd className={core.telemetry.error?'text-danger':'text-success'}>{core.telemetry.error||`OK • ${core.telemetry.data?.length??0} mẫu gần nhất`}</dd>
      <dt>Ngưỡng coi là dữ liệu cũ</dt><dd>{core.link.staleAfterS}s (≥ 3 chu kỳ gửi quan sát được)</dd>
      <dt>Mô hình chính trên thiết bị</dt><dd>Baseline B + ngưỡng cứng φ_hard</dd>
      <dt>Random Forest</dt><dd>Firmware chính trả class_rf=UNKNOWN; RF bốn lớp chỉ chạy shadow trong env thử nghiệm</dd>
     </dl>
     <div className="note" style={{marginTop:12}}><b>Quy tắc an toàn:</b> ACK không tắt cảnh báo cục bộ; không tắt còi khi NGUY CẤP; mất kết nối/lỗi cảm biến hiển thị rõ, không suy diễn BÌNH THƯỜNG.</div>
    </Panel>
   </div>
  </div>
 </>;
}

function Motion({core}:LiveProps){
 const f=core.link.fresh,ok=core.link.state==='ONLINE';
 const rows=sameBoot(core.telemetry.data??[]);
 return <>
  <div className="page-hero"><div><span className="eyebrow">Viễn trắc động học • LIVE</span><h1>Giám sát chuyển động</h1><p>Roll/Pitch, MAI và lớp chuyển động từ telemetry thật của phiên khởi động hiện tại.</p></div><LinkPills core={core}/></div>
  <StaleNote core={core}/>
  <div className="compact-metrics-grid" style={{marginBottom:20}}>
   <Metric label="Góc lắc ngang" value={ok?deg(f?.roll_deg):'—'} note={ok?'Tức thời':core.link.label} tone="cyan"/>
   <Metric label="Góc chúi dọc" value={ok?deg(f?.pitch_deg):'—'} note={ok?'Tức thời':core.link.label} tone="amber"/>
   <Metric label="Chỉ số bất thường MAI" value={ok&&f?.mai!=null?`${f.mai} / 100`:'—'} note={f&&f.mai==null?'Không có MAI':'Từ thiết bị'} tone={(f?.mai??0)>=70?'red':(f?.mai??0)>=35?'amber':'green'}/>
   <Metric className="metric-tinyml" label="Lớp Baseline B" value={f?.class_baseline_b?getRFClassNameVi(f.class_baseline_b):'—'} note={`RF: ${f?.class_rf??'—'}`} tone={!f?'red':f.class_baseline_b==='NORMAL'?'green':'amber'}/>
  </div>
  <div className="motion-monitoring-grid">
   <Panel title="Mô hình chuyển động tàu" tag="Góc thật từ telemetry">
    <ShipMotionVisualizer rollDeg={ok?f?.roll_deg:null} pitchDeg={ok?f?.pitch_deg:null} mai={ok?f?.mai:null} alarmLevel={f?.alarm_level??'NORMAL'}
     classRf={f?.class_baseline_b??'UNKNOWN'} sourceMode={core.link.latest?.source_mode??'SENSOR'} sensorOk={ok} variant="split"/>
   </Panel>
   <Panel title="Biểu đồ dao động" tag={`${rows.length} mẫu • cùng boot`}>
    <LiveLineChart height={280} series={[{label:'Roll (°)',color:'#0284C7',values:rows.map(r=>r.sensor_ok?r.roll_deg:null)},{label:'Pitch (°)',color:'#D97706',values:rows.map(r=>r.sensor_ok?r.pitch_deg:null)}]} empty="Chờ telemetry từ thiết bị"/>
   </Panel>
  </div>
  <Panel title="Xu hướng chỉ số bất thường MAI" tag="Lịch sử thật, không nội suy">
   <LiveLineChart height={170} series={[{label:'MAI',color:'#7C3AED',values:rows.map(r=>r.mai)}]} empty="Thiết bị chưa gửi MAI"/>
  </Panel>
  <Panel title="Cảm biến hầm hàng (GPIO 35 & DHT22)" tag="Dữ liệu thật từ ESP32">
   <div className="compact-metrics-grid">
    <Metric label="Mực nước hầm hàng" value={ok&&f?.cargo_water_pct!=null?`${f.cargo_water_pct.toFixed(1)}%`:'—'} note={ok?'GPIO 35 (ADC1)':core.link.label} tone={(f?.cargo_water_pct??0)>=70?'red':(f?.cargo_water_pct??0)>=35?'amber':'green'}/>
    <Metric label="Nhiệt độ hầm hàng" value={ok&&f?.cargo_temp_c!=null?`${f.cargo_temp_c.toFixed(1)}°C`:'—'} note={ok?'DHT22 (GPIO 4)':core.link.label} tone={(f?.cargo_temp_c??0)>=45?'red':'cyan'}/>
    <Metric label="Độ ẩm hầm hàng" value={ok&&f?.cargo_humidity_pct!=null?`${f.cargo_humidity_pct.toFixed(1)}%`:'—'} note={ok?'DHT22 (GPIO 4)':core.link.label} tone={(f?.cargo_humidity_pct??0)>=85?'amber':'green'}/>
   </div>
  </Panel>
  <div className="columns">
   <Panel title="Mô hình phân loại & đối chiếu" tag="Baseline B vs Random Forest">
    <dl className="kv">
     <dt>Baseline B (mô hình chính trên thiết bị)</dt><dd style={{fontWeight:600}}>{f?.class_baseline_b??'—'}</dd>
     <dt>Random Forest</dt><dd>{f?.class_rf??'—'}{f?.class_rf==='UNKNOWN'?' (firmware chính chưa nạp RF)':''}</dd>
     <dt>Đồng thuận</dt><dd>{!f||!classifiedPair(f.class_rf,f.class_baseline_b)?`${NO_AGREEMENT} (RF/Baseline B không có lớp phân loại hợp lệ)`:f.class_rf===f.class_baseline_b?'✓ Đồng thuận':'⚠ Bất đồng'}</dd>
     <dt>Cảm biến</dt><dd className={core.link.latest?.sensor_ok?'text-success':'text-danger'}>{core.link.latest?(core.link.latest.sensor_ok?'sensor_ok=true':'sensor_ok=false'):'—'}</dd>
    </dl>
   </Panel>
  </div>
 </>;
}

function Alarms(props:LiveProps){
 const {core,session,token,notify}=props;
 const [filter,setFilter]=useState('ALL');
 const [open,setOpen]=useState<number|null>(null);
 const list=(core.alarms.data??[]).filter(a=>filter==='ALL'||a.state===filter||a.level===filter);
 const st=core.alarmStats.data;
 const liveLevel=core.link.state==='ONLINE'?core.link.fresh?.alarm_level??null:null;
 const sel=core.alarms.data?.find(a=>a.id===open);
 return <>
  <header className="page-heading"><h1>Quản lý cảnh báo</h1><p>Cảnh báo thật từ Backend. ACK ghi nhận người trực đã biết; còi chỉ tắt bằng lệnh mute_alarm (≤300 s, không áp dụng khi NGUY CẤP).</p></header>
  <ErrorNote res={core.alarmStats} what="Thống kê cảnh báo"/>
  <div className="metrics">
   <Metric label="Đang phát (ACTIVE)" value={st?String(st.active):'—'} note={st?.open_previous_boot?`${st.open_previous_boot} cảnh báo mở của lần khởi động trước (lịch sử)`:undefined} tone={st?.active?'red':'green'}/>
   <Metric label="Đã xác nhận" value={st?String(st.acked):'—'} tone="amber"/>
   <Metric label="Đã kết thúc" value={st?String(st.cleared):'—'} tone="green"/>
   <Metric label="Thời gian tiếp nhận TB (MTTA)" value={st?.mtta_s!=null?`${Math.round(st.mtta_s)}s`:'—'} note={st?`Leo thang ${st.escalated} • báo nhầm ${pct(st.false_alarm_rate)}`:undefined} tone="cyan"/>
  </div>
  <Panel title="Danh sách cảnh báo" tag={`${core.alarms.data?.length??0} gần nhất`}>
   <ErrorNote res={core.alarms} what="Danh sách cảnh báo"/>
   <div className="filter-line"><label htmlFor="live-alarm-filter">Lọc</label><select id="live-alarm-filter" value={filter} onChange={e=>setFilter(e.target.value)}>
    <option value="ALL">Tất cả</option><option value="ACTIVE">Đang phát (ACTIVE)</option><option value="ACKED">Đã xác nhận (ACKED)</option><option value="CLEARED">Đã kết thúc (CLEARED)</option><option value="CRITICAL">Nguy cấp</option><option value="WARNING">Cảnh báo</option>
   </select></div>
   {list.map(a=><AlarmEntry key={a.id} a={a} session={session} token={token} notify={notify} reload={core.reloadAll} detail={false} onOpen={()=>setOpen(a.id)} liveLevel={liveLevel}/>)}
   {core.alarms.data&&!list.length&&<p>Không có cảnh báo phù hợp.</p>}
  </Panel>
  {sel&&<Panel title={`Chi tiết cảnh báo ${sel.alarm_id}`} tag={`#${sel.id} • ${sel.source_mode}`}><AlarmEntry a={sel} session={session} token={token} notify={notify} reload={core.reloadAll} detail liveLevel={liveLevel}/><Button kind="ghost" onClick={()=>setOpen(null)}>Đóng chi tiết</Button></Panel>}
 </>;
}

/** Lệnh firmware chính hỗ trợ (core/src/cmd.c + HOOKS app.cpp) và vai trò tối thiểu theo backend commands.service.REQUIRED_ROLE. */
const SUPPORTED:{cmd:CommandName;label:string;role:'Supervisor'|'Admin'}[]=[
 {cmd:'set_profile',label:'Đổi profile ngưỡng',role:'Supervisor'},{cmd:'set_threshold',label:'Đặt ngưỡng',role:'Supervisor'},
 {cmd:'calibrate_zero',label:'Hiệu chuẩn điểm 0',role:'Supervisor'},{cmd:'restart_device',label:'Khởi động lại thiết bị',role:'Admin'}];
const NOT_SUPPORTED=['set_scenario','set_mode','set_timewarp','request_snapshot','set_model (chỉ có trong bản firmware kiểm thử SVMG_EXT_COMMANDS)','start_voyage / stop_voyage xuống thiết bị (firmware trả UNSUPPORTED; chuyến đi quản lý ở Backend)'];

function Control({core,session,token,notify,onUnauthorized}:LiveProps){
 const enc=core.deviceId?encodeURIComponent(core.deviceId):null;
 const cmds=useResource<CommandOut[]>(token,enc?`/api/v1/commands?device_id=${enc}&limit=50`:null,5000,onUnauthorized);
 const stats=useResource<CommandStats>(token,enc?`/api/v1/commands/stats?device_id=${enc}`:null,5000,onUnauthorized);
 // Thẻ thống kê và Nhật ký lệnh là hai request khác nhịp: mỗi khi trạng thái lệnh trong nhật ký đổi (vd. SENT→APPLIED) thì đọc lại
 // thống kê ngay để hai nơi không lệch nhau (trước đây thống kê 10 s/lần nên 'APPLIED' có lúc chậm một lệnh).
 const cmdSig=(cmds.data??[]).map(c=>`${c.cmd_id}:${c.state}`).join('|');
 useEffect(()=>{if(cmdSig)stats.reload();},[cmdSig,stats.reload]);
 const configs=useResource<ConfigOut[]>(token,enc?`/api/v1/devices/${enc}/config`:null,30000,onUnauthorized);
 const [profile,setProfile]=useState('STANDARD');
 const [th,setTh]=useState({phi_hard_deg:'',mai_caution:'',debounce_n:'',report_interval_s:''});
 const allowed=(role:'Supervisor'|'Admin')=>role==='Admin'?session.role==='Admin':isSupervisor(session);
 const send=(cmd:CommandName,params:Record<string,unknown>,what:string)=>confirmAndRun(`Gửi lệnh ${cmd} tới ${core.deviceId}?\n${what}\nLệnh đi qua MQTT tới thiết bị thật và được ghi nhật ký kiểm toán.`,
  async()=>{const c=await apiRequest<CommandOut>(token,`/api/v1/devices/${enc}/commands`,{method:'POST',body:JSON.stringify({cmd,params})});return `Lệnh ${c.cmd_id} (${c.cmd}): ${c.state}${c.reason?` – ${c.reason}`:''}`},notify,()=>{cmds.reload();stats.reload();configs.reload()});
 const thParams=Object.fromEntries(Object.entries(th).filter(([,v])=>v!=='').map(([k,v])=>[k,Number(v)]));
 const s=stats.data;
 return <>
  <div className="page-hero"><div><span className="eyebrow">Điều khiển từ xa • LIVE</span><h1>Trung tâm điều khiển</h1><p>Chỉ bật các lệnh mà firmware chính hỗ trợ; vai trò được Backend kiểm tra lại. Không có lệnh nào tắt cảnh báo cục bộ.</p></div><LinkPills core={core}/></div>
  <div className="metrics">
   <Metric label="Tổng lệnh" value={s?String(s.total):'—'} tone="cyan"/>
   <Metric label="APPLIED" value={s?String(s.by_state.APPLIED??0):'—'} tone="green"/>
   <Metric label="REJECTED / TIMEOUT" value={s?`${s.by_state.REJECTED??0} / ${s.by_state.TIMEOUT??0}`:'—'} tone="amber"/>
   <Metric label="RTT p95" value={s?.rtt_p95_s!=null?`${s.rtt_p95_s.toFixed(1)}s`:'—'} note={s?.timeout_rate!=null?`Tỉ lệ timeout ${pct(s.timeout_rate)}`:undefined} tone="cyan"/>
  </div>
  <div className="columns">
   <Panel title="Gửi lệnh tới thiết bị" tag={core.deviceId??'Chưa có thiết bị'}>
    {!isSupervisor(session)&&<div className="note warning">Vai trò Operator không gửi được lệnh cấu hình (Backend yêu cầu Supervisor/Admin). Operator vẫn ACK và tắt còi ở màn hình Cảnh báo.</div>}
    {core.link.state!=='ONLINE'&&<div className="note offline">Thiết bị không trực tuyến: lệnh có thể TIMEOUT.</div>}
    <div className="filter-line"><label htmlFor="live-profile">Profile</label><select id="live-profile" value={profile} onChange={e=>setProfile(e.target.value)}><option>STANDARD</option><option>SENSITIVE</option><option>CONSERVATIVE</option></select>
     <Button disabled={!allowed('Supervisor')||!enc} onClick={()=>send('set_profile',{profile},`Profile mới: ${profile}`)}>Áp dụng profile</Button></div>
    <div className="filter-line" style={{flexWrap:'wrap'}}>
     {([['phi_hard_deg','φ_hard (15–25°)'],['mai_caution','MAI caution (30–90)'],['debounce_n','debounce (1–10)'],['report_interval_s','chu kỳ gửi (1–3600 s)']] as const).map(([k,l])=>
      <label key={k} style={{display:'flex',flexDirection:'column',gap:2}}><span className="micro">{l}</span><input type="number" value={th[k]} onChange={e=>setTh(o=>({...o,[k]:e.target.value}))} style={{width:120}}/></label>)}
     <Button disabled={!allowed('Supervisor')||!enc||!Object.keys(thParams).length} onClick={()=>send('set_threshold',thParams,`Tham số: ${JSON.stringify(thParams)}`)}>Đặt ngưỡng</Button>
    </div>
    <div className="button-line">
     <Button kind="secondary" disabled={!allowed('Supervisor')||!enc} onClick={()=>send('calibrate_zero',{},'Thiết bị chỉ chấp nhận khi tàu đứng yên (NOT_STATIC nếu đang dao động) và không có cảnh báo ≥ WARNING.')}>Hiệu chuẩn điểm 0</Button>
     <Button kind="danger" disabled={!allowed('Admin')||!enc} onClick={()=>send('restart_device',{},'Thiết bị từ chối khi đang ở mức ≥ WARNING.')}>Khởi động lại (Admin)</Button>
    </div>
    <p className="micro">Hỗ trợ: {SUPPORTED.map(c=>`${c.cmd} (${c.role}+)`).join(', ')}, mute_alarm/ack_alarm ở màn hình Cảnh báo.</p>
    <div className="note"><b>{UNAVAILABLE} trên firmware chính:</b> {NOT_SUPPORTED.join('; ')}.</div>
   </Panel>
   <Panel title="Cấu hình đã lưu" tag={configs.data?`${configs.data.length} phiên bản`:''}>
    <ErrorNote res={configs} what="Cấu hình"/>
    {(configs.data??[]).slice(0,5).map(c=><div key={c.config_version} className="data-line"><span>v{c.config_version} • {c.applied?'đã áp dụng':c.rejected_reason?`từ chối: ${c.rejected_reason}`:'chờ'}</span><span className="micro">{c.created_by} • {clock(c.created_at)} • {JSON.stringify(c.payload)}</span></div>)}
    {configs.data&&!configs.data.length&&<p className="micro">Chưa có cấu hình nào được lưu trên Backend.</p>}
   </Panel>
  </div>
  <Panel title="Nhật ký lệnh" tag="50 lệnh gần nhất">
   <ErrorNote res={cmds} what="Nhật ký lệnh"/>
   {(cmds.data??[]).map(c=><div key={c.cmd_id} className="data-line"><span><Pill kind={c.state}>{c.state}</Pill> <b>{c.cmd}</b> {c.params?JSON.stringify(c.params):''}</span><span className="micro">{c.cmd_id} • {c.issued_by} • {clock(c.created_at)}{c.rtt_s!=null?` • RTT ${c.rtt_s.toFixed(1)}s`:''}{c.reason?` • ${c.reason}`:''}</span></div>)}
   {cmds.data&&!cmds.data.length&&<p className="micro">Chưa có lệnh nào.</p>}
  </Panel>
 </>;
}

/** Seq dùng chung (telemetry/event/health) nên không suy ra mất gói từ khoảng trống; chỉ hiện tỉ lệ khi đã xác minh. */
function receiveText(q:ReportSummary['data_quality']):string{
 const lb=q.received_rate_lower_bound!=null?` (cận dưới ${pct(q.received_rate_lower_bound)})`:'';
 switch(q.receive_status){
  case 'VERIFIED':return `Tỉ lệ nhận ${pct(q.received_rate)} — mọi khoảng trống seq đã xác minh là bản tin khác loại`;
  case 'NO_LOSS_EVIDENCE':return `Không có bằng chứng mất telemetry: khoảng trống seq khớp bản tin health theo thời gian; chưa đủ bằng chứng để tính tỉ lệ${lb}`;
  case 'INSUFFICIENT_EVIDENCE':return `Chưa đủ bằng chứng: ${q.seq_gaps_unclassified??'?'} khoảng trống seq chưa phân loại${lb}`;
  case 'NO_DATA':return 'Chưa có telemetry';
  default:return 'Backend chưa hỗ trợ đánh giá theo bằng chứng (cần cập nhật Backend)';
 }
}

function Reports({core,session,token,notify,onUnauthorized}:LiveProps){
 const enc=core.deviceId?encodeURIComponent(core.deviceId):null;
 const voyages=useResource<VoyageOut[]>(token,enc?`/api/v1/voyages?device_id=${enc}&limit=50`:null,30000,onUnauthorized);
 const [sel,setSel]=useState<string|null>(null);
 const vid=sel??voyages.data?.[0]?.voyage_id??null;
 const sum=useResource<ReportSummary>(token,vid?`/api/v1/voyages/${encodeURIComponent(vid)}/summary`:null,0,onUnauthorized);
 const active=voyages.data?.find(v=>v.status==='ACTIVE');
 const r=sum.data;
 const dist=(d?:{share?:Record<string,number>})=>d?.share?Object.entries(d.share).map(([k,v])=>`${k} ${pct(v)}`).join(' • '):'—';
 const download=(kind:'telemetry.csv'|'alarms.csv'|'report.pdf')=>vid&&apiDownload(token,`/api/v1/voyages/${encodeURIComponent(vid)}/${kind}`,`SVMG_${vid}_${kind}`).then(()=>notify(`Đã tải ${kind}`)).catch(e=>notify(`Tải thất bại: ${e instanceof Error?e.message:e}`));
 const start=()=>confirmAndRun(`Bắt đầu chuyến đi mới cho ${core.deviceId}? (Chỉ ghi Backend, không gửi lệnh xuống thiết bị.)`,
  async()=>{const v=await apiRequest<VoyageOut>(token,'/api/v1/voyages',{method:'POST',body:JSON.stringify({device_id:core.deviceId})});setSel(v.voyage_id);return `Đã bắt đầu ${v.voyage_id}`},notify,voyages.reload);
 const end=()=>active&&confirmAndRun(`Kết thúc chuyến ${active.voyage_id}?`,
  async()=>{await apiRequest<VoyageOut>(token,`/api/v1/voyages/${encodeURIComponent(active.voyage_id)}/end`,{method:'POST'});return `Đã kết thúc ${active.voyage_id}`},notify,()=>{voyages.reload();sum.reload()});
 return <>
  <div className="page-hero"><div><span className="eyebrow">Hồ sơ hải trình • LIVE</span><h1>Báo cáo hành trình</h1><p>Tổng hợp từ telemetry, cảnh báo và lệnh đã lưu trong SQLite. Báo cáo chuyến đang chạy là tạm thời (provisional).</p></div>
   <div className="button-line"><Button disabled={!isSupervisor(session)||!!active||!core.deviceId} onClick={start} title={isSupervisor(session)?'':'Supervisor/Admin'}>Bắt đầu chuyến</Button><Button kind="secondary" disabled={!isSupervisor(session)||!active} onClick={end}>Kết thúc chuyến đang chạy</Button></div></div>
  <ErrorNote res={voyages} what="Danh sách chuyến đi"/>
  <div className="columns">
   <Panel title="Chuyến đi" tag={voyages.data?`${voyages.data.length} chuyến`:''}>
    {(voyages.data??[]).map(v=><div key={v.voyage_id} className="data-line"><span><Button kind={v.voyage_id===vid?'primary':'ghost'} onClick={()=>setSel(v.voyage_id)}>{v.voyage_id}</Button> <Pill kind={v.status==='ACTIVE'?'delivered':'applied'}>{v.status}</Pill></span><span className="micro">{clock(v.started_at)} → {v.ended_at?clock(v.ended_at):'đang chạy'} • {v.source_mode}</span></div>)}
    {voyages.data&&!voyages.data.length&&<p className="micro">Chưa có chuyến đi. Supervisor/Admin có thể bắt đầu chuyến mới.</p>}
   </Panel>
   <Panel title={vid?`Báo cáo ${vid}`:'Báo cáo'} tag={r?(r.provisional?'TẠM THỜI':'Đã chốt'):''}>
    <ErrorNote res={sum} what="Báo cáo"/>
    {r?<>
     <dl className="kv">
      <dt>Nguồn</dt><dd>{r.source_label}</dd>
      <dt>Thời lượng / mẫu</dt><dd>{r.duration_s!=null?`${(r.duration_s/60).toFixed(1)} phút`:'—'} • {r.data_quality.samples} telemetry • {r.data_quality.boots} lần khởi động • lỗi cảm biến {r.data_quality.sensor_fault_samples}</dd>
      <dt>Chất lượng nhận</dt><dd>{receiveText(r.data_quality)}</dd>
      <dt>Khoảng trống seq</dt><dd>{r.data_quality.seq_gaps==null?'—':`${r.data_quality.seq_gaps} / dải ${r.data_quality.seq_span}: sự kiện ${r.data_quality.seq_used_by_events??0} • ngoài chuyến ${r.data_quality.seq_telemetry_outside_voyage??0} • khớp health ${r.data_quality.seq_gaps_health_timing??0} • chưa phân loại ${r.data_quality.seq_gaps_unclassified??0}`}</dd>
      <dt>Roll max / p95 / RMS TB</dt><dd>{deg(r.motion.max_abs_roll_deg)} / {deg(r.motion.p95_abs_roll_deg)} / {deg(r.motion.mean_rms_roll_deg)}</dd>
      <dt>Pitch max</dt><dd>{deg(r.motion.max_abs_pitch_deg)}</dd>
      <dt>Phân bố Baseline B</dt><dd>{dist(r.class_baseline_b)}</dd>
      <dt>Phân bố RF</dt><dd>{dist(r.class_rf)}</dd>
      <dt>Mức cảnh báo</dt><dd>{dist(r.alarm_levels)}</dd>
      <dt>Cảnh báo / MTTA</dt><dd>{r.alarms.total} • MTTA {r.alarms.mtta_s!=null?`${Math.round(r.alarms.mtta_s)}s`:'—'} • báo nhầm/giờ {r.false_alarms_per_hour??'—'}</dd>
      <dt>Lệnh</dt><dd>{r.commands.total} {r.commands.by_state?JSON.stringify(r.commands.by_state):''}</dd>
     </dl>
     {r.notes.map((n,i)=><div key={i} className="note" style={{marginTop:8}}>{n}</div>)}
     {r.disclaimer&&<p className="micro" style={{marginTop:8}}>{r.disclaimer}</p>}
     <div className="button-line" style={{marginTop:10}}><Button kind="secondary" onClick={()=>download('telemetry.csv')}>Telemetry CSV</Button><Button kind="secondary" onClick={()=>download('alarms.csv')}>Cảnh báo CSV</Button><Button kind="secondary" onClick={()=>download('report.pdf')}>Báo cáo PDF</Button></div>
    </>:vid&&!sum.error&&<p className="micro">Đang tải báo cáo…</p>}
   </Panel>
  </div>
 </>;
}

function Replay({core,token,onUnauthorized}:LiveProps){
 const enc=core.deviceId?encodeURIComponent(core.deviceId):null;
 const voyages=useResource<VoyageOut[]>(token,enc?`/api/v1/voyages?device_id=${enc}&limit=50`:null,0,onUnauthorized);
 const [sel,setSel]=useState<string|null>(null);
 const vid=sel??voyages.data?.[0]?.voyage_id??null;
 const rep=useResource<ReplayResponse>(token,vid?`/api/v1/voyages/${encodeURIComponent(vid)}/replay?limit=2000`:null,0,onUnauthorized);
 const pts=rep.data?.telemetry??[];
 const [idx,setIdx]=useState(0);
 const [playing,setPlaying]=useState(false);
 useEffect(()=>{setIdx(0);setPlaying(false)},[vid]);
 useEffect(()=>{if(!playing)return;const id=window.setInterval(()=>setIdx(i=>{if(i>=pts.length-1){setPlaying(false);return i}return i+1}),250);return()=>window.clearInterval(id)},[playing,pts.length]);
 const markers=useMemo(()=>{const ev=rep.data?.alarm_events??[];return ev.map(e=>pts.findIndex(p=>p.boot_id===e.boot_id&&p.seq>=e.seq)).filter(i=>i>=0)},[rep.data,pts]);
 const p=pts[Math.min(idx,pts.length-1)];
 return <>
  <div className="page-hero"><div><span className="eyebrow">Hộp đen hải trình • LIVE</span><h1>Phát lại và đánh giá</h1><p>Phát lại telemetry, sự kiện cảnh báo và lệnh đã lưu của một chuyến đi (dữ liệu thật, không nội suy).</p></div>
   <div className="filter-line"><label htmlFor="live-replay-voyage">Chuyến</label><select id="live-replay-voyage" value={vid??''} onChange={e=>setSel(e.target.value)}>{(voyages.data??[]).map(v=><option key={v.voyage_id} value={v.voyage_id}>{v.voyage_id} ({v.status})</option>)}</select></div></div>
  <ErrorNote res={voyages} what="Chuyến đi"/><ErrorNote res={rep} what="Phát lại"/>
  {voyages.data&&!voyages.data.length&&<div className="note">Chưa có chuyến đi để phát lại. Tạo chuyến ở màn hình Báo cáo hành trình.</div>}
  {rep.data&&<>
   <div className="metrics">
    <Metric label="Mẫu trong cửa sổ" value={`${rep.data.meta.window_samples} / ${rep.data.meta.total_samples}`} note={rep.data.truncated?`Đã cắt ở ${rep.data.limit} mẫu`:'Đầy đủ'} tone="cyan"/>
    <Metric label="Sự kiện cảnh báo" value={String(rep.data.alarm_events.length)} tone={rep.data.alarm_events.length?'amber':'green'}/>
    <Metric label="Lệnh trong chuyến" value={String(rep.data.commands.length)} tone="cyan"/>
    <Metric label="Số lần khởi động" value={String(rep.data.meta.boots)} note={rep.data.meta.source_modes.join(', ')} tone="cyan"/>
   </div>
   <Panel title="Roll / Pitch theo thời gian" tag="Vạch đỏ = sự kiện cảnh báo">
    <LiveLineChart height={240} markers={markers} cursor={pts.length?idx:undefined} series={[{label:'Roll (°)',color:'#0284C7',values:pts.map(t=>t.sensor_ok?t.roll_deg:null)},{label:'Pitch (°)',color:'#D97706',values:pts.map(t=>t.sensor_ok?t.pitch_deg:null)}]} empty="Chuyến đi chưa có telemetry"/>
    {pts.length>0&&<div className="button-line" style={{alignItems:'center'}}>
     <Button kind="secondary" onClick={()=>setPlaying(v=>!v)}>{playing?'Tạm dừng':'Phát'}</Button>
     <input type="range" min={0} max={pts.length-1} value={Math.min(idx,pts.length-1)} onChange={e=>{setPlaying(false);setIdx(Number(e.target.value))}} style={{flex:1}} aria-label="Vị trí phát lại"/>
     <span className="micro">{idx+1}/{pts.length}</span>
    </div>}
    {p&&<dl className="kv"><dt>Thời điểm</dt><dd>{clock(p.server_rx_time)} • seq {p.seq} • T+{p.t_sim_s.toFixed(1)}s • {p.source_mode}{p.scenario_id?` • ${p.scenario_id}`:''}</dd>
     <dt>Roll / Pitch / MAI</dt><dd>{p.sensor_ok?`${deg(p.roll_deg)} / ${deg(p.pitch_deg)}`:'lỗi cảm biến'} / {p.mai??'—'}</dd>
     <dt>Baseline B / RF / mức</dt><dd>{p.class_baseline_b??'—'} / {p.class_rf} / {getAlarmLevelNameVi(p.alarm_level)}</dd>
     <dt>Mô hình / cấu hình</dt><dd>{p.model_version} • v{p.config_version}</dd></dl>}
   </Panel>
  </>}
 </>;
}

function Health({core,token,onUnauthorized}:LiveProps){
 const enc=core.deviceId?encodeURIComponent(core.deviceId):null;
 const hist=useResource<DeviceHealthOut[]>(token,enc?`/api/v1/devices/${enc}/health?limit=60`:null,30000,onUnauthorized);
 const sum=core.health.data?.find(h=>h.device_id===core.deviceId);
 const h=sum?.latest;
 const rows=(hist.data??[]).slice().reverse();
 return <>
  <div className="page-hero"><div><span className="eyebrow">Chẩn đoán phần cứng • LIVE</span><h1>Tình trạng thiết bị</h1><p>Bản tin health thật của ESP32 (heap, uptime, cảm biến, MQTT, bộ đệm). Thiết bị gửi health định kỳ, không phải mỗi telemetry.</p></div><LinkPills core={core}/></div>
  <ErrorNote res={core.health} what="Sức khỏe thiết bị"/>
  <div className="metrics">
   <Metric label="Kết nối" value={sum?(sum.stale?'Im lặng (stale)':sum.state==='online'?'Online':'Offline'):'—'} note={sum?.seconds_since_seen!=null?`Lần cuối ${Math.round(sum.seconds_since_seen)}s trước`:'Chưa thấy thiết bị'} tone={sum&&!sum.stale?'green':'red'}/>
   <Metric label="Cảm biến" value={h?(h.sensor_ok?'OK':'FAULT'):'—'} note={h?.i2c_errors!=null?`Lỗi I2C: ${h.i2c_errors}`:undefined} tone={h?.sensor_ok?'green':'red'}/>
   <Metric label="Heap trống" value={h?`${(h.free_heap_bytes/1024).toFixed(1)} KB`:'—'} note={h?.min_free_heap_bytes!=null?`Thấp nhất ${(h.min_free_heap_bytes/1024).toFixed(1)} KB`:undefined} tone="cyan"/>
   <Metric label="Uptime" value={h?`${(h.uptime_ms/60000).toFixed(1)} phút`:'—'} note={h?`Bản tin ${clock(h.server_rx_time)}`:'Chưa có bản tin health'} tone="cyan"/>
  </div>
  <div className="columns">
   <Panel title="Chi tiết bản tin health mới nhất" tag={core.deviceId??''}>
    {h?<dl className="kv">
     <dt>Thời gian suy luận</dt><dd>{h.inference_ms!=null?`${h.inference_ms} ms`:UNAVAILABLE}</dd>
     <dt>MQTT reconnect</dt><dd>{h.mqtt_reconnects??'—'}</dd>
     <dt>Bộ đệm offline</dt><dd>{h.buffer_used!=null?`${h.buffer_used}/${h.buffer_capacity??'?'} (${h.buffer_used_pct??'—'}%)`:'—'}</dd>
     <dt>Hiệu chuẩn gần nhất</dt><dd>{sum?.last_calibrated_at?clock(sum.last_calibrated_at):'Chưa có'}{sum?.last_calibration_state?` • lần gửi cuối ${sum.last_calibration_state}`:''}</dd>
     <dt>Nguồn dữ liệu</dt><dd>{sum?.source_mode}</dd>
    </dl>:<p className="micro">Backend chưa nhận bản tin health nào từ thiết bị này.</p>}
   </Panel>
   <Panel title="Heap trống theo thời gian" tag={`${rows.length} bản tin`}>
    <ErrorNote res={hist} what="Lịch sử health"/>
    <LiveLineChart height={180} series={[{label:'Heap trống (KB)',color:'#059669',values:rows.map(r=>r.free_heap_bytes/1024)}]} empty="Chưa đủ bản tin health"/>
   </Panel>
  </div>
  <Panel title="Đội thiết bị" tag={`${core.health.data?.length??0} thiết bị`}>
   {(core.health.data??[]).map(d=><div key={d.device_id} className="data-line"><span><b>{d.device_id}</b> <Pill kind={d.stale?'critical':'normal'}>{d.stale?'stale':d.state}</Pill></span><span className="micro">{d.source_mode} • lần cuối {clock(d.last_seen)} • heap {d.latest?`${(d.latest.free_heap_bytes/1024).toFixed(0)} KB`:'—'}</span></div>)}
  </Panel>
 </>;
}

/** Trạng thái đồng thuận. Backend cũ (chưa có `status`) có thể tính UNKNOWN==UNKNOWN là khớp: khi đó chỉ tin tỉ lệ nếu
 *  mọi lớp RF đều là lớp phân loại và chỉ có một nguồn; ngược lại coi là chưa đủ dữ liệu. */
function agreementStatus(a:AgreementStats):'OK'|'INSUFFICIENT_DATA'|'MIXED_SOURCES'{
 if(a.status)return a.status;
 if(a.source_modes.length>1)return 'MIXED_SOURCES';
 const keys=Object.keys(a.by_rf_class);
 return a.samples_considered>0&&keys.length>0&&keys.every(k=>CLASSIFIED.has(k))?'OK':'INSUFFICIENT_DATA';
}

function Model({core,session,token,onUnauthorized}:LiveProps){
 const enc=core.deviceId?encodeURIComponent(core.deviceId):null;
 const op=session.role==='Operator';
 const agree=useResource<AgreementStats>(token,!op&&enc?`/api/v1/monitor/agreement?device_id=${enc}&limit=1000`:null,30000,onUnauthorized);
 const drift=useResource<DriftStatus>(token,!op&&enc?`/api/v1/monitor/drift?device_id=${enc}`:null,60000,onUnauthorized);
 if(op)return <>
  <div className="page-hero"><div><span className="eyebrow">Giới hạn quyền truy cập</span><h1>Model Monitor</h1><p>Theo dõi mô hình học máy và đối chiếu Baseline B</p></div><Pill kind="warning">Sĩ quan trực ca: Không có quyền truy cập</Pill></div>
  <div className="note warning" style={{padding:20}}><h3>Quyền truy cập bị giới hạn</h3><p style={{marginTop:8}}>Màn hình giám sát mô hình dành cho <b>Supervisor</b> và <b>Admin</b>.</p></div></>;
 const rows=core.telemetry.data??[];
 const rfCounts=rows.reduce<Record<string,number>>((m,r)=>{m[r.class_rf]=(m[r.class_rf]??0)+1;return m},{});
 const rfInactive=rows.length>0&&rows.every(r=>r.class_rf==='UNKNOWN');
 const a=agree.data,d=drift.data;
 return <>
  <div className="page-hero"><div><span className="eyebrow">MLOps • LIVE</span><h1>Giám sát mô hình AI</h1><p>Số liệu từ /monitor/agreement và /monitor/drift của Backend. Mô hình quyết định trên thiết bị hiện là Baseline B.</p></div><Pill kind={rfInactive?'fault':'normal'}>{rfInactive?'RF chưa hoạt động (class_rf=UNKNOWN)':'RF có dự đoán'}</Pill></div>
  {rfInactive&&<div className="note warning" style={{marginBottom:14}}><b>Random Forest chưa hoạt động trên firmware chính:</b> toàn bộ {rows.length} mẫu gần nhất có class_rf=UNKNOWN. RF bốn lớp đóng băng (svmg-rf-four-class-m2r6a-0.1.0) chỉ chạy chế độ shadow trong env firmware thử nghiệm, chưa được kiểm chứng trên cảm biến thật. Không trình bày RF như mô hình đang vận hành.</div>}
  <div className="metrics">
   <Metric label="Cặp hợp lệ (RF và Baseline B có lớp)" value={a?String(a.samples_considered):'—'} note={a?`Loại ${a.excluded_unclassified??0} mẫu UNKNOWN/FAULT • ${a.excluded_sensor_fault} mẫu lỗi cảm biến`:undefined} tone="cyan"/>
   <Metric label="Đồng thuận RF – Baseline B" value={!a?'—':agreementStatus(a)==='OK'&&a.agreement_rate!=null?pct(a.agreement_rate):agreementStatus(a)==='MIXED_SOURCES'?'Theo từng nguồn':NO_AGREEMENT}
    note={!a?undefined:agreementStatus(a)==='OK'?`${a.matched}/${a.samples_considered} cặp khớp • ${a.source_label}`:agreementStatus(a)==='MIXED_SOURCES'?'SENSOR và SIMULATION không gộp chung':'Không có cặp mà cả hai mô hình có lớp phân loại'} tone={a&&agreementStatus(a)==='OK'?'cyan':'amber'}/>
   <Metric label="Drift (PSI)" value={d?(d.available?`${d.flagged_count??0} đặc trưng cảnh báo`:UNAVAILABLE):'—'} note={d?.reason??undefined} tone={d?.available?'amber':'red'}/>
   <Metric label="Lớp RF gần nhất" value={rows[0]?.class_rf??'—'} note={Object.entries(rfCounts).map(([k,v])=>`${k}:${v}`).join(' ')} tone="cyan"/>
  </div>
  <div className="columns">
   <Panel title="Đồng thuận theo lớp RF" tag={a?.source_label??''}>
    <ErrorNote res={agree} what="Đồng thuận"/>
    {a&&agreementStatus(a)==='INSUFFICIENT_DATA'&&<div className="note warning"><b>{NO_AGREEMENT}.</b> Không có cặp mẫu nào mà cả Random Forest và Baseline B đều có lớp phân loại hợp lệ; hai mô hình cùng UNKNOWN không được tính là đồng thuận.</div>}
    {a&&agreementStatus(a)==='MIXED_SOURCES'&&Object.entries(a.by_source_mode??{}).map(([mode,v])=><div key={mode} className="data-line"><span><b>{mode}</b></span><span className="micro">{v.matched}/{v.samples_considered} cặp • {pct(v.agreement_rate)}</span></div>)}
    {a&&agreementStatus(a)==='OK'&&Object.entries(a.by_rf_class).map(([k,v])=><div key={k} className="data-line"><span>{k}</span><span className="micro">{v.matched}/{v.rf_total} • {pct(v.rate)}</span></div>)}
    {a&&Object.keys(a.unclassified_labels??{}).length>0&&<p className="micro" style={{marginTop:8}}>Đã loại (nhãn không phải lớp phân loại): {Object.entries(a.unclassified_labels??{}).map(([k,v])=>`${k}: ${v}`).join(' • ')}</p>}
    {a?.notes.map((n,i)=><div key={i} className="note" style={{marginTop:8}}>{n}</div>)}
   </Panel>
   <Panel title="Drift đặc trưng" tag={d?`${d.window_hours} giờ • ${d.window_samples} mẫu`:''}>
    <ErrorNote res={drift} what="Drift"/>
    {d&&(d.available?(d.features??[]).filter(x=>x.flagged).map(x=><div key={x.feature_index} className="data-line"><span>{x.feature_name}</span><span className="micro">PSI {x.psi.toFixed(3)}</span></div>)
     :<div className="note"><b>{UNAVAILABLE}:</b> {d.reason??'Backend chưa có dữ liệu đặc trưng'} (cần {d.expected_features.length} đặc trưng, contract {d.feature_schema_version??'—'}).</div>)}
   </Panel>
  </div>
 </>;
}

export function LivePage(props:LiveProps){
 switch(props.page){
  case 'overview':return <Overview {...props}/>;
  case 'motion':return <Motion {...props}/>;
  case 'alarms':return <Alarms {...props}/>;
  case 'control':return <Control {...props}/>;
  case 'reports':case 'report-detail':return <Reports {...props}/>;
  case 'replay':return <Replay {...props}/>;
  case 'health':return <Health {...props}/>;
  case 'model':return <Model {...props}/>;
  default:return null;
 }
}
