import {useEffect,useMemo,useState} from 'react';
import type {ReactNode,FormEvent} from 'react';
import type {Alarm,Command,Page,Scenario,Session,MotionSnapshot,ZeroCalibration,ReplayPoint} from './domain';
import {computeHealth,computeModelInfo,INITIAL_ALARMS,makeTelemetry,mockLogin,mockRegister,mockForgotPassword,MOCK_VOYAGES,REPLAY_SAMPLES,samples,SCENARIOS} from './mock';
import { ShipMotionVisualizer } from './ShipMotionVisualizer';
import { LiveMotionChart } from './LiveMotionChart';
import { MaiAlarmsChart } from './MaiAlarmsChart';
import { VoyageKinematicDistributionChart, VoyageRfDistributionChart } from './VoyageAnalyticsCharts';
import { ModelConcordanceChart } from './ModelConcordanceChart';

const NAV:{key:Page;label:string;mini:string}[]=[
 {key:'overview',label:'Overview',mini:'Home'}, {key:'motion',label:'Live Motion',mini:'Motion'},
 {key:'alarms',label:'Alarms',mini:'Alarms'}, {key:'control',label:'Control Center',mini:'Control'},
 {key:'reports',label:'Voyage Reports',mini:'Reports'}, {key:'replay',label:'Replay & Review',mini:'Replay'},
 {key:'health',label:'Device Health',mini:'Health'}, {key:'model',label:'Model Monitor',mini:'AI'},
];
const format=(n:number|null|undefined,unit='°')=>n==null?'—':`${n>0?'+':''}${n.toFixed(1)}${unit}`;
const time=(iso?:string)=>iso?new Date(iso).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—';
const canOperate=(s:Session|null)=>!!s&&s.role!=='Operator';
const isAdmin=(s:Session|null)=>s?.role==='Admin';
function Pill({children,kind='neutral'}:{children:ReactNode;kind?:string}){return <span className={`pill ${kind.toLowerCase()}`}>{children}</span>}
function Panel({title,tag,children,footer}:{title:string;tag?:string;children:ReactNode;footer?:ReactNode}){return <section className="panel"><header className="panel-head"><h3>{title}</h3>{tag&&<span className="micro">{tag}</span>}</header>{children}{footer&&<footer className="panel-foot">{footer}</footer>}</section>}
function Metric({label,value,note,tone='cyan'}:{label:string;value:string;note?:string;tone?:string}){return <div className="metric"><span className="label">{label}</span><strong className={`metric-value ${tone}`}>{value}</strong>{note&&<span className="micro">{note}</span>}</div>}
function Button({children,onClick,disabled=false,kind='primary',title,style}:{children:ReactNode;onClick?:()=>void;disabled?:boolean;kind?:string;title?:string;style?:React.CSSProperties}){return <button type="button" className={`btn ${kind}`} style={style} onClick={onClick} disabled={disabled} title={title}>{children}</button>}
export function MotionChart({s,tick,height=190,offline=false}:{s:Scenario;tick:number;height?:number;offline?:boolean}){
 const arr=samples(s,tick,64),w=650,h=height,pad=15;const scale=(v:number)=>h/2-v*(h-2*pad)/42;
 const poly=(key:'roll'|'pitch')=>arr.map((v,i)=>`${(i/(arr.length-1))*w},${scale(v[key])}`).join(' ');
 return <div className="chart-holder" role="img" aria-label="Biểu đồ DEMO góc lắc ngang roll và lắc dọc pitch theo thời gian">
   {offline?<div className="chart-empty"><b>NO LIVE DATA</b><small>OFFLINE / SENSOR FAULT – không suy diễn trạng thái NORMAL</small></div>:<>
   <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" width="100%" height={height} aria-hidden="true">
    {[.25,.5,.75].map(y=><line key={y} x1="0" y1={y*h} x2={w} y2={y*h} stroke="var(--border-subtle, #D0DDEB)" strokeDasharray="4 7" />)}
    <line x1="0" y1={h/2} x2={w} y2={h/2} stroke="var(--border-color, #183E65)" strokeWidth="1.2" />
    <polyline points={poly('roll')} fill="none" stroke="#0284C7" strokeWidth="2.8" vectorEffect="non-scaling-stroke"/>
    <polyline points={poly('pitch')} fill="none" stroke="#D97706" strokeWidth="2.2" vectorEffect="non-scaling-stroke"/>
   </svg><div className="legend"><span><i className="dot cyan-bg" style={{background:'#0284C7'}}/>Roll (°)</span><span><i className="dot amber-bg" style={{background:'#D97706'}}/>Pitch (°)</span><span className="micro">MÔ PHỎNG</span></div></>}
 </div>
}
function DownloadCSV({rows,allowed,voyageId}:{rows:ReplayPoint[];allowed:boolean;voyageId:string}){const download=()=>{
 const header='seq,t_sim_s,roll_deg,pitch_deg,source_mode,synthetic\n';const body=rows.map(r=>`${r.seq},${r.t_sim_s},${r.roll.toFixed(2)},${r.pitch.toFixed(2)},SIMULATION,true`).join('\n');
 const u=URL.createObjectURL(new Blob([header+body],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download=`SVMG_${voyageId}_telemetry.csv`;a.click();URL.revokeObjectURL(u)};
 return <Button onClick={download} disabled={!allowed} title={allowed?"CSV được tính từ fixture DEMO 121 mẫu":"Chỉ Supervisor/Admin có quyền xuất báo cáo"}>Xuất CSV DEMO (121 mẫu)</Button>}

function ReplayChart({samples,currentIndex,onSeek}:{samples:ReplayPoint[];currentIndex:number;onSeek:(idx:number)=>void}){
 const [hoverIdx, setHoverIdx] = useState<number | null>(null);
 const [isDragging, setIsDragging] = useState(false);
 const w=720,h=210,pad=20;
 const maxDeg = 24;
 const scale=(v:number)=>h/2-v*(h-2*pad)/(2*maxDeg);
 const poly=(key:'roll'|'pitch')=>samples.map((v,i)=>`${(i/(samples.length-1))*w},${scale(v[key])}`).join(' ');
 const curX=(currentIndex/(samples.length-1))*w;
 const alarmsWithMarkers=samples.filter(s=>s.alarm_id);

 const handleSeek = (clientX: number, rect: DOMRect) => {
   const ratio=Math.max(0,Math.min(1,(clientX-rect.left)/rect.width));
   onSeek(Math.round(ratio*(samples.length-1)));
 };

 const activeIdx = hoverIdx !== null ? hoverIdx : currentIndex;
 const activeSample = samples[activeIdx] || samples[0];

 return <div className="chart-holder" style={{position:'relative',overflow:'hidden',background:'var(--panel-bg)',borderRadius:8,border:'1px solid var(--border-color)',boxShadow:'var(--card-shadow)',padding:'10px 10px 4px'}}>
  <svg
   viewBox={`0 0 ${w} ${h}`}
   preserveAspectRatio="none"
   width="100%"
   height={h}
   style={{cursor:'crosshair',display:'block'}}
   onPointerDown={(e)=>{
    setIsDragging(true);
    handleSeek(e.clientX, e.currentTarget.getBoundingClientRect());
   }}
   onPointerMove={(e)=>{
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));
    const idx = Math.round(ratio*(samples.length-1));
    setHoverIdx(idx);
    if(isDragging){
      onSeek(idx);
    }
   }}
   onPointerUp={()=>setIsDragging(false)}
   onPointerLeave={()=>{
    setIsDragging(false);
    setHoverIdx(null);
   }}
  >
   {/* Degree Gridlines */}
   {[-15, 0, 15].map(deg => (
    <g key={deg}>
      <line x1="0" y1={scale(deg)} x2={w} y2={scale(deg)} stroke={deg===0?"var(--border-navy, #183E65)":"var(--border-subtle, #DCE5EE)"} strokeWidth={deg===0?1.3:0.8} strokeDasharray={deg===0?undefined:"3 4"} />
      <text x={w - 6} y={scale(deg) - 3} textAnchor="end" fill={deg===0?"var(--text-main, #102B49)":"var(--text-muted, #718EA6)"} fontSize="8.5" fontFamily="monospace">
        {deg > 0 ? `+${deg}°` : `${deg}°`}
      </text>
    </g>
   ))}

   {/* Alarms with markers */}
   {alarmsWithMarkers.map(ap=>{
    const ax=(ap.seq/(samples.length-1))*w;
    const col=ap.alarm_level==='CRITICAL'?'#DC2626':ap.alarm_level==='WARNING'?'#D97706':'#0284C7';
    return <g key={ap.seq} onClick={(e)=>{ e.stopPropagation(); onSeek(ap.seq); }} style={{cursor:'pointer'}}>
     <line x1={ax} y1="0" x2={ax} y2={h} stroke={col} strokeWidth="1.5" strokeDasharray="3 3" opacity="0.85" />
     <rect x={ax - 20} y={4} width={40} height={14} rx={2} fill={col} />
     <text x={ax} y={14} textAnchor="middle" fill="#FFFFFF" fontSize="8" fontFamily="monospace" fontWeight="bold">{ap.alarm_id}</text>
    </g>;
   })}

   {/* Waveform curves */}
   <polyline points={poly('roll')} fill="none" stroke="#0284C7" strokeWidth="2.8" vectorEffect="non-scaling-stroke"/>
   <polyline points={poly('pitch')} fill="none" stroke="#D97706" strokeWidth="2.0" vectorEffect="non-scaling-stroke"/>

   {/* Playhead vertical needle */}
   <line x1={curX} y1="0" x2={curX} y2={h} stroke="#10B981" strokeWidth="2.5" />
   <circle cx={curX} cy={scale(samples[currentIndex]?.roll||0)} r="5" fill="#10B981" stroke="#FFFFFF" strokeWidth="1.5" />

   {/* Hover guide line if different */}
   {hoverIdx !== null && hoverIdx !== currentIndex && (
    <line x1={(hoverIdx/(samples.length-1))*w} y1="0" x2={(hoverIdx/(samples.length-1))*w} y2={h} stroke="#183E65" strokeWidth="1.2" strokeDasharray="2 2" />
   )}
  </svg>

  {/* Floating Readout */}
  <div style={{position:'absolute',top:14,right:16,background:'var(--panel-bg)',border:'1px solid var(--border-color)',borderRadius:6,padding:'4px 10px',fontSize:'0.72rem',display:'flex',gap:10,pointerEvents:'none',color:'var(--text-main)',boxShadow:'var(--card-shadow)'}}>
   <span>MỐC: <b>T+{activeSample.t_sim_s}s</b></span>
   <span className="text-info">ROLL: <b>{activeSample.roll>0?`+${activeSample.roll.toFixed(1)}°`:`${activeSample.roll.toFixed(1)}°`}</b></span>
   <span className="text-warning">PITCH: <b>{activeSample.pitch>0?`+${activeSample.pitch.toFixed(1)}°`:`${activeSample.pitch.toFixed(1)}°`}</b></span>
   <span className={activeSample.mai>=70?'text-danger':activeSample.mai>=35?'text-warning':'text-success'}>MAI: <b>{activeSample.mai}</b></span>
  </div>

  <div className="legend" style={{marginTop:6,display:'flex',justifyContent:'space-between',fontSize:'0.72rem'}}>
   <div style={{display:'flex',gap:12}}>
    <span><i className="dot cyan-bg"/>Roll (°)</span>
    <span><i className="dot amber-bg"/>Pitch (°)</span>
    <span><span className="text-success" style={{fontWeight:'bold'}}>|</span> Playhead T+{samples[currentIndex]?.t_sim_s||0}s</span>
   </div>
   <span className="micro muted">Kéo thả chuột trên biểu đồ để nhảy mốc phát lại • Nhấp vào thẻ cảnh báo để nhảy trực tiếp</span>
  </div>
 </div>;
}
const PROFILE_THRESHOLDS: Record<string,{roll_warning_deg:number;roll_trip_deg:number;mai_alert_threshold:number}> = {
 STANDARD: { roll_warning_deg: 15.0, roll_trip_deg: 22.0, mai_alert_threshold: 0.70 },
 SENSITIVE: { roll_warning_deg: 12.0, roll_trip_deg: 18.0, mai_alert_threshold: 0.65 },
 CONSERVATIVE: { roll_warning_deg: 18.0, roll_trip_deg: 25.0, mai_alert_threshold: 0.75 },
};
export default function App(){
 const [theme,setTheme]=useState<'light'|'dark'>(()=>{
  try{return (localStorage.getItem('svmg_theme') as any)||'light'}catch{return 'light'}
 });
 useEffect(()=>{
  document.documentElement.setAttribute('data-theme',theme);
  try{localStorage.setItem('svmg_theme',theme)}catch{}
 },[theme]);
 const [session,setSession]=useState<Session|null>(null);
 const [authView,setAuthView]=useState<'login'|'register'|'forgot'>('login');
 const [loginName,setLoginName]=useState('operator');
 const [loginPass,setLoginPass]=useState('demo123');
 const [showPassword,setShowPassword]=useState(false);
 const [loginError,setLoginError]=useState('');

 const [regFullName,setRegFullName]=useState('');
 const [regUsername,setRegUsername]=useState('');
 const [regPass,setRegPass]=useState('');
 const [regConfirmPass,setRegConfirmPass]=useState('');
 const [regShowPass,setRegShowPass]=useState(false);
 const [regError,setRegError]=useState('');
 const [regPendingNotice,setRegPendingNotice]=useState('');

 const [forgotIdentifier,setForgotIdentifier]=useState('');
 const [forgotError,setForgotError]=useState('');
 const [forgotPendingNotice,setForgotPendingNotice]=useState('');
 const [page,setPage]=useState<Page>('overview');const [scenario,setScenario]=useState<Scenario>('S0');const [tick,setTick]=useState(62);const [profile,setProfile]=useState('STANDARD');const [configVersion,setConfigVersion]=useState(7);const [previousProfile,setPreviousProfile]=useState('STANDARD');const [hasPreviousProfile,setHasPreviousProfile]=useState(false);const [timewarp,setTimewarp]=useState(1);const [activeModel,setActiveModel]=useState<'RF'|'BASELINE_B'>('RF');
 const [alarms,setAlarms]=useState<Alarm[]>(INITIAL_ALARMS);const [alarmId,setAlarmId]=useState<string|null>(null);const [alarmFilter,setAlarmFilter]=useState('ALL');
 const [commands,setCommands]=useState<Command[]>([]);const [notice,setNotice]=useState('');const [replayIndex,setReplayIndex]=useState(0);const [playing,setPlaying]=useState(false);const [speed,setSpeed]=useState(1);
 const [selectedVoyageId,setSelectedVoyageId]=useState('V-2026-001');
 const [latestSnapshot,setLatestSnapshot]=useState<MotionSnapshot|null>(null);
 const [zeroCalibration,setZeroCalibration]=useState<ZeroCalibration|null>(null);
 const [hoveredMotionSample, setHoveredMotionSample] = useState<{ roll: number; pitch: number; t: number } | null>(null);
 const thresholds = PROFILE_THRESHOLDS[profile] || PROFILE_THRESHOLDS['STANDARD'];
 const selectedVoyage = useMemo(()=>MOCK_VOYAGES.find(v=>v.id===selectedVoyageId)||MOCK_VOYAGES[0],[selectedVoyageId]);
 const telemetry=useMemo(()=>makeTelemetry(scenario,tick,configVersion),[scenario,tick,configVersion]);
 const health=useMemo(()=>computeHealth(scenario,tick),[scenario,tick]);
 const modelInfo=useMemo(()=>computeModelInfo(activeModel),[activeModel]);
 useEffect(()=>{const ms=Math.max(100,Math.round(1100/(timewarp||1)));const id=window.setInterval(()=>setTick(v=>v+1),ms);return()=>clearInterval(id)},[timewarp]);
 useEffect(()=>{
  if(!playing)return;
  const interval=Math.max(80,Math.round(900/Math.max(1,speed)));
  const id=window.setInterval(()=>{
   setReplayIndex(i=>{
    if(i>=REPLAY_SAMPLES.length-1){
     setPlaying(false);
     return REPLAY_SAMPLES.length-1;
    }
    return i+1;
   });
  },interval);
  return()=>clearInterval(id);
 },[playing,speed]);
 const goto=(p:Page)=>{if(p==='model'&&!canOperate(session)){setNotice('Chỉ Supervisor/Admin được truy cập Model Monitor.');return;}setPage(p);setAlarmId(null);window.scrollTo({top:0,behavior:'smooth'})};
 const submitLogin=(e:FormEvent)=>{
  e.preventDefault();
  const result=mockLogin(loginName,loginPass);
  if(!result){
   setLoginError('Tài khoản hoặc mã truy cập (passcode) chưa đúng. Vui lòng kiểm tra lại.');
   return;
  }
  setSession(result);
  setPage('overview');
  setLoginError('');
  setNotice(`Đăng nhập thành công • Vai trò: ${result.role} (${result.displayName})`);
 };
 const submitRegister=(e:FormEvent)=>{
  e.preventDefault();
  setRegError('');
  setRegPendingNotice('');
  if(!regUsername.trim()||!regPass){
   setRegError('Vui lòng điền đầy đủ Tên đăng nhập và Mật khẩu.');
   return;
  }
  if(regPass!==regConfirmPass){
   setRegError('Mật khẩu xác nhận không khớp. Vui lòng nhập lại.');
   return;
  }
  if(regPass.length<6){
   setRegError('Mật khẩu phải có độ dài tối thiểu 6 ký tự.');
   return;
  }
  const res=mockRegister(regUsername,regPass,regFullName);
  if(!res.success){
   setRegError(res.error||'Đăng ký không thành công.');
   return;
  }
  setRegPendingNotice(res.message);
  setLoginName(regUsername.trim().toLowerCase());
  setLoginPass(regPass);
 };
 const submitForgotPassword=(e:FormEvent)=>{
  e.preventDefault();
  setForgotError('');
  setForgotPendingNotice('');
  if(!forgotIdentifier.trim()){
   setForgotError('Vui lòng nhập Tên đăng nhập hoặc Email sĩ quan.');
   return;
  }
  const res=mockForgotPassword(forgotIdentifier);
  if(!res.success){
   setForgotError(res.error||'Yêu cầu không hợp lệ.');
   return;
  }
  setForgotPendingNotice(res.message);
 };
 const logout=()=>{setSession(null);setPage('overview');setPlaying(false);setNotice('')};
 const ackAlarm=(id:string)=>{setAlarms(old=>old.map(a=>a.id===id&&a.status==='RAISED'?{...a,status:'ACKED',ackedAt:new Date().toISOString()}:a));setNotice(`ACK ${id} — chỉ cập nhật DEMO; không gửi MQTT`)};
 const muteAlarm=(id:string)=>{const a=alarms.find(item=>item.id===id);if(!a||a.level==='CRITICAL'){setNotice('REJECTED: không thể MUTE khi mức CRITICAL.');return}setAlarms(old=>old.map(v=>v.id===id?{...v,mutedUntil:new Date(Date.now()+300000).toISOString()}:v));setNotice(`MUTE ${id} 300s (DEMO)`) };
 const reviewAlarm=(id:string,label:'TRUE'|'FALSE'|'UNCERTAIN')=>{
  setAlarms(old=>old.map(a=>a.id===id?{...a,review:label}:a));
  setNotice(`Đã lưu thẩm định ${id}: ${label === 'TRUE' ? 'ĐÚNG (True Positive)' : label === 'FALSE' ? 'SAI (False Positive)' : 'CHƯA RÕ (Uncertain)'} vào Mock State.`);
 };
 const sendCommand=(name:string,requireAdmin=false,argument?:string)=>{
  if(requireAdmin?!isAdmin(session):!canOperate(session)){setNotice(`Không đủ quyền thực hiện lệnh (Bảng 3.1: ${session?.role??'Operator'} không được phép).`);return}
  const id=`CMD-${Math.random().toString(16).slice(2,6).toUpperCase()}-${String(Date.now()).slice(-4)}`;
  const isTimeout=(name==='test_timeout');
  const isStatic=(scenario==='S0');
  const isSnapshot=(name==='request_snapshot');
  const isCalZero=(name==='calibrate_zero');
  const isRollback=(name==='rollback');
  const isSetMode=(name==='set_mode');

  const invalid=(isCalZero&&!isStatic)||(isSetMode&&argument==='SENSOR')||(name==='set_scenario'&&!argument)||(isRollback&&!hasPreviousProfile);
  const reason=(isCalZero&&!isStatic)?'NOT_STATIC: Độ lệch chuẩn roll σ > 1.0° trong 30s đo; tàu đang dao động, không đạt điều kiện tĩnh':
               (isSetMode&&argument==='SENSOR')?'NO_SENSOR_IN_MOCK: Chưa kết nối cảm biến phần cứng MPU6050 trong môi trường demo TV4':
               (isRollback&&!hasPreviousProfile)?'NO_PREVIOUS_VERSION: Chưa có bản cấu hình trước đó để rollback':'BAD_PARAM';

  const displayName=isTimeout?'[TEST UTILITY] test_timeout (Mô phỏng TTL 30s)':name+(argument?` (${argument})`:'');

  setCommands(old=>[{
   id,name:displayName,status:'SENT',
   detail:isTimeout?'Khởi chạy tiện ích kiểm thử: Đang gửi lệnh thử nghiệm timeout TTL 30s...':
          isCalZero?'Đang lấy mẫu và kiểm tra độ ổn định tín hiệu trong 30s (độ lệch chuẩn roll)...':
          'Đang xuất bản qua topic MQTT QoS 1 tới thiết bị giám sát...',
   issuedAt:new Date().toISOString(),version:configVersion,issued_by:session?.username,is_test_utility:isTimeout
  },...old]);

  window.setTimeout(()=>setCommands(old=>old.map(c=>c.id===id?{
   ...c,status:'DELIVERED',
   detail:isTimeout?'Thiết bị đã nhận lệnh thử nghiệm; đang đợi phản hồi ACK (mô phỏng mất gói)...':
          isCalZero?'Thiết bị đang đo phương sai và độ lệch 0 trong cửa sổ 30s...':
          'Thiết bị đã nhận lệnh (QoS 1 PUBACK); đang kiểm tra...'
  }:c)),280);

  window.setTimeout(()=>{
   if(isTimeout){
    setCommands(old=>old.map(c=>c.id===id?{
     ...c,status:'TIMEOUT',detail:'EXPIRED: Quá hạn TTL 30s không nhận được phản hồi ACK từ thiết bị (Tiện ích kiểm thử).',reason:'TTL_EXPIRED'
    }:c));
    setNotice(`${id} TIMEOUT: Quá hạn TTL 30s không nhận phản hồi (Tiện ích kiểm thử)`);
    return;
   }

   if(invalid){
    setCommands(old=>old.map(c=>c.id===id?{
     ...c,status:'REJECTED',detail:reason,reason:reason.split(':')[0]
    }:c));
    setNotice(`REJECTED: ${reason}`);
    return;
   }

   let appliedDetail='ACK mô phỏng (APPLIED thành công vào cấu hình thiết bị)';
   if(name==='set_profile'&&argument){
    setPreviousProfile(profile);setHasPreviousProfile(true);setProfile(argument);setConfigVersion(v=>v+1);
    appliedDetail=`Áp dụng Profile ${argument} thành công. Config version nâng lên v${configVersion+1}.`;
   }
   if(isRollback){
    setProfile(previousProfile);setHasPreviousProfile(false);setConfigVersion(v=>v+1);
    appliedDetail=`Đã rollback về Profile ${previousProfile}. Config version mới: v${configVersion+1}.`;
   }
   if(name==='set_scenario'&&argument){
    setScenario(argument as Scenario);
    appliedDetail=`Đã kích hoạt kịch bản mô phỏng ${argument}. Dữ liệu telemetry cập nhật ngay.`;
   }
   if(name==='set_timewarp'&&argument){
    const tw=Number(argument);setTimewarp(tw);
    appliedDetail=`Tốc độ thời gian ảo trong SIMULATION chuyển mức ×${tw}.`;
   }
   if(name==='set_model'&&argument){
    setActiveModel(argument as 'RF'|'BASELINE_B');
    appliedDetail=`Mô hình quyết định chính: ${argument==='RF'?'Random Forest (Dữ liệu demo)':'Baseline B (Dữ liệu demo)'}. Không có suy luận AI trên client.`;
   }
   if(isCalZero){
    const cal:ZeroCalibration={
     roll_offset_deg:0.12,pitch_offset_deg:-0.05,std_dev_roll:0.15,duration_s:30,calibrated_at:new Date().toISOString()
    };
    setZeroCalibration(cal);setConfigVersion(v=>v+1);
    appliedDetail=`Tín hiệu tĩnh 30s đạt chuẩn (σ=0.15° ≤ 1.0°). Đã lưu điểm 0: roll +0.12°, pitch -0.05° vào cấu hình v${configVersion+1}.`;
   }
   if(isSnapshot){
    const snap:MotionSnapshot={
     snapshot_id:`SNAP-${String(Date.now()).slice(-6)}`,
     timestamp:new Date().toISOString(),window_s:180,sample_count:36,
     roll_min:telemetry?.rms_roll_deg?-telemetry.rms_roll_deg:-3.2,
     roll_max:telemetry?.rms_roll_deg?+telemetry.rms_roll_deg:+3.2,
     pitch_min:-1.6,pitch_max:1.8,
     rms_roll_deg:telemetry?.rms_roll_deg||2.4,
     mai:telemetry?.mai||15,
     triggered_by:session?.username||'supervisor'
    };
    setLatestSnapshot(snap);
    appliedDetail=`Bản chụp 180s (36 mẫu) đã được tạo và lưu trong Mock State: ${snap.snapshot_id}.`;
   }

   setCommands(old=>old.map(c=>c.id===id?{...c,status:'APPLIED',detail:appliedDetail}:c));
   setNotice(`${name} — APPLIED thành công trong Mock State`);
  },780);
 };
 const renderAlarm=(a:Alarm,detail=false)=><div className={`alarm-entry ${a.level.toLowerCase()}`} key={a.id}>
  <div className="alarm-title"><div><b>{a.id}</b> <span className="muted">• {a.title}</span></div><Pill kind={a.level}>{a.level}</Pill></div>
  <div className="data-line"><span className="micro">{a.raisedAt.startsWith('2026')?time(a.raisedAt):a.raisedAt} · {a.status}</span>{a.mutedUntil&&<span className="micro">MUTED (DEMO)</span>}</div>
  {detail&&<div className="button-line"><Button kind="secondary" disabled={a.status!=='RAISED'} onClick={()=>ackAlarm(a.id)}>ACK</Button><Button kind="ghost" disabled={a.status==='CLEARED'||a.level==='CRITICAL'} title={a.level==='CRITICAL'?'Không mute khi CRITICAL':''} onClick={()=>muteAlarm(a.id)}>Mute ≤300s</Button></div>}
  {!detail&&<Button kind="ghost" onClick={()=>{setAlarmId(a.id);setPage('alarms')}}>Xem chi tiết →</Button>}
 </div>;
 const renderPage=()=>{
  switch(page){
  case 'overview':{
   const raisedAlarms = alarms.filter(a => a.status === 'RAISED');
   const ackedAlarms = alarms.filter(a => a.status === 'ACKED');
   const activeSeverity = telemetry?.alarm_level || 'NORMAL';
   const isConnected = !!telemetry?.sensor_ok;

   return <>
    <div className="page-hero">
     <div>
      <span className="eyebrow">VESSEL DEMO 01 / CẦU TÀU (BRIDGE DASHBOARD)</span>
      <h1>Vessel Overview</h1>
      <p>Tổng quan vận hành: Trạng thái an toàn, kết nối thiết bị IoT, mức bất thường MAI và cảnh báo ca trực.</p>
     </div>
     <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
      <Pill kind={isConnected ? 'normal' : scenario==='OFFLINE' ? 'critical' : 'fault'}>
       {isConnected ? '● KẾT NỐI ONLINE' : scenario==='OFFLINE' ? 'OFFLINE (>30s)' : 'SENSOR FAULT (I2C)'}
      </Pill>
      <Pill kind={activeSeverity}>
       {activeSeverity}
      </Pill>
     </div>
    </div>

    <div className="metrics">
     <Metric
      label="MỨC CẢNH BÁO TÀU"
      value={activeSeverity}
      note={activeSeverity === 'CRITICAL' ? 'Nguy cấp: Vượt ngưỡng Trip' : activeSeverity === 'WARNING' ? 'Cảnh báo: Biên độ lắc lớn' : 'An toàn trong giới hạn'}
      tone={activeSeverity === 'CRITICAL' ? 'red' : activeSeverity === 'WARNING' ? 'amber' : 'green'}
     />
     <Metric
      label="KẾT NỐI THIẾT BỊ"
      value={isConnected ? 'BÌNH THƯỜNG' : (scenario === 'OFFLINE' ? 'OFFLINE' : 'LỖI CẢM BIẾN')}
      note={isConnected ? 'ESP32 • MPU6050 (400kHz)' : 'Mất tín hiệu viễn trắc'}
      tone={isConnected ? 'cyan' : (scenario === 'OFFLINE' ? 'red' : 'amber')}
     />
     <Metric
      label="CHỈ SỐ BẤT THƯỜNG (MAI)"
      value={isConnected ? `${telemetry.mai} / 100` : '—'}
      note={(telemetry?.mai||0) >= 70 ? 'Vượt ngưỡng cảnh giác (≥70)' : (telemetry?.mai||0) >= 35 ? 'Mức theo dõi (35-70)' : 'Biển êm / Bình thường (<35)'}
      tone={(telemetry?.mai||0) >= 70 ? 'red' : (telemetry?.mai||0) >= 35 ? 'amber' : 'green'}
     />
     <Metric
      label="CẢNH BÁO CA TRỰC"
      value={activeSeverity === 'NORMAL' && raisedAlarms.length === 0 ? '0 ĐANG MỞ' : `${raisedAlarms.length} ĐANG MỞ`}
      note={activeSeverity === 'NORMAL' && raisedAlarms.length === 0 ? 'Toàn bộ hệ thống an toàn' : `${ackedAlarms.length} đã tiếp nhận (ACK)`}
      tone={raisedAlarms.length > 0 ? 'red' : 'green'}
     />
    </div>

    <div className="columns">
     <div>
      {/* Panel 1: Kinematics Summary */}
      <Panel title="TÓM TẮT ĐỘNG HỌC THÂN TÀU (KINEMATICS SNAPSHOT)" tag="TỨC THỜI • FR05">
       <div style={{marginBottom:14}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:4}}>
         <span className="micro" style={{fontWeight:600}}>CHỈ SỐ BẤT THƯỜNG MAI HIỆN TẠI</span>
         <span className={isConnected ? (((telemetry?.mai||0)>=70)?'text-danger':((telemetry?.mai||0)>=35)?'text-warning':'text-success') : 'text-muted'} style={{fontWeight:700,fontFamily:'monospace'}}>
          {isConnected ? `${telemetry?.mai} / 100` : 'KHÔNG KHẢ DỤNG'}
         </span>
        </div>
        <div style={{width:'100%',height:8,background:'var(--border-color)',borderRadius:4,overflow:'hidden'}}>
         <div
          style={{
           width:`${Math.min(100, Math.max(0, isConnected ? (telemetry?.mai||0) : 0))}%`,
           height:'100%',
           background:(telemetry?.mai||0)>=70?'var(--status-red-text)':(telemetry?.mai||0)>=35?'var(--status-amber-text)':'var(--status-green-text)',
           transition:'width 0.3s ease-out',
          }}
         />
        </div>
        <div style={{display:'flex',justifyContent:'space-between',fontSize:'0.65rem',color:'var(--text-muted)',marginTop:3}}>
         <span>0 (Bình thường)</span>
         <span>Ngưỡng cảnh giác: 35</span>
         <span>Nguy cấp: 70+</span>
        </div>
       </div>

       <dl className="kv">
        <dt>Góc lắc ngang tức thời (Roll)</dt>
        <dd className={isConnected ? (Math.abs(telemetry?.roll_deg||0) >= thresholds.roll_warning_deg ? 'text-danger' : 'text-info') : 'text-muted'} style={{fontWeight:600}}>
         {isConnected ? `${format(telemetry?.roll_deg)} (${(telemetry?.roll_deg||0) > 0.1 ? 'Mạn phải / STBD' : (telemetry?.roll_deg||0) < -0.1 ? 'Mạn trái / PORT' : 'Cân bằng'})` : '—'}
        </dd>
        <dt>Góc lắc dọc tức thời (Pitch)</dt>
        <dd className="text-warning" style={{fontWeight:600}}>
         {isConnected ? `${format(telemetry?.pitch_deg)} (${(telemetry?.pitch_deg||0) > 0.1 ? 'Ngóc mũi / BOW UP' : (telemetry?.pitch_deg||0) < -0.1 ? 'Chúi mũi / BOW DOWN' : 'Mức'})` : '—'}
        </dd>
        <dt>Nhận dạng TinyML (Random Forest)</dt>
        <dd className="text-success" style={{fontWeight:600}}>{telemetry?.class_rf ?? 'UNKNOWN'}</dd>
        <dt>Ngưỡng an toàn mô phỏng</dt>
        <dd>Warn ±{thresholds.roll_warning_deg}° • Trip ±{thresholds.roll_trip_deg}°</dd>
       </dl>

       <div style={{marginTop:16,paddingTop:12,borderTop:'1px solid var(--border-subtle)',display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:8}}>
        <span className="micro muted">Xem biểu đồ dao động 280px & mô hình tàu 2D</span>
        <Button kind="primary" onClick={()=>goto('motion')}>Mở Live Motion chi tiết →</Button>
       </div>
      </Panel>

      {/* Panel 2: Thông số tàu & kết nối */}
      <Panel title="THÔNG SỐ TÀU & KẾT NỐI THIẾT BỊ" tag="vessel-demo-01">
       <dl className="kv">
        <dt>Tên tàu / Nhận dạng</dt><dd>Smart Vessel Demo 01 (IMO-9876543)</dd>
        <dt>Chế độ nguồn dữ liệu (Source Mode)</dt><dd>{telemetry?.source_mode ?? 'SIMULATION'}</dd>
        <dt>Kịch bản kiểm thử hiện hành</dt><dd className="text-info" style={{fontWeight:600}}>{scenario}</dd>
        <dt>Đồng hồ mô phỏng (t_sim_s)</dt><dd>T+{telemetry?.t_sim_s ?? '—'}s (Chu kỳ 5.0s)</dd>
        <dt>Cấu hình Profile / Phiên bản</dt><dd>{profile} (v{configVersion})</dd>
        <dt>Sĩ quan ca trực hiện tại</dt><dd>{session?.username} ({session?.role})</dd>
       </dl>
       <div className="button-line" style={{marginTop:12}}>
        <Button kind="ghost" onClick={()=>goto('control')}>Điều chỉnh Profile / Lệnh →</Button>
        <Button kind="ghost" onClick={()=>goto('health')}>Kiểm tra Device Health →</Button>
       </div>
      </Panel>
     </div>

     <div>
      {/* Panel 3: Actionable Alarms */}
      <Panel title="CẢNH BÁO ĐANG MỞ & CẦN XỬ LÝ (ACTIONABLE ALARMS)" tag={raisedAlarms.length > 0 ? `${raisedAlarms.length} SỰ KIỆN CHỜ XỬ LÝ` : 'AN TOÀN'}>
       {raisedAlarms.length > 0 ? (
        <>
         <p className="micro" style={{marginBottom:10}}>Các cảnh báo đang mở cần sĩ quan trực ca tiếp nhận (ACK) hoặc kiểm tra an toàn:</p>
         {raisedAlarms.slice(0, 3).map(a => renderAlarm(a, true))}
        </>
       ) : (
        <div className="note success" style={{marginBottom:12}}>
         <b>✓ TRẠNG THÁI CA TRỰC AN TOÀN:</b> Hiện không có cảnh báo nào ở trạng thái chờ xử lý (RAISED). Mọi dao động thân tàu và chỉ số MAI đều nằm trong ngưỡng an toàn cho phép.
        </div>
       )}

       <div style={{marginTop:14,display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:8}}>
        <span className="micro muted">Tổng cộng {alarms.length} sự kiện trong phiên</span>
        <Button kind="secondary" onClick={()=>goto('alarms')}>Xem toàn bộ danh sách cảnh báo →</Button>
       </div>
      </Panel>

      {/* Panel 4: Lối tắt điều hướng nhanh */}
      <Panel title="LỐI TẮT VẬN HÀNH CA TRỰC (WORKFLOW SHORTCUTS)" tag="ĐIỀU HƯỚNG NHANH">
       <div className="more-list">
        <button type="button" onClick={()=>goto('motion')}>
         <div>
          <strong style={{display:'block'}}>1. Giám sát dao động Live Motion</strong>
          <small className="muted">Biểu đồ Roll/Pitch oscilloscope 4 cửa sổ, Freeze Frame & mô hình tàu 2D</small>
         </div>
         <span>→</span>
        </button>
        <button type="button" onClick={()=>goto('alarms')}>
         <div>
          <strong style={{display:'block'}}>2. Trung tâm cảnh báo Alarms</strong>
          <small className="muted">Quản lý vòng đời cảnh báo, thời gian phản hồi MTTA & biểu đồ MAI</small>
         </div>
         <span>→</span>
        </button>
        <button type="button" onClick={()=>goto('control')}>
         <div>
          <strong style={{display:'block'}}>3. Trung tâm điều khiển Control Center</strong>
          <small className="muted">Gửi lệnh cấu hình, đổi profile ngưỡng an toàn và đổi kịch bản</small>
         </div>
         <span>→</span>
        </button>
        <button type="button" onClick={()=>goto('reports')}>
         <div>
          <strong style={{display:'block'}}>4. Báo cáo hành trình & Replay</strong>
          <small className="muted">Kiểm toán động học T11, xuất CSV 121 mẫu và thẩm định trực ca</small>
         </div>
         <span>→</span>
        </button>
       </div>
      </Panel>
     </div>
    </div>
   </>;
  }
  case 'motion':return <>
   <div className="page-hero">
    <div>
     <span className="eyebrow">TELEMETRY DEEP DIVE / FR05 • FR20</span>
     <h1>Live Motion</h1>
     <p>Giám sát dao động thân tàu thời gian thực: Đồ thị dao động Roll/Pitch, mô hình chuyển động 2D, đối chiếu TinyML và xu hướng MAI.</p>
    </div>
    <div className="button-line" style={{marginTop:0}}>
     <Button kind="ghost" onClick={()=>goto('overview')}>← Về Overview</Button>
     <Button kind="ghost" onClick={()=>goto('alarms')}>Danh sách cảnh báo →</Button>
    </div>
   </div>

   <div className="metrics">
    <Metric
     label="ROLL TỨC THỜI"
     value={telemetry?.sensor_ok?format(telemetry.roll_deg):'—'}
     note={telemetry?.sensor_ok ? (telemetry.roll_deg > 0.1 ? 'Mạn phải (STBD)' : telemetry.roll_deg < -0.1 ? 'Mạn trái (PORT)' : 'Cân bằng (EVEN)') : 'Mất dữ liệu'}
     tone={Math.abs(telemetry?.roll_deg||0)>=thresholds.roll_warning_deg?'red':'cyan'}
    />
    <Metric
     label="PITCH TỨC THỜI"
     value={telemetry?.sensor_ok?format(telemetry.pitch_deg):'—'}
     note={telemetry?.sensor_ok ? (telemetry.pitch_deg > 0.1 ? 'Ngóc mũi (BOW UP)' : telemetry.pitch_deg < -0.1 ? 'Chúi mũi (BOW DOWN)' : 'Mức (LEVEL)') : 'Mất dữ liệu'}
     tone="amber"
    />
    <Metric
     label="CHỈ SỐ MAI"
     value={telemetry?.sensor_ok?`${telemetry.mai} / 100`:'—'}
     note={(telemetry?.mai||0)>=70?'Nguy cấp (Critical)':(telemetry?.mai||0)>=35?'Cảnh giác (Elevated)':'Bình thường (Safe)'}
     tone={(telemetry?.mai||0)>=70?'red':(telemetry?.mai||0)>=35?'amber':'green'}
    />
    <Metric
     label="KỊCH BẢN & MỐC GIỜ"
     value={scenario}
     note={telemetry?.t_sim_s !== undefined ? `T+${telemetry.t_sim_s}s (Chu kỳ 5.0s)` : '—'}
     tone="cyan"
    />
   </div>

   {/* 2D Vessel Motion Visualizer (Full Interactive Model) */}
   <Panel title="TRỰC QUAN HÓA DAO ĐỘNG THÂN TÀU (2D MOTION VISUALIZER)" tag="ĐỒNG BỘ CON TRỎ & FREEZE FRAME">
    <ShipMotionVisualizer
     rollDeg={hoveredMotionSample ? hoveredMotionSample.roll : (telemetry?.sensor_ok ? telemetry.roll_deg : null)}
     pitchDeg={hoveredMotionSample ? hoveredMotionSample.pitch : (telemetry?.sensor_ok ? telemetry.pitch_deg : null)}
     mai={telemetry?.sensor_ok ? telemetry.mai : null}
     alarmLevel={telemetry?.alarm_level || 'NORMAL'}
     scenario={scenario}
     classRf={telemetry?.class_rf || 'NORMAL'}
     sourceMode={telemetry?.source_mode || 'SIMULATION'}
     sensorOk={telemetry?.sensor_ok}
     compact={false}
    />
   </Panel>

   {/* Main Interactive Oscilloscope Waveform */}
   <Panel title="ĐỒ THỊ DAO ĐỘNG THỜI GIAN THỰC (INTERACTIVE OSCILLOSCOPE)" tag="LIVE MOCK • 1.1s/STEP">
    <LiveMotionChart
     scenario={scenario}
     tick={tick}
     height={280}
     offline={!telemetry?.sensor_ok}
     warningDeg={thresholds.roll_warning_deg}
     tripDeg={thresholds.roll_trip_deg}
     alarms={alarms}
     onHoverSample={setHoveredMotionSample}
    />
   </Panel>

   {/* MAI Timeline Trend & Alarm Triggers */}
   <Panel title="XU HƯỚNG CHỈ SỐ BẤT THƯỜNG (MAI TIMELINE & ALARM TRIGGERS)" tag="TINYML ANOMALY TRACKING">
    <MaiAlarmsChart
     currentMai={telemetry?.sensor_ok ? telemetry.mai : 0}
     alarms={alarms}
     thresholdCaution={35}
     thresholdCritical={Math.round(thresholds.mai_alert_threshold * 100)}
     onSelectAlarm={(id)=>{setAlarmId(id);setPage('alarms');}}
     height={170}
     offline={!telemetry?.sensor_ok}
    />
   </Panel>

   <div className="columns">
    <Panel title="MÔ HÌNH PHÂN LOẠI & ĐỐI CHIẾU SHADOW (FR20)" tag="RANDOM FOREST VS BASELINE B">
     <dl className="kv">
      <dt>Random Forest (Mô hình chính)</dt><dd className="text-info" style={{fontWeight:600}}>{telemetry?.class_rf??'UNKNOWN'}</dd>
      <dt>Baseline B (Mô hình bóng)</dt><dd className="text-warning" style={{fontWeight:600}}>{telemetry?.class_baseline_b??'UNKNOWN'}</dd>
      <dt>Độ đồng thuận (Concordance)</dt>
      <dd className={!telemetry?.sensor_ok ? 'text-muted' : (telemetry.class_rf === telemetry.class_baseline_b ? 'text-success' : 'text-warning')} style={{fontWeight:600}}>
       {!telemetry?.sensor_ok ? 'N/A (CẢM BIẾN LỖI/OFFLINE)' : (telemetry.class_rf === telemetry.class_baseline_b ? '✓ ĐỒNG THUẬN (CONCORDANT)' : '⚠ BẤT ĐỒNG (DISCREPANCY)')}
      </dd>
      <dt>Phiên bản mô hình (Registry)</dt><dd>{telemetry?.model_version ?? 'RF-DEMO-v1'}</dd>
      <dt>Tình trạng cảm biến IMU</dt>
      <dd className={telemetry?.sensor_ok ? 'text-success' : 'text-danger'} style={{fontWeight:600}}>
       {telemetry?.sensor_ok ? 'BÌNH THƯỜNG (MPU6050 400kHz)' : 'MẤT KẾT NỐI / I2C NACK'}
      </dd>
     </dl>
    </Panel>
    <Panel title="CHẤT LƯỢNG NGUỒN & CƠ CHẾ ĐỒNG BỘ" tag="NGUYÊN TẮC AN TOÀN">
     <p>Mô hình 2D phía trên đồng bộ trực tiếp với con trỏ của đồ thị dao động. Khi rê chuột trên biểu đồ hoặc bấm Freeze Frame, thân tàu sẽ xoay theo góc nghiêng của mẫu tương ứng.</p>
     <p className="note" style={{marginTop:10}}>Khi mất kết nối hoặc lỗi cảm biến, hệ thống tuân thủ nghiêm ngặt nguyên tắc: không hiển thị trạng thái NORMAL giả mạo và không làm mới đường biểu đồ như dữ liệu thực.</p>
    </Panel>
   </div>
  </>;
  case 'alarms':return <>
   <header className="page-heading">
    <h1>Alarms</h1>
    <p>Vòng đời RAISED → ACKED → CLEARED, tắt còi mô phỏng có điều kiện.</p>
   </header>
   <div className="metrics">
    <Metric label="ACTIVE" value={String(alarms.filter(a=>a.status==='RAISED').length)} tone="red"/>
    <Metric label="ACKED" value={String(alarms.filter(a=>a.status==='ACKED').length)}/>
    <Metric label="CLEARED" value={String(alarms.filter(a=>a.status==='CLEARED').length)}/>
    <Metric label="MTTA (DEMO)" value={(()=>{const list=alarms.filter(a=>a.ackedAt);return list.length?`${Math.round(list.reduce((a,v)=>a+(new Date(v.ackedAt!).getTime()-new Date(v.raisedAt).getTime())/1000,0)/list.length)}s`:'—'})()}/>
   </div>

   <div style={{marginBottom:18}}>
    <MaiAlarmsChart
     currentMai={telemetry?.sensor_ok ? telemetry.mai : 0}
     alarms={alarms}
     thresholdCaution={35}
     thresholdCritical={Math.round(thresholds.mai_alert_threshold * 100)}
     onSelectAlarm={(id)=>setAlarmId(id)}
     height={190}
     offline={!telemetry?.sensor_ok}
    />
   </div>

   <Panel title="DANH SÁCH CẢNH BÁO" tag="DEMO"><div className="filter-line"><label htmlFor="alarm-filter">Lọc trạng thái</label><select id="alarm-filter" value={alarmFilter} onChange={e=>setAlarmFilter(e.target.value)}>{['ALL','RAISED','ACKED','CLEARED','CRITICAL','WARNING'].map(v=><option key={v}>{v}</option>)}</select></div>
   {alarms.filter(a=>alarmFilter==='ALL'||a.status===alarmFilter||a.level===alarmFilter).map(a=>renderAlarm(a,true))}
   {alarms.every(a=>alarmFilter!=='ALL'&&a.status!==alarmFilter&&a.level!==alarmFilter)&&<p>Không có cảnh báo phù hợp.</p>}</Panel>
   {alarmId&&<Panel title={`CHI TIẾT CẢNH BÁO ${alarmId}`} tag="INCIDENT">{alarms.filter(a=>a.id===alarmId).map(a=>renderAlarm(a,true))}<Button kind="ghost" onClick={()=>setAlarmId(null)}>Đóng chi tiết</Button></Panel>}
   <div className="note">ACK chỉ xác nhận đã tiếp nhận, không xóa cảnh báo. CRITICAL không cho phép Mute. Thay đổi hiện tại chỉ lưu ở phiên Demo.</div></>;
  case 'control':{
   const isOp=session?.role==='Operator';
   const isSup=session?.role==='Supervisor';
   const isAdm=session?.role==='Admin';
   return <>
    <div className="page-hero">
     <div>
      <span className="eyebrow">VESSEL DEMO 01 / CONTROL CENTER</span>
      <h1>Control Center</h1>
      <p>Quản trị cấu hình thiết bị giám sát chuyển động • Tuân thủ Bảng 3.1 đề cương v2.0</p>
     </div>
     <Pill kind={isAdm?'normal':isSup?'caution':'warning'}>
      {isAdm?'ADMIN: TOÀN QUYỀN':isSup?'SUPERVISOR: CẤU HÌNH':'OPERATOR: CHỈ ĐỌC (VIEW ONLY)'}
     </Pill>
    </div>

    <div className="note" style={{marginBottom:18}}>
     <b>LƯU Ý NGƯỠNG CẢNH BÁO:</b> Các ngưỡng Roll Warning, Roll Trip và MAI là cấu hình mô phỏng nội bộ của nhóm dự án (Demo Profile thresholds, dựa trên dải an toàn 15°–25° theo đề cương), không phải tiêu chuẩn IMO chính thức được cấp phép an toàn hàng hải.
    </div>

    {isOp && (
     <div className="note warning" style={{marginBottom:18}}>
      <b>CHẾ ĐỘ CHỈ ĐỌC (OPERATOR):</b> Theo Bảng 3.1 đề cương v2.0, Operator chỉ được xem cấu hình hiện hành và nhật ký lệnh. Các nút gửi lệnh đã bị vô hiệu hóa. Để điều chỉnh cấu hình, vui lòng đăng nhập tài khoản <code>supervisor</code> hoặc <code>admin</code>.
     </div>
    )}

    <div className="metrics">
     <Metric label="PROFILE HIỆN HÀNH" value={profile} note="Cấu hình ngưỡng mô phỏng" tone="cyan"/>
     <Metric label="CONFIG VERSION" value={`v${configVersion}`} note="Phiên bản cấu hình" tone="green"/>
     <Metric label="NGƯỠNG ROLL (WARN / TRIP)" value={`${thresholds.roll_warning_deg}° / ${thresholds.roll_trip_deg}°`} note="Ngưỡng mô phỏng nhóm" tone="amber"/>
     <Metric label="NGƯỠNG MAI (MÔ PHỎNG)" value={String(thresholds.mai_alert_threshold)} note="Motion Anomaly Index" tone="red"/>
    </div>

    <div className="columns">
     <div>
      <Panel title="CẤU HÌNH THIẾT BỊ GIÁM SÁT" tag={`v${configVersion}`}>
       <dl className="kv">
        <dt>Device ID</dt><dd>vessel-demo-01</dd>
        <dt>Active Profile</dt><dd>{profile}</dd>
        <dt>Roll Warning Limit (Mô phỏng)</dt><dd>{thresholds.roll_warning_deg}°</dd>
        <dt>Roll Trip Limit (Mô phỏng)</dt><dd>{thresholds.roll_trip_deg}°</dd>
        <dt>MAI Alert Threshold (Mô phỏng)</dt><dd>{thresholds.mai_alert_threshold}</dd>
        <dt>Hiệu chuẩn điểm 0 (30s tĩnh)</dt><dd>{zeroCalibration ? `Roll ${zeroCalibration.roll_offset_deg>0?'+':''}${zeroCalibration.roll_offset_deg}°, Pitch ${zeroCalibration.pitch_offset_deg}°` : 'Mặc định (0.0°)'}</dd>
        <dt>Tốc độ ảo (set_timewarp)</dt><dd>×{timewarp}</dd>
        <dt>Mô hình quyết định</dt><dd>{activeModel === 'RF' ? 'Random Forest (Dữ liệu demo)' : 'Baseline B (Dữ liệu demo)'}</dd>
        <dt>Telemetry Mode</dt><dd>SIMULATION</dd>
       </dl>
       <div style={{marginTop:16}}>
        <span className="label">Chọn Profile Ngưỡng Mô Phỏng (Supervisor / Admin):</span>
        <div className="button-line">
         <Button kind={profile==='STANDARD'?'primary':'secondary'} disabled={!canOperate(session)} onClick={()=>sendCommand('set_profile',false,'STANDARD')}>STANDARD (15°/22°)</Button>
         <Button kind={profile==='SENSITIVE'?'primary':'secondary'} disabled={!canOperate(session)} onClick={()=>sendCommand('set_profile',false,'SENSITIVE')}>SENSITIVE (12°/18°)</Button>
         <Button kind={profile==='CONSERVATIVE'?'primary':'secondary'} disabled={!canOperate(session)} onClick={()=>sendCommand('set_profile',false,'CONSERVATIVE')}>CONSERVATIVE (18°/25°)</Button>
        </div>
       </div>
       <div style={{marginTop:14}}>
        <Button kind="ghost" disabled={!canOperate(session)||!hasPreviousProfile} onClick={()=>sendCommand('rollback')}>
         {hasPreviousProfile ? `Rollback về ${previousProfile}` : 'Rollback profile (Không có bản trước)'}
        </Button>
        <small className="muted" style={{display:'block',marginTop:5}}>Rollback khôi phục cấu hình hợp lệ trước đó và tăng số phiên bản config_version.</small>
       </div>
      </Panel>

      <Panel title="LỆNH THIẾT BỊ (MONITORING COMMANDS)" tag="SUPERVISOR / ADMIN">
       <p className="micro">Các lệnh kiểm tra và hiệu chuẩn thiết bị giám sát tại chỗ (Bảng 8.2).</p>
       <div className="button-line">
        <Button disabled={!canOperate(session)} onClick={()=>sendCommand('calibrate_zero')}>Calibrate Zero (30s tĩnh)</Button>
        <Button kind="secondary" disabled={!canOperate(session)} onClick={()=>sendCommand('request_snapshot')}>Request Snapshot (180s)</Button>
       </div>
       <p className="note" style={{marginTop:12}}>
        <b>Quy tắc an toàn:</b> Calibrate Zero kiểm tra phương sai trong 30s và chỉ chấp nhận khi tín hiệu ở trạng thái tĩnh (S0 - Biển êm, σ ≤ 1.0°). Nếu tàu đang lắc ở các kịch bản khác, lệnh sẽ bị <code>REJECTED: NOT_STATIC</code>. Lệnh Snapshot trích xuất chuỗi 180s và lưu trực tiếp vào Mock State.
       </p>
      </Panel>

      {latestSnapshot && (
       <Panel title="BẢN CHỤP DỮ LIỆU ĐỘNG HỌC (LATEST SNAPSHOT 180s)" tag="MOCK STATE ARTIFACT">
        <dl className="kv">
         <dt>Mã Snapshot</dt><dd>{latestSnapshot.snapshot_id}</dd>
         <dt>Thời điểm tạo</dt><dd>{time(latestSnapshot.timestamp)}</dd>
         <dt>Độ dài cửa sổ</dt><dd>{latestSnapshot.window_s}s ({latestSnapshot.sample_count} mẫu)</dd>
         <dt>Giới hạn Roll</dt><dd>{format(latestSnapshot.roll_min)} .. {format(latestSnapshot.roll_max)}</dd>
         <dt>RMS Roll</dt><dd>{format(latestSnapshot.rms_roll_deg)}</dd>
         <dt>MAI Snapshot</dt><dd>{latestSnapshot.mai}</dd>
         <dt>Người yêu cầu</dt><dd>{latestSnapshot.triggered_by}</dd>
         <dt>Trạng thái</dt><dd className="text-success" style={{fontWeight:600}}>ĐÃ LƯU TRONG MOCK STATE</dd>
        </dl>
       </Panel>
      )}

      <Panel title="TIỆN ÍCH KIỂM THỬ (TEST HARNESS / MOCK ONLY)" tag="UTILITY FOR QA / DEV">
       <p className="micro">Tiện ích giả lập sự cố kết nối phục vụ kiểm thử giao diện & vòng đời lệnh TIMEOUT (không phải lệnh cấu hình thiết bị trong Bảng 8.2 đề cương):</p>
       <div className="button-line">
        <Button kind="ghost" disabled={!canOperate(session)} onClick={()=>sendCommand('test_timeout')}>[TEST UTILITY] Thử nghiệm TIMEOUT (TTL 30s)</Button>
       </div>
      </Panel>
     </div>

     <div>
      <Panel title="QUẢN TRỊ MÔ PHỎNG & AI" tag="ADMIN ONLY">
       {!isAdmin(session) ? (
        <p className="muted" style={{padding:'12px 0'}}>Chỉ tài khoản Admin có quyền thay đổi tốc độ mô phỏng, mô hình AI và kịch bản biển động.</p>
       ) : (
        <>
         <div>
          <span className="label">Tốc độ giả lập (set_timewarp):</span>
          <div className="button-line">
           {[1, 5, 10].map(tw => (
            <Button key={tw} kind={timewarp === tw ? 'primary' : 'secondary'} onClick={()=>sendCommand('set_timewarp', true, String(tw))}>×{tw}</Button>
           ))}
          </div>
          <small className="muted" style={{display:'block',marginTop:4}}>Hệ số tăng tốc thời gian ảo: Thay đổi trực tiếp chu kỳ cập nhật dữ liệu và đồng hồ t_sim_s.</small>
         </div>

         <div style={{marginTop:16}}>
          <span className="label">Mô hình quyết định chính (set_model):</span>
          <div className="button-line">
           <Button kind={activeModel === 'RF' ? 'primary' : 'secondary'} onClick={()=>sendCommand('set_model', true, 'RF')}>Random Forest (Chính)</Button>
           <Button kind={activeModel === 'BASELINE_B' ? 'primary' : 'secondary'} onClick={()=>sendCommand('set_model', true, 'BASELINE_B')}>Baseline B (Shadow)</Button>
          </div>
          <small className="muted" style={{display:'block',marginTop:4}}>Chỉ chọn luồng nhãn chính trong dữ liệu demo. Không thực hiện suy luận TinyML/AI trên Frontend.</small>
         </div>

         <div style={{marginTop:16}}>
          <span className="label">Nguồn dữ liệu (set_mode):</span>
          <div className="button-line">
           <Button kind="primary" disabled title="Chế độ hiện tại">SIMULATION (Đang chạy)</Button>
           <Button kind="ghost" onClick={()=>sendCommand('set_mode', true, 'SENSOR')}>SENSOR (Thử MPU6050)</Button>
          </div>
          <small className="muted" style={{display:'block',marginTop:4}}>Thử nghiệm SENSOR trong Mock sẽ bị REJECTED vì chưa kết nối phần cứng.</small>
         </div>

         <div style={{marginTop:16}}>
          <span className="label">Kịch bản chuyển động (set_scenario):</span>
          <div className="scenario-grid">
           {SCENARIOS.map(s => (
            <Button key={s.id} kind={scenario === s.id ? 'primary' : 'secondary'} onClick={()=>sendCommand('set_scenario', true, s.id)}>
             {s.id} · {s.name}
            </Button>
           ))}
          </div>
         </div>
        </>
       )}
      </Panel>
     </div>
    </div>

    <Panel title="LỊCH SỬ THỰC THI LỆNH (COMMAND AUDIT LOG)" tag="SENT → DELIVERED → APPLIED / REJECTED / TIMEOUT">
     {commands.length ? (
      commands.map(c => (
       <div className="command-line" key={c.id}>
        <div>
         <div>
          <b>{c.name}</b>
          <span className="micro muted" style={{marginLeft:8}}>v{c.version}</span>
          {c.is_test_utility && <span className="pill caution" style={{marginLeft:8,fontSize:'0.6rem'}}>TEST UTILITY</span>}
         </div>
         <small className="muted">{c.id} • {time(c.issuedAt)} {c.issued_by ? `• Người gửi: ${c.issued_by}` : ''}</small>
         <small className="muted">{c.detail}</small>
        </div>
        <div>
         <Pill kind={c.status === 'APPLIED' ? 'normal' : c.status === 'REJECTED' || c.status === 'TIMEOUT' ? 'critical' : 'caution'}>
          {c.status}
         </Pill>
         {c.reason && (
          <span className="micro text-danger" style={{marginTop:4,display:'block',fontWeight:600}}>
           [{c.reason}]
          </span>
         )}
        </div>
       </div>
      ))
     ) : (
      <p className="muted">Chưa có lệnh nào được thực thi trong phiên làm việc này.</p>
     )}
    </Panel>
   </>;
  }
  case 'reports':{
   const v = selectedVoyage;
   return <>
    <div className="page-hero">
     <div>
      <span className="eyebrow">VESSEL DEMO 01 / VOYAGE INTELLIGENCE</span>
      <h1>Voyage Reports</h1>
      <p>Quản lý hành trình, kiểm toán thống kê chuyển động học và phân bố nhận dạng rủi ro • Dữ liệu mô phỏng TV4</p>
     </div>
     <Pill kind="normal">MOCK DATA • ĐỒNG BỘ T11</Pill>
    </div>

    {/* Voyage Selector Tabs */}
    <Panel title="DANH SÁCH CHUYẾN ĐI MÔ PHỎNG" tag="CHỌN CHUYẾN">
     <div className="button-line" style={{marginBottom:14}}>
      {MOCK_VOYAGES.map(voy=>(
       <Button
        key={voy.id}
        kind={selectedVoyageId===voy.id?'primary':'secondary'}
        onClick={()=>setSelectedVoyageId(voy.id)}
       >
        {selectedVoyageId===voy.id?`● ${voy.id}`:voy.id} ({voy.durationMinutes} min)
       </Button>
      ))}
     </div>
     <dl className="kv">
      <dt>Tên chuyến</dt><dd>{v.name}</dd>
      <dt>Tuyến đường</dt><dd>{v.route}</dd>
      <dt>Thời gian</dt><dd>{time(v.startTime)} – {time(v.endTime)} UTC ({v.durationMinutes} phút)</dd>
      <dt>Thiết bị / Nguồn</dt><dd>{v.deviceId} • {v.sourceMode}</dd>
      <dt>Mô hình / Config</dt><dd>{v.modelVersion} • v{v.configVersion}</dd>
     </dl>
    </Panel>

    {/* Kinematic Summary Metrics */}
    <div className="metrics">
     <Metric label="THỜI LƯỢNG" value={`${v.durationMinutes} phút`} note={`${v.sampleCount} mẫu`} tone="cyan"/>
     <Metric label="SỰ KIỆN CẢNH BÁO" value={String(v.alarms)} note={v.alarms>0?'Cần xem xét':'Bình thường'} tone={v.alarms>0?'amber':'green'}/>
     <Metric label="ROLL CỰC ĐẠI |°|" value={`${v.maxAbsRollDeg.toFixed(1)}°`} note={v.maxAbsRollDeg>15?'Vượt ngưỡng 15°':'An toàn'} tone={v.maxAbsRollDeg>15?'red':'amber'}/>
     <Metric label="RMS ROLL (T11)" value={`${v.rmsRollDeg.toFixed(2)}°`} note="Đo theo đề cương" tone="cyan"/>
    </div>

    <div className="metrics">
     <Metric label="P95 ABS ROLL" value={`${v.p95AbsRollDeg.toFixed(2)}°`} note="Phân vị 95% biên độ" tone="cyan"/>
     <Metric label="PITCH CỰC ĐẠI / RMS" value={`${v.maxAbsPitchDeg.toFixed(1)}° / ${v.rmsPitchDeg.toFixed(2)}°`} note="Lắc dọc thân tàu" tone="cyan"/>
     <Metric label="MAI CỰC ĐẠI" value={`${v.maiMax} / 100`} note="Motion Anomaly Index" tone={v.maiMax>70?'red':'amber'}/>
     <Metric label="MAI TRUNG BÌNH" value={`${v.maiAvg} / 100`} note={`Vượt ngưỡng: ${v.maiCautionMinutes} min`} tone="cyan"/>
    </div>

    {/* Interactive Kinematic Distribution & RF Breakdown Charts */}
    <div className="columns" style={{marginBottom:18}}>
     <div>
      <VoyageKinematicDistributionChart voyage={v} />
     </div>
     <div>
      <VoyageRfDistributionChart voyage={v} />
     </div>
    </div>

    <div className="columns">
     <div>
      {/* RF Distribution Panel */}
      <Panel title="PHÂN BỐ NHẬN DẠNG RANDOM FOREST" tag={`${v.agreementPercent}% ĐỒNG THUẬN BASELINE B`}>
       <p className="micro">Tỷ lệ phân bố các trạng thái động học trong chuyến đi:</p>
       <div style={{height:18,borderRadius:4,overflow:'hidden',display:'flex',marginBottom:14,border:'1px solid var(--border-color)'}}>
        <div style={{width:`${v.rfDistribution.normalPct}%`,background:'var(--accent-color)'}} title={`Normal: ${v.rfDistribution.normalPct}%`}/>
        <div style={{width:`${v.rfDistribution.highRollPct}%`,background:'var(--status-amber-text)'}} title={`High Roll: ${v.rfDistribution.highRollPct}%`}/>
        <div style={{width:`${v.rfDistribution.persistentOffsetPct}%`,background:'#EAB308'}} title={`Persistent Offset: ${v.rfDistribution.persistentOffsetPct}%`}/>
        <div style={{width:`${v.rfDistribution.amplitudeGrowthPct}%`,background:'var(--status-red-text)'}} title={`Amplitude Growth: ${v.rfDistribution.amplitudeGrowthPct}%`}/>
       </div>
       <dl className="kv">
        <dt><span className="dot cyan-bg"/>Normal (Bình thường)</dt><dd>{v.rfDistribution.normalPct}%</dd>
        <dt><span className="dot amber-bg"/>High Roll (Lắc ngang lớn)</dt><dd>{v.rfDistribution.highRollPct}%</dd>
        <dt><span className="dot amber-bg"/>Persistent Offset (Nghiêng lệch)</dt><dd>{v.rfDistribution.persistentOffsetPct}%</dd>
        <dt><span className="dot red-bg"/>Amplitude Growth (Cộng hưởng tăng)</dt><dd>{v.rfDistribution.amplitudeGrowthPct}%</dd>
        <dt>Độ đồng thuận với Baseline B</dt><dd className="text-success" style={{fontWeight:600}}>{v.agreementPercent}%</dd>
       </dl>
      </Panel>
     </div>

     <div>
      <Panel title="THAO TÁC HÀNH TRÌNH" tag="M4-05">
       <p className="micro">Xem chi tiết báo cáo kiểm toán số liệu hoặc mở công cụ phát lại đồng bộ chuỗi thời gian:</p>
       <div className="button-line" style={{flexDirection:'column',alignItems:'stretch'}}>
        <Button onClick={()=>goto('report-detail')}>Xem chi tiết báo cáo (T11 Audit) →</Button>
        <Button kind="secondary" onClick={()=>goto('replay')}>Mở Replay & Review chuỗi thời gian →</Button>
        <DownloadCSV rows={REPLAY_SAMPLES} allowed={canOperate(session)} voyageId={v.id}/>
       </div>
       <div className="note" style={{marginTop:16}}>
        <b>Đồng bộ T11:</b> Số liệu của <code>V-2026-001</code> được tính toán khớp chính xác với script <code>t11_recompute.py</code> từ tập mẫu <code>telemetry_demo.csv</code>.
       </div>
      </Panel>
     </div>
    </div>
   </>;
  }
  case 'report-detail':{
   const v = selectedVoyage;
   const tpCount = alarms.filter(a => a.review === 'TRUE').length;
   const fpCount = alarms.filter(a => a.review === 'FALSE').length;
   const uncertainCount = alarms.filter(a => a.review === 'UNCERTAIN').length;
   const reviewedTotal = tpCount + fpCount;
   const confidenceRate = reviewedTotal > 0 ? ((tpCount / reviewedTotal) * 100).toFixed(1) + '%' : 'Chưa đủ mẫu';

   return <>
    <div className="page-hero">
     <div>
      <div style={{marginBottom:8}}>
       <Button kind="ghost" onClick={()=>goto('reports')}>← Quay lại Voyage Reports</Button>
      </div>
      <span className="eyebrow">AUDIT DOSSIER / {v.id}</span>
      <h1>Report Details: {v.id}</h1>
      <p>{v.name} • {v.route}</p>
     </div>
     <Pill kind="normal">AUDIT VERIFIED • T11 COMPLIANT</Pill>
    </div>

    <Panel title="THÔNG TIN HÀNH TRÌNH KIỂM TOÁN" tag="METADATA">
     <dl className="kv">
      <dt>Mã chuyến (Voyage ID)</dt><dd>{v.id}</dd>
      <dt>Tuyến hành trình</dt><dd>{v.route}</dd>
      <dt>Khoảng thời gian UTC</dt><dd>{v.startTime} – {v.endTime} ({v.durationMinutes} phút)</dd>
      <dt>Thiết bị giám sát</dt><dd>{v.deviceId} (ESP32 Edge Unit)</dd>
      <dt>Mô hình AI trên thiết bị</dt><dd>{v.modelVersion}</dd>
      <dt>Phiên bản cấu hình</dt><dd>v{v.configVersion}</dd>
      <dt>Chế độ nguồn dữ liệu</dt><dd>{v.sourceMode} (Đồng bộ fixture)</dd>
     </dl>
    </Panel>

    {/* Interactive Voyage Analytics Charts */}
    <div className="columns" style={{marginBottom:18}}>
     <div>
      <VoyageKinematicDistributionChart voyage={v} />
     </div>
     <div>
      <VoyageRfDistributionChart voyage={v} />
     </div>
    </div>

    <div className="columns">
     <div>
      {/* Kinematic Statistics Audit */}
      <Panel title="KIỂM TOÁN ĐỘNG HỌC CHUYỂN ĐỘNG (T11 SPECIFICATION)" tag="RECOMPUTED EXACT">
       <dl className="kv">
        <dt>Tổng số mẫu telemetry (sample_count)</dt><dd>{v.sampleCount} mẫu (chu kỳ 5s)</dd>
        <dt>Roll cực đại (|max_abs_roll_deg|)</dt><dd className={v.maxAbsRollDeg>15?'text-danger':'text-info'} style={{fontWeight:600}}>{v.maxAbsRollDeg.toFixed(2)}°</dd>
        <dt>Độ lệch bình phương trung bình (rms_roll_deg)</dt><dd className="text-info" style={{fontWeight:600}}>{v.rmsRollDeg.toFixed(2)}° (7.083967° chuẩn)</dd>
        <dt>Phân vị 95% biên độ roll (p95_abs_roll_deg)</dt><dd>{v.p95AbsRollDeg.toFixed(2)}°</dd>
        <dt>Pitch cực đại (|max_abs_pitch_deg|)</dt><dd>{v.maxAbsPitchDeg.toFixed(2)}°</dd>
        <dt>RMS Pitch (rms_pitch_deg)</dt><dd>{v.rmsPitchDeg.toFixed(2)}°</dd>
       </dl>
       <div className="note success" style={{marginTop:14}}>
        <b>✓ ĐỐI CHỨNG T11:</b> Số liệu trên trùng khớp 100% với kết quả chạy kiểm tra tự động <code>tests/e2e/t11_recompute.py</code> trên fixture <code>tests/e2e/fixtures/telemetry_demo.csv</code> và <code>report_demo.json</code>.
       </div>
      </Panel>

      {/* MAI and Cargo Risk Evidence */}
      <Panel title="CHỈ SỐ BẤT THƯỜNG MAI & BẰNG CHỨNG RỦI RO HÀNG HÓA" tag="EVIDENCE">
       <dl className="kv">
        <dt>Chỉ số bất thường cực đại (MAI max)</dt><dd className={v.maiMax>70?'text-danger':'text-warning'} style={{fontWeight:600}}>{v.maiMax} / 100</dd>
        <dt>Chỉ số bất thường trung bình (MAI avg)</dt><dd>{v.maiAvg} / 100</dd>
        <dt>Thời lượng cảnh báo (MAI &gt; 70)</dt><dd>{v.maiCautionMinutes} phút</dd>
        <dt>Đánh giá trực ca: Đúng (True Positive - TP)</dt><dd className="text-success" style={{fontWeight:600}}>{tpCount} sự kiện</dd>
        <dt>Đánh giá trực ca: Sai (False Positive - FP)</dt><dd className="text-danger" style={{fontWeight:600}}>{fpCount} sự kiện</dd>
        <dt>Đánh giá trực ca: Chưa rõ (Uncertain)</dt><dd className="text-warning" style={{fontWeight:600}}>{uncertainCount} sự kiện</dd>
        <dt>Độ tin cậy cảnh báo đánh giá bởi trực ca</dt><dd className="text-success" style={{fontWeight:'bold'}}>{confidenceRate}</dd>
       </dl>
       <small className="muted" style={{display:'block',marginTop:8}}>
        Đánh giá sự kiện cảnh báo được thực hiện trực tiếp bởi trực ca trong giao diện Replay & Review và tự động lưu vào Mock State.
       </small>
      </Panel>
     </div>

     <div>
      {/* Alarm Log */}
      <Panel title="NHẬT KÝ CẢNH BÁO HÀNH TRÌNH" tag={`${alarms.length} SỰ KIỆN`}>
       {alarms.map(a => renderAlarm(a, true))}
      </Panel>

      {/* Export Cluster */}
      <Panel title="XUẤT BÁO CÁO & KÝ SỐ" tag="EXPORT CLUSTER">
       <p className="micro">Các tùy chọn kết xuất dữ liệu và báo cáo theo đề cương TV4:</p>
       <div className="button-line" style={{flexDirection:'column',alignItems:'stretch'}}>
        <DownloadCSV rows={REPLAY_SAMPLES} allowed={canOperate(session)} voyageId={v.id}/>
        <Button kind="secondary" onClick={()=>window.print()}>Xem trước / In báo cáo (HTML Print)</Button>
       </div>
       <div className="note" style={{marginTop:14}}>
        <b>TRẠNG THÁI PDF CHÍNH THỨC:</b><br/>
        <span className="text-warning" style={{fontWeight:600}}>Đang chờ Backend TV3 Report Service</span> kết nối cơ sở dữ liệu và cấp chứng chỉ ký số mật mã. Ở giai đoạn Mock Mode TV4, hệ thống hỗ trợ xuất trực tiếp CSV chuỗi thời gian 121 mẫu và in bản ghi HTML.
       </div>
      </Panel>
     </div>
    </div>
   </>;
  }
  case 'replay':{
   const currentPoint = REPLAY_SAMPLES[replayIndex] || REPLAY_SAMPLES[0];
   const v = selectedVoyage;

   return <>
    <div className="page-hero">
     <div>
      <span className="eyebrow">TIME-SERIES DIGITAL RECORDER / {v.id}</span>
      <h1>Replay & Review</h1>
      <p>Phát lại đồng bộ chuỗi thời gian chuyển động học và thẩm định cảnh báo trực ca (Bảng 3.1 đề cương v2.0)</p>
     </div>
     <Pill kind={playing?'normal':'caution'}>
      {playing ? `ĐANG PHÁT (×${speed})` : 'TẠM DỪNG'}
     </Pill>
    </div>

    {/* Top HUD Readout Bar */}
    <div className="metrics">
     <Metric label="MỐC THỜI GIAN" value={`T+${currentPoint.t_sim_s}s`} note={`Mẫu ${replayIndex + 1} / ${REPLAY_SAMPLES.length} (Tổng 600s)`} tone="cyan"/>
     <Metric label="GÓC LẮC NGANG (ROLL)" value={format(currentPoint.roll)} note="Dao động ngang" tone={Math.abs(currentPoint.roll)>12?'red':'cyan'}/>
     <Metric label="GÓC LẮC DỌC (PITCH)" value={format(currentPoint.pitch)} note="Dao động dọc" tone="amber"/>
     <Metric label="MAI / PHÂN LOẠI RF" value={`${currentPoint.mai} • ${currentPoint.class_rf}`} note={`Shadow: ${currentPoint.class_baseline_b}`} tone={currentPoint.mai>70?'red':'green'}/>
    </div>

    {/* 2D Vessel Visualizer Synchronized with Playhead */}
    <Panel title="TRỰC QUAN HÓA THÂN TÀU (REPLAY 2D DYNAMICS)" tag={`T+${currentPoint.t_sim_s}s`}>
     <ShipMotionVisualizer
      rollDeg={currentPoint.roll}
      pitchDeg={currentPoint.pitch}
      mai={currentPoint.mai}
      alarmLevel={currentPoint.alarm_level}
      scenario="S0"
      classRf={currentPoint.class_rf}
      sourceMode="SIMULATION"
      sensorOk={true}
      compact={false}
     />
    </Panel>

    {/* Waveform with needle & markers */}
    <Panel title={`ĐỒ THỊ CHUYỂN ĐỘNG THEO THỜI GIAN (${v.id})`} tag={`T+${currentPoint.t_sim_s}s`}>
     <ReplayChart
      samples={REPLAY_SAMPLES}
      currentIndex={replayIndex}
      onSeek={(idx)=>setReplayIndex(idx)}
     />
    </Panel>

    {/* Transport Deck & Time Scrubber */}
    <Panel title="BÀN ĐIỀU KHIỂN PHÁT LẠI (TRANSPORT DECK)" tag="ĐIỀU KHIỂN ĐỒNG BỘ">
     <div style={{marginBottom:12}}>
      <label htmlFor="replay-slider" className="micro" style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
       <span>KÉO THANH THỜI GIAN (TIME SCRUBBER)</span>
       <span className="text-success" style={{fontWeight:'bold'}}>T+{currentPoint.t_sim_s}s / 600s (Mẫu {replayIndex + 1}/121)</span>
      </label>
      <input
       id="replay-slider"
       type="range"
       min={0}
       max={REPLAY_SAMPLES.length - 1}
       value={replayIndex}
       onChange={(e)=>setReplayIndex(Number(e.target.value))}
      />
     </div>

     <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:12}}>
      <div className="button-line" style={{marginTop:0}}>
       <Button kind={playing?'secondary':'primary'} onClick={()=>setPlaying(p=>!p)}>
        {playing ? '❚❚ Tạm dừng' : '▶ Phát lại'}
       </Button>
       <Button kind="ghost" onClick={()=>setReplayIndex(idx => Math.max(0, idx - 2))}>-10s</Button>
       <Button kind="ghost" onClick={()=>setReplayIndex(idx => Math.min(REPLAY_SAMPLES.length - 1, idx + 2))}>+10s</Button>
       <Button kind="ghost" onClick={()=>setReplayIndex(0)}>Về đầu (0s)</Button>
      </div>

      <div style={{display:'flex',alignItems:'center',gap:8}}>
       <span className="micro muted">TỐC ĐỘ:</span>
       <div className="button-line" style={{marginTop:0}}>
        {[1, 5, 10, 20, 60].map(sp => (
         <Button
          key={sp}
          kind={speed === sp ? 'primary' : 'ghost'}
          onClick={()=>setSpeed(sp)}
          style={{minHeight:32,padding:'4px 8px'}}
         >
          ×{sp}
         </Button>
        ))}
       </div>
      </div>
     </div>
    </Panel>

    {/* Watchstander Event Review Section */}
    <Panel title="THẨM ĐỊNH CẢNH BÁO BỞI TRỰC CA (WATCHSTANDER REVIEW)" tag="BẢNG 3.1 ĐỀ CƯƠNG">
     <p className="micro">
      Trực ca đánh giá tính chuẩn xác của các cảnh báo trong chuyến đi (Đúng / Sai / Chưa rõ) và nhập lý do thẩm định. Thao tác lưu trực tiếp vào Mock State:
     </p>
     {alarms.map(a => {
      // Find trigger time in replay samples
      const triggerSample = REPLAY_SAMPLES.find(s => s.alarm_id === a.id);
      const triggerTime = triggerSample ? `T+${triggerSample.t_sim_s}s` : '—';

      return (
       <div className="review-line" key={a.id} style={{padding:'12px 0',borderBottom:'1px solid var(--border-subtle)'}}>
        <div style={{flex:1,minWidth:200}}>
         <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
          <b>{a.id}</b>
          <Pill kind={a.level}>{a.level}</Pill>
          <span className="micro text-success" style={{fontWeight:600}}>[Thời điểm: {triggerTime}]</span>
         </div>
         <div className="micro muted">{a.title}</div>
         {triggerSample && (
          <button
           type="button"
           style={{background:'none',border:'none',color:'var(--accent-color)',cursor:'pointer',fontSize:'0.7rem',padding:0,marginTop:4,textDecoration:'underline'}}
           onClick={()=>setReplayIndex(triggerSample.seq)}
          >
           → Nhảy tới mốc {triggerTime}
          </button>
         )}
        </div>

        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-end',gap:6}}>
         <div className="button-line" style={{marginTop:0}}>
          <Button
           kind={a.review === 'TRUE' ? 'primary' : 'ghost'}
           onClick={()=>reviewAlarm(a.id, 'TRUE')}
           style={{minHeight:32,padding:'4px 10px'}}
          >
           ✓ ĐÚNG (TP)
          </Button>
          <Button
           kind={a.review === 'FALSE' ? 'danger' : 'ghost'}
           onClick={()=>reviewAlarm(a.id, 'FALSE')}
           style={{minHeight:32,padding:'4px 10px'}}
          >
           ✗ SAI (FP)
          </Button>
          <Button
           kind={a.review === 'UNCERTAIN' ? 'secondary' : 'ghost'}
           onClick={()=>reviewAlarm(a.id, 'UNCERTAIN')}
           style={{minHeight:32,padding:'4px 10px'}}
          >
           ? CHƯA RÕ
          </Button>
         </div>
         <span className={`micro ${a.review==='TRUE'?'text-success':a.review==='FALSE'?'text-danger':a.review==='UNCERTAIN'?'text-warning':'text-muted'}`} style={{fontWeight:600}}>
          Trạng thái thẩm định: {a.review ? `${a.review}` : 'Chưa thẩm định'}
         </span>
        </div>
       </div>
      );
     })}
    </Panel>
   </>;
  }
  case 'health':{
   const isOffline = scenario === 'OFFLINE';
   const isSensorFault = scenario === 'SENSOR_FAULT';
   return <>
    <div className="page-hero">
     <div>
      <span className="eyebrow">VESSEL DEMO 01 / HARDWARE DIAGNOSTICS</span>
      <h1>Device Health</h1>
      <p>Chẩn đoán vi điều khiển ESP32, cảm biến IMU MPU6050, bus I2C và hàng đợi dữ liệu • Tuân thủ hợp đồng health.json</p>
     </div>
     <Pill kind={health.healthStatus === 'HEALTHY' ? 'normal' : health.healthStatus === 'DEGRADED' ? 'caution' : 'critical'}>
      {health.healthStatus === 'HEALTHY' ? 'HEALTH: 100% EXCELLENT' : health.healthStatus === 'DEGRADED' ? 'HEALTH: 45% SENSOR FAULT' : 'HEALTH: 15% OFFLINE'}
     </Pill>
    </div>

    {/* Callout banners */}
    {isOffline ? (
     <div className="note danger" style={{marginBottom:18}}>
      <b>MẤT KẾT NỐI VỚI THIẾT BỊ (OFFLINE):</b> Thiết bị giám sát mất kết nối MQTT (&gt;30s). Dữ liệu cảm biến không khả dụng. Theo đề cương, hệ thống không tự tạo dữ liệu mới để hiển thị như dữ liệu thật. Dữ liệu đang được tự động lưu vào bộ đệm Flash ngoại tuyến trên ESP32 và sẽ đồng bộ bù khi tái kết nối.
     </div>
    ) : isSensorFault ? (
     <div className="note warning" style={{marginBottom:18}}>
      <b>LỖI GIAO TIẾP CẢM BIẾN (SENSOR FAULT):</b> Phát hiện 3 lỗi I2C NACK với cảm biến MPU6050. Tín hiệu đo không khả dụng, hệ thống không suy diễn trạng thái NORMAL.
     </div>
    ) : (
     <div className="note success" style={{marginBottom:18}}>
      <b>THIẾT BỊ HOẠT ĐỘNG TỐT (100% HEALTH):</b> ESP32 kết nối ổn định qua MQTT QoS 0/1. Cảm biến MPU6050 hoạt động chuẩn xác với chu kỳ đo 5.0s.
     </div>
    )}

    {/* 4 Primary Diagnostic Metrics */}
    <div className="metrics">
     <Metric
      label="ĐIỂM SỨC KHỎE (FR17)"
      value={`${health.healthScore} / 100`}
      note={health.healthStatus}
      tone={health.healthScore >= 80 ? 'green' : health.healthScore >= 40 ? 'amber' : 'red'}
     />
     <Metric
      label="TRẠNG THÁI CẢM BIẾN"
      value={health.sensor}
      note={health.sensor === 'OK' ? 'MPU6050 kết nối tốt' : health.sensor === 'FAULT' ? 'Lỗi bus I2C' : 'Chưa rõ / Offline'}
      tone={health.sensor === 'OK' ? 'green' : health.sensor === 'FAULT' ? 'amber' : 'red'}
     />
     <Metric
      label="LỖI BUS I2C"
      value={String(health.i2cErrors)}
      note={health.i2cErrors > 0 ? 'NACK timeout phát hiện' : '0 lỗi bus (Chuẩn)'}
      tone={health.i2cErrors > 0 ? 'red' : 'green'}
     />
     <Metric
      label="FREE HEAP (ESP32)"
      value={`${health.freeHeapKb} KB`}
      note={`Tối thiểu: ${health.minFreeHeapKb} KB`}
      tone={health.freeHeapKb < 80 ? 'amber' : 'cyan'}
     />
    </div>

    {/* Secondary Metrics */}
    <div className="metrics">
     <Metric
      label="WIFI RSSI"
      value={health.rssiDbm !== null ? `${health.rssiDbm} dBm` : '—'}
      note={health.rssiDbm !== null ? 'Cường độ thu phát tốt' : 'Mất kết nối'}
      tone={health.rssiDbm !== null ? 'cyan' : 'red'}
     />
     <Metric
      label="UPTIME THIẾT BỊ"
      value={`${health.uptimeMinutes} phút`}
      note={`${Math.floor(health.uptimeMinutes/60)} giờ ${health.uptimeMinutes%60} phút`}
      tone="cyan"
     />
     <Metric
      label="BỘ ĐỆM NGOẠI TUYẾN"
      value={`${health.bufferUsed} / ${health.bufferCapacity}`}
      note={`Đang lưu: ${((health.bufferUsed / health.bufferCapacity) * 100).toFixed(1)}%`}
      tone={health.bufferUsed > 0 ? 'amber' : 'green'}
     />
     <Metric
      label="ĐỘ TRỄ HÀNG ĐỢI"
      value={`${health.queueLatencyMs} ms`}
      note={health.bufferStatus === 'BUFFERING' ? 'Đang lưu bù Flash' : 'Đồng bộ trực tiếp'}
      tone={health.queueLatencyMs > 100 ? 'amber' : 'green'}
     />
    </div>

    <div className="columns">
     <div>
      {/* Hardware & Bus Panel */}
      <Panel title="CHẨN ĐOÁN PHẦN CỨNG & BUS TRUYỀN THÔNG" tag="ESP32 • MPU6050">
       <dl className="kv">
        <dt>Mã thiết bị (Device ID)</dt><dd>vessel-demo-01</dd>
        <dt>Boot ID / Phiên bản firmware</dt><dd>mock-boot-01 (v1.2.0-esp32)</dd>
        <dt>Tần số xung nhịp I2C</dt><dd>400 kHz (Fast Mode)</dd>
        <dt>Tình trạng bus I2C</dt><dd className={health.i2cErrors>0?'text-danger':'text-success'} style={{fontWeight:600}}>{health.lastI2cError || 'Bình thường (0 lỗi NACK)'}</dd>
        <dt>Bộ nhớ SRAM khả dụng (Free Heap)</dt><dd>{health.freeHeapKb} KB (Phân mảnh {health.heapFragmentationPct}%)</dd>
        <dt>Bộ nhớ Heap tối thiểu từng ghi nhận</dt><dd>{health.minFreeHeapKb} KB (An toàn &gt; 64 KB)</dd>
        <dt>Thời gian thực thi Edge TinyML</dt><dd>{health.inferenceMs} ms / mẫu</dd>
       </dl>
      </Panel>

      {/* Heel Zero Calibration (FR18) */}
      <Panel title="HIỆU CHUẨN ĐIỂM 0 (HEEL ZERO CALIBRATION - FR18)" tag="FR18 SPEC">
       <dl className="kv">
        <dt>Trạng thái hiệu chuẩn</dt><dd className={zeroCalibration?'text-success':'text-muted'} style={{fontWeight:600}}>{zeroCalibration ? 'ĐÃ HIỆU CHUẨN (30S TĨNH)' : 'MẶC ĐỊNH NHÀ MÁY (0.0°)'}</dd>
        <dt>Độ lệch Roll hiện hành (offset)</dt><dd className="text-info" style={{fontWeight:600}}>{zeroCalibration ? `${zeroCalibration.roll_offset_deg>0?'+':''}${zeroCalibration.roll_offset_deg}°` : '0.00°'}</dd>
        <dt>Độ lệch Pitch hiện hành (offset)</dt><dd className="text-warning" style={{fontWeight:600}}>{zeroCalibration ? `${zeroCalibration.pitch_offset_deg}°` : '0.00°'}</dd>
        <dt>Độ lệch chuẩn tín hiệu 30s đo</dt><dd className={zeroCalibration?'text-success':'text-muted'} style={{fontWeight:600}}>{zeroCalibration ? `σ = ${zeroCalibration.std_dev_roll}° (Đạt chuẩn ≤ 1.0°)` : 'Chưa lấy mẫu'}</dd>
        <dt>Thời điểm hiệu chuẩn gần nhất</dt><dd>{zeroCalibration ? time(zeroCalibration.calibrated_at) : '—'}</dd>
       </dl>
       <div style={{marginTop:14}}>
        <Button kind="ghost" disabled={!canOperate(session)} onClick={()=>goto('control')}>Đến Control Center để hiệu chuẩn →</Button>
       </div>
      </Panel>
     </div>

     <div>
      {/* Offline Buffer Panel */}
      <Panel title="BỘ ĐỆM NGOẠI TUYẾN & ĐỒNG BỘ BÙ (FR19)" tag="FLASH RING BUFFER">
       <p className="micro">Cơ chế lưu trữ Flash ring buffer trên ESP32 đảm bảo không mất mát dữ liệu khi mất kết nối mạng biển:</p>
       <dl className="kv">
        <dt>Dung lượng bộ đệm Flash tối đa</dt><dd>{health.bufferCapacity} mẫu (~83 phút khi mất mạng)</dd>
        <dt>Số mẫu đang lưu trong đệm</dt><dd className={health.bufferUsed>0?'text-warning':'text-success'} style={{fontWeight:600}}>{health.bufferUsed} / {health.bufferCapacity} mẫu</dd>
        <dt>Trạng thái bộ đệm</dt><dd className={health.bufferStatus==='BUFFERING'?'text-warning':'text-success'} style={{fontWeight:600}}>{health.bufferStatus === 'BUFFERING' ? 'ĐANG LƯU BÙ FLASH' : 'ĐỒNG BỘ TRỰC TIẾP'}</dd>
        <dt>Độ trễ hàng đợi truyền phát (RTT)</dt><dd>{health.queueLatencyMs} ms</dd>
        <dt>Bản tin telemetry gần nhất</dt><dd className={isOffline?'text-danger':'text-success'} style={{fontWeight:600}}>{health.lastPacketUtc} ({health.packetGapS}s gap)</dd>
        <dt>Số lần kết nối lại MQTT (Reconnects)</dt><dd>{health.mqttReconnects} lần</dd>
        <dt>Chống trùng lặp (Deduplication)</dt><dd className="text-success" style={{fontWeight:600}}>Bảo vệ qua device_id + boot_id + seq</dd>
       </dl>
       <div className="note" style={{marginTop:14}}>
        <b>NGUYÊN TẮC AN TOÀN KHI OFFLINE:</b> Khi mất kết nối MQTT, thiết bị vẫn duy trì cảnh báo cục bộ độc lập qua còi buzzer và đèn LED trên bo mạch phần cứng, đồng thời lưu trữ chuỗi thời gian vào Flash để tự động đồng bộ bù khi mạng phục hồi.
       </div>
      </Panel>
     </div>
    </div>
   </>;
  }
  case 'model':{
   const isOp = session?.role === 'Operator';
   if(isOp){
    return <>
     <div className="page-hero">
      <div>
       <span className="eyebrow">ACCESS DENIED / TABLE 3.1</span>
       <h1>Model Monitor</h1>
       <p>Theo dõi mô hình học máy Random Forest và đối chiếu Baseline B</p>
      </div>
      <Pill kind="warning">OPERATOR: KHÔNG CÓ QUYỀN TRUY CẬP</Pill>
     </div>
     <div className="note warning" style={{padding:20}}>
      <h3>QUYỀN TRUY CẬP BỊ TỪ CHỐI (BẢNG 3.1 ĐỀ CƯƠNG)</h3>
      <p style={{marginTop:8}}>
       Theo quy định phân quyền tại Bảng 3.1 đề cương dự án Smart Vessel Motion Guard v2.0, vai trò <b>Operator</b> không có quyền truy cập màn hình Model Monitor. Tính năng này chỉ dành riêng cho <b>Supervisor</b> và Quản trị viên (<b>Admin</b>).
      </p>
      <div style={{marginTop:16}}>
       <Button kind="primary" onClick={()=>goto('overview')}>Quay lại Trang Chủ (Overview) →</Button>
      </div>
     </div>
    </>;
   }

   const isRf = modelInfo.activeModelId === 'RF';
   const currentPredPrimary = telemetry?.sensor_ok ? (isRf ? telemetry.class_rf : telemetry.class_baseline_b) : 'N/A';
   const currentPredShadow = telemetry?.sensor_ok ? (isRf ? telemetry.class_baseline_b : telemetry.class_rf) : 'N/A';
   const agree = telemetry?.sensor_ok ? (telemetry.class_rf === telemetry.class_baseline_b) : null;

   return <>
    <div className="page-hero">
     <div>
      <span className="eyebrow">EDGE AI & MARITIME INFERENCE / MODEL MONITOR</span>
      <h1>Model Monitor</h1>
      <p>Theo dõi chất lượng mô hình học máy Random Forest & đối chiếu Baseline B shadow (FR04/FR20) • Không suy luận AI trên Frontend</p>
     </div>
     <Pill kind="normal">MOCK DATA • ĐỒNG THUẬN {modelInfo.agreementPercent}%</Pill>
    </div>

    {/* 4 Summary Metrics */}
    <div className="metrics">
     <Metric
      label="MÔ HÌNH CHÍNH (ACTIVE)"
      value={modelInfo.activeModelId === 'RF' ? 'Random Forest' : 'Baseline B'}
      note={modelInfo.version}
      tone="cyan"
     />
     <Metric
      label="DỰ ĐOÁN HIỆN TẠI (CHÍNH)"
      value={currentPredPrimary}
      note={telemetry?.sensor_ok ? 'Từ mẫu telemetry hiện hành' : 'Cảm biến lỗi/Offline'}
      tone={currentPredPrimary === 'NORMAL' ? 'green' : currentPredPrimary === 'HIGH_ROLL' || currentPredPrimary === 'AMPLITUDE_GROWTH' ? 'red' : 'amber'}
     />
     <Metric
      label="ĐỘ ĐỒNG THUẬN CHUNG"
      value={`${modelInfo.agreementPercent}%`}
      note="Kiểm toán trên V-2026-001"
      tone="green"
     />
     <Metric
      label="POPULATION STABILITY (PSI)"
      value={String(modelInfo.psi)}
      note="Độ ổn định phân phối (Stable)"
      tone="green"
     />
    </div>

    {/* Interactive Model Concordance Timeline */}
    <div style={{marginBottom:18}}>
     <ModelConcordanceChart scenario={scenario} height={210} />
    </div>

    <div className="columns">
     <div>
      {/* Realtime Prediction Comparison */}
      <Panel title="SO SÁNH DỰ ĐOÁN MẪU HIỆN HÀNH (ACTIVE VS SHADOW)" tag="CURRENT DEMO SAMPLE">
       <dl className="kv">
        <dt>Mô hình quyết định chính (Active)</dt><dd className="text-info" style={{fontWeight:600}}>{modelInfo.active}</dd>
        <dt>Dự đoán mô hình chính</dt><dd className={currentPredPrimary==='NORMAL'?'text-success':'text-warning'} style={{fontWeight:'bold'}}>{currentPredPrimary}</dd>
        <dt>Mô hình bóng (Shadow Mode)</dt><dd className="text-warning" style={{fontWeight:600}}>{modelInfo.baseline}</dd>
        <dt>Dự đoán mô hình bóng</dt><dd className={currentPredShadow==='NORMAL'?'text-success':'text-warning'} style={{fontWeight:600}}>{currentPredShadow}</dd>
        <dt>Trạng thái so sánh (Concordance)</dt>
        <dd className={agree===null?'text-muted':agree?'text-success':'text-warning'} style={{fontWeight:'bold'}}>
         {agree === null ? 'N/A (CẢM BIẾN LỖI/OFFLINE)' : agree ? '✓ ĐỒNG THUẬN (AGREE)' : '⚠ BẤT ĐỒNG (DISAGREE)'}
        </dd>
       </dl>
       {scenario === 'S0b' && !agree && (
        <div className="note warning" style={{marginTop:14}}>
         <b>PHÁT HIỆN BẤT ĐỒNG CÓ CHỦ ĐÍCH (KỊCH BẢN S0b):</b> Baseline B dựa trên ngưỡng góc tức thời nên phát nhãn <code>HIGH_ROLL</code> khi có gió giật; trong khi Random Forest học đặc trưng chuỗi thời gian của quá trình tự hồi phục góc nghiêng nên nhận diện chuẩn xác nhãn <code>NORMAL</code>.
        </div>
       )}
      </Panel>

      {/* Model Registry Specs */}
      <Panel title="THÔNG TIN ĐẶC TẢ MÔ HÌNH (MODEL REGISTRY - FR04)" tag="TINYML SPECIFICATION">
       <dl className="kv">
        <dt>Tên và phiên bản mô hình</dt><dd>{modelInfo.version}</dd>
        <dt>Kiến trúc giải thuật</dt><dd>{modelInfo.algorithm}</dd>
        <dt>Thời gian suy luận trên ESP32</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.inferenceMs} ms / mẫu</dd>
        <dt>Chiếm dụng bộ nhớ Flash</dt><dd>{modelInfo.flashKb} KB (trong phân vùng 4MB)</dd>
        <dt>Chiếm dụng bộ nhớ RAM</dt><dd>{modelInfo.ramKb} KB (trong 320KB SRAM)</dd>
        <dt>Số đặc trưng đầu vào (Input Features)</dt><dd>{modelInfo.featuresCount} đặc trưng động học</dd>
        <dt>Vectơ đặc trưng</dt><dd style={{fontSize:'0.65rem'}}>{modelInfo.features.join(', ')}</dd>
       </dl>
      </Panel>
     </div>

     <div>
      {/* Concordance Breakdown */}
      <Panel title="TỶ LỆ ĐỒNG THUẬN THEO LỚP ĐỘNG HỌC (FR20)" tag={`${modelInfo.agreementPercent}% TỔNG THỂ`}>
       <p className="micro">Phân tích mức độ đồng thuận giữa Random Forest và Baseline B theo từng trạng thái biển:</p>
       <dl className="kv">
        <dt>Lớp NORMAL (Biển êm / S0)</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.concordanceBreakdown.normal}%</dd>
        <dt>Lớp HIGH_ROLL (Lắc ngang lớn / S1)</dt><dd>{modelInfo.concordanceBreakdown.highRoll}%</dd>
        <dt>Lớp PERSISTENT_OFFSET (Nghiêng lệch / S2)</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.concordanceBreakdown.persistentOffset}%</dd>
        <dt>Lớp AMPLITUDE_GROWTH (Cộng hưởng tăng / S3)</dt><dd>{modelInfo.concordanceBreakdown.amplitudeGrowth}%</dd>
       </dl>
       <small className="muted" style={{display:'block',marginTop:10}}>
        Số liệu được kiểm toán trên chuỗi thời gian 121 mẫu hành trình V-2026-001 (chuẩn T11/T15).
       </small>
      </Panel>

      {/* Data Drift & PSI (FR21) */}
      <Panel title="THEO DÕI ĐỘ LỆCH PHÂN PHỐI (DATA DRIFT / PSI - FR21)" tag="POPULATION STABILITY INDEX">
       <dl className="kv">
        <dt>Chỉ số PSI hiện tại (Population Stability Index)</dt><dd className="text-success" style={{fontWeight:'bold'}}>{modelInfo.psi}</dd>
        <dt>Đánh giá độ ổn định phân phối</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.psiStatus}</dd>
        <dt>Mô hình Isolation Forest (Phát hiện bất thường)</dt><dd className="text-warning" style={{fontWeight:600}}>Chờ kết nối Backend TV3</dd>
        <dt>Phân tích phân phối tần suất FFT</dt><dd>Chờ dữ liệu TV2 / TV3</dd>
       </dl>
       <div className="note" style={{marginTop:14}}>
        <b>LƯU Ý PHẠM VI HỆ THỐNG:</b> Chỉ số PSI và thuật toán Isolation Forest được tính toán định kỳ tại máy chủ Backend TV3 từ cơ sở dữ liệu lịch sử. Giao diện Frontend tuân thủ nghiêm ngặt nguyên tắc <b>không tự huấn luyện và không chạy suy luận TinyML trên trình duyệt</b>.
       </div>
      </Panel>
     </div>
    </div>
   </>;
  }
  case 'more':return <><header className="page-heading"><h1>More</h1><p>Các chức năng thuộc đề cương và tài khoản demo.</p></header>
   <Panel title="GIAO DIỆN HIỂN THỊ (THEME)" tag={theme==='light'?'LIGHT MARITIME':'DARK MARITIME'}>
    <p className="micro">Tùy chọn phong cách màu sắc giao diện hệ thống:</p>
    <div className="button-line">
     <Button kind={theme==='light'?'primary':'secondary'} onClick={()=>setTheme('light')}>☀ Light Maritime (Mặc định)</Button>
     <Button kind={theme==='dark'?'primary':'secondary'} onClick={()=>setTheme('dark')}>🌙 Dark Maritime (Giao diện cũ)</Button>
    </div>
   </Panel>
   <Panel title="CÔNG CỤ GIÁM SÁT"><div className="more-list">{NAV.filter(n=>['control','replay','health','model'].includes(n.key)).map(n=><button type="button" key={n.key} onClick={()=>goto(n.key)}>{n.label}<span>→</span></button>)}</div></Panel><Panel title="TÀI KHOẢN"><dl className="kv"><dt>Username</dt><dd>{session?.username}</dd><dt>Role</dt><dd>{session?.role}</dd><dt>Mode</dt><dd>DEMO AUTH</dd></dl><Button kind="danger" onClick={logout}>Đăng xuất</Button></Panel></>;
  }
 };
  if (!session) {
    return (
      <div className="auth-layout">
        <div className="auth-brand">
          <div className="brand-mark">≋</div>
          <span className="eyebrow">IOT • EDGE AI • MARITIME SAFETY</span>
          <h1>Smart Vessel<br/>Motion Guard</h1>
          <p>Hệ thống giám sát động học chuyển động tàu thời gian thực và phát hiện bất thường TinyML trên ESP32.</p>
          <div className="auth-sec-notice" style={{marginTop: 18, maxWidth: 460}}>
            <span style={{fontSize: '1rem'}}>🔒</span>
            <span>RSA-4096 BRIDGE HARDWARE KEY ENCRYPTED • M4 DEMO</span>
          </div>
          <span className="stamp">M4 • LIGHT MARITIME CONSOLE • TIÊU CHUẨN AN TOÀN HÀNG HẢI</span>
        </div>

        {authView === 'login' && (
          <form className="auth-card" onSubmit={submitLogin}>
            <div className="reticle-tl"></div>
            <div className="reticle-tr"></div>
            <div className="reticle-bl"></div>
            <div className="reticle-br"></div>

            <div className="auth-badge-row">
              <span className="auth-badge">ACCESS CONTROL LEVEL 1</span>
              <span className="auth-sysid">SYS_ID: 994-IMU-BRG</span>
            </div>

            <h2>Đăng nhập Buồng lái</h2>
            <p className="auth-sub">Nhập thông tin định danh sĩ quan trực ca hoặc giám sát viên:</p>

            <label>
              Mã Sĩ quan / Tên đăng nhập (Officer ID)
              <input
                value={loginName}
                onChange={e => { setLoginName(e.target.value); setLoginError(''); }}
                autoComplete="username"
                placeholder="e.g. operator / supervisor / admin"
                required
              />
            </label>

            <div className="auth-label-row">
              <span>Mật mã buồng lái / Passcode</span>
              <button
                type="button"
                className="auth-key-recovery-btn"
                onClick={() => { setAuthView('forgot'); setLoginError(''); }}
                title="Khôi phục mật mã truy cập"
              >
                KEY_RECOVERY
              </button>
            </div>
            <div className="password-row">
              <input
                type={showPassword ? 'text' : 'password'}
                value={loginPass}
                onChange={e => { setLoginPass(e.target.value); setLoginError(''); }}
                autoComplete="current-password"
                placeholder="Nhập mật mã truy cập"
                required
              />
              <button type="button" onClick={() => setShowPassword(v => !v)}>
                {showPassword ? 'Ẩn' : 'Hiện'}
              </button>
            </div>

            <div className="auth-sec-notice">
              <span>🛡️</span>
              <span>TOKEN: HARDWARE AUTH (RSA-4096 EDGE KEY)</span>
            </div>

            {loginError && <div className="error" role="alert">{loginError}</div>}

            <button className="btn primary full" type="submit">
              ĐĂNG NHẬP HỆ THỐNG →
            </button>

            <div className="auth-footer-nav">
              <button
                type="button"
                className="auth-nav-link"
                onClick={() => { setAuthView('register'); setLoginError(''); }}
              >
                Đăng ký tài khoản Sĩ quan trực ca (Operator) →
              </button>
            </div>
          </form>
        )}

        {authView === 'register' && (
          <form className="auth-card" onSubmit={submitRegister}>
            <div className="reticle-tl"></div>
            <div className="reticle-tr"></div>
            <div className="reticle-bl"></div>
            <div className="reticle-br"></div>

            <div className="auth-badge-row">
              <span className="auth-badge">OFFICER ONBOARDING</span>
              <span className="auth-sysid">RBAC: TABLE 3.1</span>
            </div>

            <h2>Đăng ký Sĩ quan</h2>
            <p className="auth-sub">Tạo tài khoản trực ca giám sát động học tàu mới:</p>

            <label>
              Họ và tên sĩ quan (Full Name)
              <input
                value={regFullName}
                onChange={e => { setRegFullName(e.target.value); setRegError(''); }}
                placeholder="e.g. Sĩ quan Nguyễn Văn A"
                required
              />
            </label>

            <label>
              Tên đăng nhập / Mã sĩ quan (Officer ID)
              <input
                value={regUsername}
                onChange={e => { setRegUsername(e.target.value); setRegError(''); }}
                autoComplete="username"
                placeholder="e.g. officer_bridge01"
                required
              />
            </label>

            <label>
              Mật khẩu truy cập (Passcode)
              <div className="password-row">
                <input
                  type={regShowPass ? 'text' : 'password'}
                  value={regPass}
                  onChange={e => { setRegPass(e.target.value); setRegError(''); }}
                  autoComplete="new-password"
                  placeholder="Tối thiểu 6 ký tự"
                  required
                />
                <button type="button" onClick={() => setRegShowPass(v => !v)}>
                  {regShowPass ? 'Ẩn' : 'Hiện'}
                </button>
              </div>
            </label>

            <label>
              Xác nhận mật khẩu (Confirm Passcode)
              <input
                type={regShowPass ? 'text' : 'password'}
                value={regConfirmPass}
                onChange={e => { setRegConfirmPass(e.target.value); setRegError(''); }}
                autoComplete="new-password"
                placeholder="Nhập lại mật khẩu"
                required
              />
            </label>

            <div className="auth-role-fixed">
              <strong>VAI TRÒ HỆ THỐNG: OPERATOR (SĨ QUAN TRỰC CA)</strong>
              <p>
                <b>Quy chuẩn phân quyền (Bảng 3.1 Đề cương v2.0):</b> Người dùng tự đăng ký chỉ có quyền Sĩ quan trực ca (Operator / View-Only). Quyền Supervisor (Giám sát bờ) và Admin (Quản trị viên) phải do Quản trị hệ thống phê duyệt và cấp phát mã ủy quyền riêng.
              </p>
            </div>

            {regError && <div className="error" role="alert">{regError}</div>}

            {regPendingNotice && (
              <div className="auth-pending-banner" role="status">
                <b>THÔNG BÁO DỊCH VỤ XÁC THỰC:</b>
                <p style={{margin: '6px 0 10px'}}>{regPendingNotice}</p>
                <button
                  type="button"
                  className="btn primary"
                  style={{padding: '6px 12px', fontSize: '0.78rem'}}
                  onClick={() => { setAuthView('login'); setRegPendingNotice(''); }}
                >
                  Chuyển sang Đăng nhập ngay →
                </button>
              </div>
            )}

            {!regPendingNotice && (
              <button className="btn primary full" type="submit">
                XÁC NHẬN ĐĂNG KÝ →
              </button>
            )}

            <div className="auth-footer-nav">
              <button
                type="button"
                className="auth-nav-link"
                onClick={() => { setAuthView('login'); setRegError(''); setRegPendingNotice(''); }}
              >
                ← Quay lại Đăng nhập
              </button>
            </div>
          </form>
        )}

        {authView === 'forgot' && (
          <form className="auth-card" onSubmit={submitForgotPassword}>
            <div className="reticle-tl"></div>
            <div className="reticle-tr"></div>
            <div className="reticle-bl"></div>
            <div className="reticle-br"></div>

            <div className="auth-badge-row">
              <span className="auth-badge">KEY RECOVERY PROTOCOL</span>
              <span className="auth-sysid">SYS_ID: 994-IMU-BRG</span>
            </div>

            <h2>Khôi phục Mật mã</h2>
            <p className="auth-sub">Yêu cầu cấp lại mã truy cập buồng lái hoặc đặt lại mật mã:</p>

            <label>
              Mã Sĩ quan hoặc Email buồng lái (Officer ID / Email)
              <input
                value={forgotIdentifier}
                onChange={e => { setForgotIdentifier(e.target.value); setForgotError(''); }}
                placeholder="e.g. operator hoặc officer.jensen@vessel01.bridge"
                required
              />
            </label>

            {forgotError && <div className="error" role="alert">{forgotError}</div>}

            {forgotPendingNotice && (
              <div className="auth-pending-banner" role="status">
                <b>TRẠNG THÁI HẠ TẦNG XÁC THỰC:</b>
                <p style={{margin: '6px 0 10px'}}>{forgotPendingNotice}</p>
                <button
                  type="button"
                  className="btn primary"
                  style={{padding: '6px 12px', fontSize: '0.78rem'}}
                  onClick={() => { setAuthView('login'); setForgotPendingNotice(''); }}
                >
                  Quay lại màn hình Đăng nhập
                </button>
              </div>
            )}

            {!forgotPendingNotice && (
              <button className="btn primary full" type="submit">
                GỬI YÊU CẦU ĐẶT LẠI MẬT MÃ →
              </button>
            )}

            <div className="auth-footer-nav">
              <button
                type="button"
                className="auth-nav-link"
                onClick={() => { setAuthView('login'); setForgotError(''); setForgotPendingNotice(''); }}
              >
                ← Quay lại Đăng nhập
              </button>
            </div>
          </form>
        )}
      </div>
    );
  }
 return <div className="app-layout"><aside className="sidebar"><div className="brand"><div className="brand-mark">≋</div><div><strong>VESSEL MOTION</strong><small>GUARD / DEMO</small></div></div><span className="nav-label">OPERATIONS</span><nav aria-label="Menu chính">{NAV.map(n=><button key={n.key} className={page===n.key||(page==='report-detail'&&n.key==='reports')?'active':''} onClick={()=>goto(n.key)}>{n.label}<span>›</span></button>)}</nav><div className="sidebar-bottom"><Pill kind="normal">● SIMULATION</Pill><small>{session.role} · {session.username}</small><Button kind="ghost" onClick={logout}>Đăng xuất</Button></div></aside><div className="workspace"><div className="topbar"><div><b>SV<span>MG</span></b><span className="topbar-name">VESSEL DEMO 01</span></div><div className="topbar-right"><div className="theme-selector" role="group" aria-label="Giao diện hiển thị"><button type="button" className={`theme-opt-btn ${theme==='light'?'active':''}`} onClick={()=>setTheme('light')} title="Giao diện Light Maritime (Mặc định)">☀ LIGHT</button><button type="button" className={`theme-opt-btn ${theme==='dark'?'active':''}`} onClick={()=>setTheme('dark')} title="Giao diện Dark Maritime (Giao diện cũ)">🌙 DARK</button></div><Pill kind="caution">MOCK DATA</Pill><span className="micro">{session.role}</span><button className="top-logout" onClick={logout}>Thoát</button></div></div>{notice&&<div className="toast" role="status"><span>{notice}</span><button onClick={()=>setNotice('')} aria-label="Đóng thông báo">×</button></div>}<main className="main">{renderPage()}<div className="disclaimer">SMART VESSEL MOTION GUARD • TV4 UI DEMO • Không phải hệ thống cảnh báo được chứng nhận</div></main><nav className="mobile-nav" aria-label="Điều hướng điện thoại">{([{key:'overview',label:'Home'},{key:'motion',label:'Motion'},{key:'alarms',label:'Alarms'},{key:'reports',label:'Reports'},{key:'more',label:'More'}] as const).map(n=><button key={n.key} className={page===n.key||(n.key==='reports'&&page==='report-detail')||(n.key==='more'&&['control','replay','health','model'].includes(page))?'active':''} onClick={()=>goto(n.key)}>{n.label}</button>)}</nav></div></div>
}
