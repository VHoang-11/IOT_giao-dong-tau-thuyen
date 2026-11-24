import {useEffect,useMemo,useState} from 'react';
import type {ReactNode,FormEvent} from 'react';
import type {Alarm,Command,Page,Scenario,Session,MotionSnapshot,ZeroCalibration,ReplayPoint,FeatureItem} from './domain';
import {computeHealth,computeModelInfo,INITIAL_ALARMS,makeTelemetry,mockLogin,mockRegister,mockForgotPassword,MOCK_VOYAGES,REPLAY_SAMPLES,samples,SCENARIOS} from './mock';
import {exportFeaturesToCSV,CONTRACT_ID,CONTRACT_VERSION,CONTRACT_SOURCE_EXPORT,TOTAL_FEATURES} from './featureRegistry';
import { ShipMotionVisualizer } from './ShipMotionVisualizer';
import { LiveMotionChart } from './LiveMotionChart';
import { MaiAlarmsChart } from './MaiAlarmsChart';
import { VoyageKinematicDistributionChart, VoyageRfDistributionChart } from './VoyageAnalyticsCharts';
import { ModelConcordanceChart } from './ModelConcordanceChart';
import { i18n, getRoleNameVi, getAlarmLevelNameVi, getAlarmStatusNameVi, getRFClassNameVi, getScenarioNameVi, FEATURE_NAMES_VI } from './i18n/vi';

const NAV:{key:Page;label:string;mini:string}[]=[
 {key:'overview',label:i18n.nav.overview,mini:'Tổng quan'},
 {key:'motion',label:i18n.nav.motion,mini:'Chuyển động'},
 {key:'alarms',label:i18n.nav.alarms,mini:'Cảnh báo'},
 {key:'control',label:i18n.nav.control,mini:'Điều khiển'},
 {key:'reports',label:i18n.nav.reports,mini:'Báo cáo'},
 {key:'replay',label:i18n.nav.replay,mini:'Phát lại'},
 {key:'health',label:i18n.nav.health,mini:'Thiết bị'},
 {key:'model',label:i18n.nav.model,mini:'Mô hình AI'},
];
const format=(n:number|null|undefined,unit='°')=>n==null?'—':`${n>0?'+':''}${n.toFixed(1)}${unit}`;
const time=(iso?:string)=>iso?new Date(iso).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—';
const canOperate=(s:Session|null)=>!!s&&s.role!=='Operator';
const isAdmin=(s:Session|null)=>s?.role==='Admin';
function Pill({children,kind='neutral'}:{children:ReactNode;kind?:string}){return <span className={`pill ${kind.toLowerCase()}`}>{children}</span>}
function Panel({title,tag,children,footer}:{title:string;tag?:string;children:ReactNode;footer?:ReactNode}){return <section className="panel"><header className="panel-head"><h3>{title}</h3>{tag&&<span className="micro">{tag}</span>}</header>{children}{footer&&<footer className="panel-foot">{footer}</footer>}</section>}
function Metric({label,value,note,tone='cyan',className}:{label:string;value:string;note?:string;tone?:string;className?:string}){return <div className={`metric ${className||''}`}><span className="label">{label}</span><strong className={`metric-value ${tone}`}>{value}</strong>{note&&<span className="micro">{note}</span>}</div>}
function Button({children,onClick,disabled=false,kind='primary',title,style}:{children:ReactNode;onClick?:()=>void;disabled?:boolean;kind?:string;title?:string;style?:React.CSSProperties}){return <button type="button" className={`btn ${kind}`} style={style} onClick={onClick} disabled={disabled} title={title}>{children}</button>}
export function MotionChart({s,tick,height=190,offline=false}:{s:Scenario;tick:number;height?:number;offline?:boolean}){
 const arr=samples(s,tick,64),w=650,h=height,pad=15;const scale=(v:number)=>h/2-v*(h-2*pad)/42;
 const poly=(key:'roll'|'pitch')=>arr.map((v,i)=>`${(i/(arr.length-1))*w},${scale(v[key])}`).join(' ');
 return <div className="chart-holder" role="img" aria-label="Biểu đồ DEMO góc lắc ngang roll và lắc dọc pitch theo thời gian">
   {offline?<div className="chart-empty"><b>Không có dữ liệu trực tiếp</b><small>MẤT KẾT NỐI / LỖI CẢM BIẾN – không suy diễn trạng thái BÌNH THƯỜNG</small></div>:<>
   <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" width="100%" height={height} aria-hidden="true">
    {[.25,.5,.75].map(y=><line key={y} x1="0" y1={y*h} x2={w} y2={y*h} stroke="var(--border-subtle, #D0DDEB)" strokeDasharray="4 7" />)}
    <line x1="0" y1={h/2} x2={w} y2={h/2} stroke="var(--border-color, #183E65)" strokeWidth="1.2" />
    <polyline points={poly('roll')} fill="none" stroke="#0284C7" strokeWidth="2.8" vectorEffect="non-scaling-stroke"/>
    <polyline points={poly('pitch')} fill="none" stroke="#D97706" strokeWidth="2.2" vectorEffect="non-scaling-stroke"/>
   </svg><div className="legend"><span><i className="dot cyan-bg" style={{background:'#0284C7'}}/>Roll (°)</span><span><i className="dot amber-bg" style={{background:'#D97706'}}/>Pitch (°)</span><span className="micro">Mô phỏng</span></div></>}
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

 const rollAreaPath = useMemo(() => {
   if (!samples.length) return '';
   const pts = samples.map((v, i) => `${(i / (samples.length - 1)) * w},${scale(v.roll)}`);
   const zeroY = scale(0);
   return `M 0 ${zeroY} L ${pts.join(' L ')} L ${w} ${zeroY} Z`;
 }, [samples]);

 const handleSeek = (clientX: number, rect: DOMRect) => {
   const ratio=Math.max(0,Math.min(1,(clientX-rect.left)/rect.width));
   onSeek(Math.round(ratio*(samples.length-1)));
 };

 const activeIdx = hoverIdx !== null ? hoverIdx : currentIndex;
 const activeSample = samples[activeIdx] || samples[0];

 return <div className="chart-holder" style={{position:'relative',overflow:'hidden',background:'var(--panel-bg)',borderRadius:12,border:'1px solid var(--border-color)',boxShadow:'var(--card-shadow)',padding:'12px 14px 8px'}}>
  <svg
   viewBox={`0 0 ${w} ${h}`}
   preserveAspectRatio="none"
   width="100%"
   height={h}
   style={{cursor:'crosshair',display:'block',touchAction:'none'}}
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
   aria-label="Biểu đồ dao động Roll và Pitch phát lại Replay"
  >
   <defs>
    <linearGradient id="replayRollAreaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stopColor="#0284C7" stopOpacity="0.20" />
      <stop offset="50%" stopColor="#0284C7" stopOpacity="0.04" />
      <stop offset="100%" stopColor="#0284C7" stopOpacity="0.20" />
    </linearGradient>
   </defs>

   {/* Background Rect */}
   <rect x="0" y="0" width={w} height={h} fill="var(--panel-bg)" rx={6} />

   {/* Degree Gridlines */}
   {[-15, 0, 15].map(deg => (
    <g key={deg}>
      <line x1="0" y1={scale(deg)} x2={w} y2={scale(deg)} stroke={deg===0?"var(--accent-color)":"var(--border-subtle)"} strokeWidth={deg===0?1.4:0.8} strokeDasharray={deg===0?undefined:"3 4"} opacity={deg===0?0.6:0.7} />
      <text x={w - 6} y={scale(deg) - 3} textAnchor="end" fill={deg===0?"var(--text-main)":"var(--text-muted)"} fontSize="9" fontFamily="'Be Vietnam Pro', sans-serif" fontWeight={deg===0?600:400}>
        {deg > 0 ? `+${deg}°` : `${deg}°`}
      </text>
    </g>
   ))}

   {/* Roll Area Fill Gradient */}
   <path d={rollAreaPath} fill="url(#replayRollAreaGrad)" />

   {/* Alarms with beacon markers (No concentric rings) */}
   {alarmsWithMarkers.map(ap=>{
    const ax=(ap.seq/(samples.length-1))*w;
    const col=ap.alarm_level==='CRITICAL'?'#EF4444':ap.alarm_level==='WARNING'?'#F59E0B':'#0284C7';
    return <g key={ap.seq} onClick={(e)=>{ e.stopPropagation(); onSeek(ap.seq); }} style={{cursor:'pointer'}} aria-label={`Sự kiện ${ap.alarm_id}`}>
     {/* Tether drop-line */}
     <line x1={ax} y1={22} x2={ax} y2={scale(ap.roll)} stroke={col} strokeWidth="1.1" strokeDasharray="2 2" opacity={0.8} />
     {/* Single small solid dot on curve */}
     <circle cx={ax} cy={scale(ap.roll)} r="3.5" fill={col} stroke="var(--panel-bg)" strokeWidth="1.5" />
     {/* Beacon pill at top */}
     <rect x={ax - 22} y={6} width={44} height={16} rx={4} fill={col} />
     <polygon points={`${ax - 3},22 ${ax + 3},22 ${ax},24.5`} fill={col} />
     <text x={ax} y={17.5} textAnchor="middle" fill="#FFFFFF" fontSize="8" fontFamily="'JetBrains Mono', monospace" fontWeight="600">{ap.alarm_id}</text>
    </g>;
   })}

   {/* Waveform curves */}
   <polyline points={poly('pitch')} fill="none" stroke="#F59E0B" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" opacity="0.9"/>
   <polyline points={poly('roll')} fill="none" stroke="#0284C7" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke"/>

   {/* Playhead vertical needle with single solid dot (No concentric rings) */}
   <line x1={curX} y1="0" x2={curX} y2={h} stroke="#10B981" strokeWidth="2" />
   <circle cx={curX} cy={scale(samples[currentIndex]?.roll||0)} r="3.5" fill="#10B981" stroke="var(--panel-bg)" strokeWidth="1.5" />

   {/* Hover vertical slice & guide line if different */}
   {hoverIdx !== null && hoverIdx !== currentIndex && (
    <g>
      <rect x={(hoverIdx/(samples.length-1))*w - 6} y="0" width="12" height={h} fill="var(--accent-color)" fillOpacity="0.05" rx={2} />
      <line x1={(hoverIdx/(samples.length-1))*w} y1="0" x2={(hoverIdx/(samples.length-1))*w} y2={h} stroke="var(--accent-color)" strokeWidth="1.1" strokeDasharray="2 2" opacity="0.75" />
    </g>
   )}
  </svg>

  {/* Clamped Floating Readout HUD */}
  <div
    className="chart-tooltip"
    style={{
      top: 12,
      left: `${Math.max(16, Math.min(84, (activeIdx / (samples.length - 1)) * 100))}%`,
      transform: 'translateX(-50%)',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
    }}
  >
   <div>
     <span style={{color:'var(--text-muted)',fontSize:'0.68rem'}}>Mốc:</span>{' '}
     <b style={{color:'var(--text-main)',fontVariantNumeric:'tabular-nums'}}>T+{activeSample.t_sim_s}s</b>
   </div>
   <div style={{borderLeft:'1px solid var(--border-color)',paddingLeft:8}}>
     <span style={{color:'var(--color-metric-tech)',fontWeight:600}}>Roll: {activeSample.roll>0?`+${activeSample.roll.toFixed(1)}°`:`${activeSample.roll.toFixed(1)}°`}</span>
   </div>
   <div style={{borderLeft:'1px solid var(--border-color)',paddingLeft:8}}>
     <span style={{color:'var(--color-status-caution)',fontWeight:600}}>Pitch: {activeSample.pitch>0?`+${activeSample.pitch.toFixed(1)}°`:`${activeSample.pitch.toFixed(1)}°`}</span>
   </div>
   <div style={{borderLeft:'1px solid var(--border-color)',paddingLeft:8}}>
     <span style={{
       fontSize:'0.65rem',
       fontWeight:600,
       padding:'2px 6px',
       borderRadius:4,
       background:activeSample.mai>=70?'var(--note-danger-bg)':activeSample.mai>=35?'var(--note-warn-bg)':'var(--note-success-bg)',
       color:activeSample.mai>=70?'var(--status-red-text)':activeSample.mai>=35?'var(--status-amber-text)':'var(--status-green-text)',
     }}>
       MAI {activeSample.mai}
     </span>
   </div>
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
 const [forgotPendingNotice,setForgotPendingNotice]=useState('');const [authLoading,setAuthLoading]=useState(false);
 const [page,setPage]=useState<Page>('overview');const [scenario,setScenario]=useState<Scenario>('S0');const [tick,setTick]=useState(62);const [profile,setProfile]=useState('STANDARD');const [configVersion,setConfigVersion]=useState(7);const [previousProfile,setPreviousProfile]=useState('STANDARD');const [hasPreviousProfile,setHasPreviousProfile]=useState(false);const [timewarp,setTimewarp]=useState(1);const [activeModel,setActiveModel]=useState<'RF'|'BASELINE_B'>('RF');
 const [alarms,setAlarms]=useState<Alarm[]>(INITIAL_ALARMS);const [alarmId,setAlarmId]=useState<string|null>(null);const [alarmFilter,setAlarmFilter]=useState('ALL');
 const [commands,setCommands]=useState<Command[]>([]);const [notice,setNotice]=useState('');const [replayIndex,setReplayIndex]=useState(0);const [playing,setPlaying]=useState(false);const [speed,setSpeed]=useState(1);
 const [selectedVoyageId,setSelectedVoyageId]=useState('V-2026-001');
 const [latestSnapshot,setLatestSnapshot]=useState<MotionSnapshot|null>(null);
 const [zeroCalibration,setZeroCalibration]=useState<ZeroCalibration|null>(null);
 const [hoveredMotionSample, setHoveredMotionSample] = useState<{ roll: number; pitch: number; t: number } | null>(null);
 const [featureGroupFilter, setFeatureGroupFilter] = useState<'ALL' | 'roll_60s' | 'roll_180s' | 'pitch_60s'>('ALL');
 const thresholds = PROFILE_THRESHOLDS[profile] || PROFILE_THRESHOLDS['STANDARD'];
 const selectedVoyage = useMemo(()=>MOCK_VOYAGES.find(v=>v.id===selectedVoyageId)||MOCK_VOYAGES[0],[selectedVoyageId]);
 const telemetry=useMemo(()=>makeTelemetry(scenario,tick,configVersion),[scenario,tick,configVersion]);
 const health=useMemo(()=>computeHealth(scenario,tick),[scenario,tick]);
 const modelInfo=useMemo(()=>computeModelInfo(activeModel,scenario,telemetry?.sensor_ok),[activeModel,scenario,telemetry?.sensor_ok]);
 const downloadFeaturesCSV=(items:FeatureItem[])=>{
  const content=exportFeaturesToCSV(items,{voyageId:selectedVoyage.id,isMock:true});
  const blob=new Blob([content],{type:'text/csv;charset=utf-8'});
  const u=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=u;
  a.download=`SVMG_${selectedVoyage.id}_features23_${CONTRACT_VERSION}.csv`;
  a.click();
  URL.revokeObjectURL(u);
  setNotice(`Đã xuất CSV 23 đặc trưng (${CONTRACT_VERSION})`);
 };
 useEffect(()=>{
  if(!notice)return;
  const t=window.setTimeout(()=>setNotice(''),4500);
  return()=>window.clearTimeout(t);
 },[notice]);
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
 const goto=(p:Page)=>{setPage(p);setAlarmId(null);window.scrollTo({top:0,behavior:'smooth'})};
 const submitLogin=(e:FormEvent)=>{
  e.preventDefault();
  setAuthLoading(true);
  const result=mockLogin(loginName,loginPass);
  if(!result){
   setLoginError('Tài khoản hoặc mã truy cập (passcode) chưa đúng. Vui lòng kiểm tra lại.');
   setAuthLoading(false);
   return;
  }
  setSession(result);
  setPage('overview');
  setLoginError('');
  setNotice(`Đăng nhập thành công • Vai trò: ${result.role} (${result.displayName})`);
  setAuthLoading(false);
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
  if(requireAdmin?!isAdmin(session):!canOperate(session)){setNotice(`Không đủ quyền thực hiện lệnh (Vai trò: ${session?.role??'Operator'} không được phép).`);return}
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
  <div className="alarm-title"><div><b>{a.id}</b> <span className="muted">• {a.title}</span></div><Pill kind={a.level}>{getAlarmLevelNameVi(a.level)}</Pill></div>
  <div className="data-line"><span className="micro">{a.raisedAt.startsWith('2026')?time(a.raisedAt):a.raisedAt} · {getAlarmStatusNameVi(a.status)}</span>{a.mutedUntil&&<span className="micro">Đã tắt còi</span>}</div>
  {detail&&<div className="button-line"><Button kind="secondary" disabled={a.status!=='RAISED'} onClick={()=>ackAlarm(a.id)}>{a.status==='ACKED'?'✓ Đã tiếp nhận':'Xác nhận (ACK)'}</Button><Button kind="ghost" disabled={a.status==='CLEARED'||a.level==='CRITICAL'} title={a.level==='CRITICAL'?'Không tắt còi khi mức NGUY CẤP':''} onClick={()=>muteAlarm(a.id)}>{a.mutedUntil?'✓ Đã tắt còi':'Tắt còi ≤300s'}</Button></div>}
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
      <span className="eyebrow">Buồng lái chỉ huy</span>
      <h1>Tổng quan vận hành</h1>
      <p>Tổng quan an toàn: Trạng thái tàu, kết nối cảm biến IoT, chỉ số bất thường MAI và cảnh báo trực ca.</p>
     </div>
     <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
      <Pill kind={isConnected ? 'normal' : scenario==='OFFLINE' ? 'critical' : 'fault'}>
       {isConnected ? '● TRỰC TUYẾN' : scenario==='OFFLINE' ? 'MẤT KẾT NỐI (>30s)' : 'LỖI CẢM BIẾN (I2C)'}
      </Pill>
      <Pill kind={activeSeverity}>
       {getAlarmLevelNameVi(activeSeverity)}
      </Pill>
     </div>
    </div>

    <div className="metrics">
     <Metric
      label="Mức cảnh báo tàu"
      value={getAlarmLevelNameVi(activeSeverity)}
      note={activeSeverity === 'CRITICAL' ? 'Nguy cấp: Vượt ngưỡng Trip' : activeSeverity === 'WARNING' ? 'Cảnh báo: Biên độ lắc lớn' : 'An toàn trong giới hạn'}
      tone={activeSeverity === 'CRITICAL' ? 'red' : activeSeverity === 'WARNING' ? 'amber' : 'green'}
     />
     <Metric
      label="Trạng thái thiết bị"
      value={isConnected ? 'Đang kết nối' : (scenario === 'OFFLINE' ? 'Mất kết nối' : 'Lỗi cảm biến')}
      note={isConnected ? 'Thông tin thiết bị' : 'Mất tín hiệu viễn trắc'}
      tone={isConnected ? 'green' : (scenario === 'OFFLINE' ? 'red' : 'amber')}
     />
     <Metric
      label="Chỉ số bất thường MAI"
      value={isConnected ? `${telemetry.mai} / 100` : '—'}
      note={(telemetry?.mai||0) >= 70 ? 'Vượt ngưỡng cảnh giác (≥70)' : (telemetry?.mai||0) >= 35 ? 'Mức theo dõi (35-70)' : 'Biển êm / Bình thường (<35)'}
      tone={(telemetry?.mai||0) >= 70 ? 'red' : (telemetry?.mai||0) >= 35 ? 'amber' : 'green'}
     />
     <Metric
      label="Cảnh báo ca trực"
      value={activeSeverity === 'NORMAL' && raisedAlarms.length === 0 ? '0 đang mở' : `${raisedAlarms.length} đang mở`}
      note={activeSeverity === 'NORMAL' && raisedAlarms.length === 0 ? 'Toàn bộ hệ thống an toàn' : `${ackedAlarms.length} đã xác nhận (ACK)`}
      tone={raisedAlarms.length > 0 ? 'red' : 'green'}
     />
    </div>

    <div className="columns">
     <div>
      {/* Panel 1: Kinematics Summary */}
      <Panel title="Tóm tắt động học thân tàu" tag="Tức thời • Chu kỳ 5s">
       <div style={{marginBottom:14}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:4}}>
         <span className="micro" style={{fontWeight:600}}>Chỉ số bất thường MAI hiện tại</span>
         <span className={isConnected ? (((telemetry?.mai||0)>=70)?'text-danger':((telemetry?.mai||0)>=35)?'text-warning':'text-success') : 'text-muted'} style={{fontWeight:600,fontVariantNumeric:'tabular-nums'}}>
          {isConnected ? `${telemetry?.mai} / 100` : 'Không khả dụng'}
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
         {isConnected ? `${format(telemetry?.pitch_deg)} (${(telemetry?.pitch_deg||0) > 0.1 ? 'Ngóc mũi / BOW UP' : (telemetry?.pitch_deg||0) < -0.1 ? 'Chúi mũi / BOW DN' : 'Mức chuẩn'})` : '—'}
        </dd>
        <dt>Nhận dạng TinyML (Random Forest)</dt>
        <dd className="text-success" style={{fontWeight:600}}>{getRFClassNameVi(telemetry?.class_rf)} ({telemetry?.class_rf ?? 'UNKNOWN'})</dd>
        <dt>Ngưỡng an toàn mô phỏng</dt>
        <dd>Cảnh báo ±{thresholds.roll_warning_deg}° • Nguy cấp ±{thresholds.roll_trip_deg}°</dd>
       </dl>


      </Panel>

      {/* Panel 2: Thông số tàu & kết nối */}
      <Panel title="Thông số tàu & Kết nối thiết bị" tag="vessel-demo-01">
       <dl className="kv">
        <dt>Tên tàu / Nhận dạng</dt><dd>Tàu Container MV SVMG-01 (IMO-9876543)</dd>
        <dt>Chế độ nguồn dữ liệu (Source Mode)</dt><dd>Mô phỏng (SIMULATION)</dd>
        <dt>Kịch bản kiểm thử hiện hành</dt><dd className="text-info" style={{fontWeight:600}}>{scenario} — {getScenarioNameVi(scenario)}</dd>
        <dt>Đồng hồ mô phỏng (t_sim_s)</dt><dd>T+{telemetry?.t_sim_s ?? '—'}s (Chu kỳ 5.0s)</dd>
        <dt>Cấu hình Profile / Phiên bản</dt><dd>{profile} (v{configVersion})</dd>
        <dt>Sĩ quan ca trực hiện tại</dt><dd>{session?.username} ({getRoleNameVi(session?.role)})</dd>
       </dl>

      </Panel>
     </div>

     <div>
      {/* Panel 3: Actionable Alarms */}
      <Panel title="Cảnh báo đang mở & Cần xử lý" tag={raisedAlarms.length > 0 ? `${raisedAlarms.length} sự kiện chờ xử lý` : 'An toàn'}>
       {raisedAlarms.length > 0 ? (
        <>
         <p className="micro" style={{marginBottom:10}}>Các cảnh báo đang mở cần sĩ quan trực ca tiếp nhận (ACK) hoặc kiểm tra an toàn:</p>
         {raisedAlarms.slice(0, 3).map(a => renderAlarm(a, true))}
        </>
       ) : (
        <div className="note success" style={{marginBottom:12}}>
         <b>✓ Trạng thái ca trực an toàn:</b> Hiện không có cảnh báo nào ở trạng thái chờ xử lý (RAISED). Mọi dao động thân tàu và chỉ số MAI đều nằm trong ngưỡng an toàn cho phép.
        </div>
       )}

       <div style={{marginTop:14,display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:8}}>
        <span className="micro muted">Tổng cộng {alarms.length} sự kiện trong phiên</span>
       </div>
      </Panel>

      {/* Panel 4: Sẵn sàng hệ thống & Quy chuẩn ca trực */}
      <Panel title="Sẵn sàng hệ thống & Quy chuẩn ca trực" tag="Sẵn sàng hoạt động">
       <dl className="kv">
        <dt>Độ khả dụng dữ liệu (Availability)</dt>
        <dd className={isConnected ? 'text-success' : 'text-danger'} style={{fontWeight:600}}>
         {isConnected ? '100% (MPU6050 Trực tiếp)' : '0% (MẤT TÍN HIỆU)'}
        </dd>
        <dt>Mô hình TinyML tại biên</dt><dd>Random Forest v2.4 (10 cây quyết định)</dd>
        <dt>Chu kỳ làm mới dữ liệu</dt><dd>1.1s / bước (Tương đương 5.0s mô phỏng)</dd>
        <dt>Tiêu chuẩn cảnh báo nội bộ</dt><dd>Dải an toàn 15°–22° (Cấu hình mô phỏng)</dd>
       </dl>
       <div className="note" style={{marginTop:12}}>
        <b>Quy tắc an toàn buồng lái:</b> Sĩ quan trực ca theo dõi sát chỉ số MAI khi vượt ngưỡng 35. Tuyệt đối không tắt còi báo động khi sự cố đạt mức NGUY CẤP (CRITICAL).
       </div>
      </Panel>
     </div>
    </div>
   </>;
  }
  case 'motion':return <>
   <div className="page-hero">
    <div>
     <span className="eyebrow">Viễn trắc động học thời gian thực</span>
     <h1>Giám sát chuyển động</h1>
     <p>Giám sát dao động thân tàu thời gian thực: Đồ thị dao động Roll/Pitch, mô hình số hóa 3D, đối chiếu TinyML và xu hướng MAI.</p>
    </div>

   </div>

   {/* Clean 4-card compact metrics */}
   <div className="compact-metrics-grid" style={{marginBottom: 20}}>
    <Metric
     label="Góc lắc ngang tức thời"
     value={telemetry?.sensor_ok?format(telemetry.roll_deg):'—'}
     note={telemetry?.sensor_ok ? (telemetry.roll_deg > 0.1 ? 'Mạn phải' : telemetry.roll_deg < -0.1 ? 'Mạn trái' : 'Cân bằng') : 'Mất dữ liệu'}
     tone={Math.abs(telemetry?.roll_deg||0)>=thresholds.roll_warning_deg?'red':'cyan'}
    />
    <Metric
     label="Góc chúi dọc tức thời"
     value={telemetry?.sensor_ok?format(telemetry.pitch_deg):'—'}
     note={telemetry?.sensor_ok ? (telemetry.pitch_deg > 0.1 ? 'Ngóc mũi' : telemetry.pitch_deg < -0.1 ? 'Chúi mũi' : 'Mức chuẩn') : 'Mất dữ liệu'}
     tone="amber"
    />
    <Metric
     label="Chỉ số bất thường MAI"
     value={telemetry?.sensor_ok?`${telemetry.mai} / 100`:'—'}
     note={(telemetry?.mai||0)>=70?'Nguy cấp':(telemetry?.mai||0)>=35?'Cảnh giác':'Bình thường'}
     tone={(telemetry?.mai||0)>=70?'red':(telemetry?.mai||0)>=35?'amber':'green'}
    />
    <Metric
     className="metric-tinyml"
     label="Mô hình phân loại"
     value={telemetry?.sensor_ok ? getRFClassNameVi(telemetry?.class_rf) : 'Mất tín hiệu'}
     note="23 đặc trưng đầu vào"
     tone={!telemetry?.sensor_ok ? 'red' : telemetry?.class_rf === 'NORMAL' ? 'green' : 'amber'}
    />
   </div>

   {/* Primary 2-Column Split Monitoring Area (Desktop: 48% Visualizer / 52% Oscilloscope) */}
   <div className="motion-monitoring-grid">
    <Panel title="Mô hình chuyển động tàu" tag="Đồng bộ góc Roll & Pitch thời gian thực">
     <ShipMotionVisualizer
      rollDeg={hoveredMotionSample ? hoveredMotionSample.roll : (telemetry?.sensor_ok ? telemetry.roll_deg : null)}
      pitchDeg={hoveredMotionSample ? hoveredMotionSample.pitch : (telemetry?.sensor_ok ? telemetry.pitch_deg : null)}
      mai={telemetry?.sensor_ok ? telemetry.mai : null}
      alarmLevel={telemetry?.alarm_level || 'NORMAL'}
      scenario={scenario}
      classRf={telemetry?.class_rf || 'NORMAL'}
      sourceMode={telemetry?.source_mode || 'SIMULATION'}
      sensorOk={telemetry?.sensor_ok}
      variant="split"
      hoveredSample={hoveredMotionSample}
      warningDeg={thresholds.roll_warning_deg}
      tripDeg={thresholds.roll_trip_deg}
     />
    </Panel>

    <Panel title="Biểu đồ dao động" tag="Live Mock • 1.1s/step">
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
   </div>

   {/* MAI Timeline Trend & Alarm Triggers */}
   <Panel title="Xu hướng chỉ số bất thường MAI" tag="TinyML Anomaly Tracking">
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
    <Panel title="Mô hình phân loại & Đối chiếu Shadow" tag="Random Forest vs Baseline B">
     <dl className="kv">
      <dt>Random Forest (Mô hình chính)</dt><dd className="text-info" style={{fontWeight:600}}>{getRFClassNameVi(telemetry?.class_rf)} ({telemetry?.class_rf??'UNKNOWN'})</dd>
      <dt>Baseline B (Mô hình đối chiếu Shadow)</dt><dd className="text-warning" style={{fontWeight:600}}>{getRFClassNameVi(telemetry?.class_baseline_b)} ({telemetry?.class_baseline_b??'UNKNOWN'})</dd>
      <dt>Độ đồng thuận (Concordance)</dt>
      <dd className={!telemetry?.sensor_ok ? 'text-muted' : (telemetry.class_rf === telemetry.class_baseline_b ? 'text-success' : 'text-warning')} style={{fontWeight:600}}>
       {!telemetry?.sensor_ok ? 'Không khả dụng' : (telemetry.class_rf === telemetry.class_baseline_b ? '✓ Đồng thuận' : '⚠ Bất đồng')}
      </dd>
      <dt>Phiên bản mô hình (Registry)</dt><dd>{telemetry?.model_version ?? 'RF-DEMO-v1'}</dd>
      <dt>Tình trạng cảm biến IMU</dt>
      <dd className={telemetry?.sensor_ok ? 'text-success' : 'text-danger'} style={{fontWeight:600}}>
       {telemetry?.sensor_ok ? 'BÌNH THƯỜNG (MPU6050 400kHz)' : 'MẤT KẾT NỐI / I2C NACK'}
      </dd>
     </dl>
    </Panel>

   </div>
  </>;
  case 'alarms':return <>
   <header className="page-heading">
    <h1>Quản lý cảnh báo</h1>
    <p>Theo dõi, tiếp nhận (ACK) và tạm tắt còi các cảnh báo dao động tàu vượt ngưỡng an toàn.</p>
   </header>
   <div className="metrics">
    <Metric label="Đang phát" value={String(alarms.filter(a=>a.status==='RAISED').length)} tone={alarms.filter(a=>a.status==='RAISED').length>0?'red':'green'}/>
    <Metric label="Đã xác nhận" value={String(alarms.filter(a=>a.status==='ACKED').length)} tone="amber"/>
    <Metric label="Đã kết thúc" value={String(alarms.filter(a=>a.status==='CLEARED').length)} tone="green"/>
    <Metric label="Thời gian tiếp nhận TB" value={(()=>{const list=alarms.filter(a=>a.ackedAt);return list.length?`${Math.round(list.reduce((a,v)=>a+(new Date(v.ackedAt!).getTime()-new Date(v.raisedAt).getTime())/1000,0)/list.length)}s`:'—'})()} tone="cyan"/>
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

   <Panel title="Danh sách cảnh báo" tag="Nhật ký ca trực"><div className="filter-line"><label htmlFor="alarm-filter">Lọc trạng thái</label><select id="alarm-filter" value={alarmFilter} onChange={e=>setAlarmFilter(e.target.value)}>
      <option value="ALL">Tất cả trạng thái</option>
      <option value="RAISED">Đang phát (RAISED)</option>
      <option value="ACKED">Đã xác nhận (ACKED)</option>
      <option value="CLEARED">Đã kết thúc (CLEARED)</option>
      <option value="CRITICAL">Nguy cấp (CRITICAL)</option>
      <option value="WARNING">Cảnh báo (WARNING)</option>
    </select></div>
   {alarms.filter(a=>alarmFilter==='ALL'||a.status===alarmFilter||a.level===alarmFilter).map(a=>renderAlarm(a,true))}
   {alarms.every(a=>alarmFilter!=='ALL'&&a.status!==alarmFilter&&a.level!==alarmFilter)&&<p>Không có cảnh báo phù hợp.</p>}</Panel>
   {alarmId&&<Panel title={`Chi tiết cảnh báo ${alarmId}`} tag="Sự cố">{alarms.filter(a=>a.id===alarmId).map(a=>renderAlarm(a,true))}<Button kind="ghost" onClick={()=>setAlarmId(null)}>Đóng chi tiết</Button></Panel>}
   <div className="note">Tiếp nhận (ACK) ghi nhận sĩ quan đã xử lý sự cố. Cảnh báo NGUY CẤP không cho phép tắt còi (MUTE).</div></>;
  case 'control':{
   const isOp=session?.role==='Operator';
   const isSup=session?.role==='Supervisor';
   const isAdm=session?.role==='Admin';
   return <>
    <div className="page-hero">
     <div>
      <span className="eyebrow">Trung tâm điều khiển</span>
      <h1>Trung tâm điều khiển</h1>
      <p>Quản trị cấu hình thiết bị giám sát chuyển động và thông số an toàn.</p>
     </div>
     <Pill kind={isAdm?'normal':isSup?'caution':'warning'}>
      {isAdm?'Quản trị viên: Toàn quyền':isSup?'Giám sát viên: Cấu hình':'Sĩ quan trực ca: Chỉ xem'}
     </Pill>
    </div>

    <div className="note" style={{marginBottom:18}}>
     <b>Lưu ý ngưỡng cảnh báo:</b> Các ngưỡng Roll Warning, Roll Trip và MAI là cấu hình mô phỏng an toàn (dải góc an toàn 15°–25°).
    </div>

    {isOp && (
     <div className="note warning" style={{marginBottom:18}}>
      <b>Chế độ chỉ đọc (Operator):</b> Tài khoản Sĩ quan trực ca chỉ xem cấu hình hiện hành và nhật ký lệnh. Để điều chỉnh cấu hình hoặc gửi lệnh, vui lòng đăng nhập tài khoản <code>supervisor</code> hoặc <code>admin</code>.
     </div>
    )}

    <div className="metrics">
     <Metric label="Profile hiện hành" value={profile} note="Cấu hình ngưỡng mô phỏng" tone="cyan"/>
     <Metric label="Phiên bản cấu hình" value={`v${configVersion}`} note="Phiên bản cấu hình" tone="green"/>
     <Metric label="Ngưỡng lắc an toàn" value={`${thresholds.roll_warning_deg}° / ${thresholds.roll_trip_deg}°`} note="Ngưỡng mô phỏng nhóm" tone="amber"/>
     <Metric label="Ngưỡng MAI" value={String(thresholds.mai_alert_threshold)} note="Motion Anomaly Index" tone="red"/>
    </div>

    <div className="columns">
     <div>
      <Panel title="Cấu hình thiết bị giám sát" tag={`v${configVersion}`}>
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
         <Button kind={profile==='STANDARD'?'primary':'secondary'} disabled={!canOperate(session)} onClick={()=>sendCommand('set_profile',false,'STANDARD')}>STANDARD (15°/22°) — Tiêu chuẩn</Button>
         <Button kind={profile==='SENSITIVE'?'primary':'secondary'} disabled={!canOperate(session)} onClick={()=>sendCommand('set_profile',false,'SENSITIVE')}>SENSITIVE (12°/18°) — Nhạy cao</Button>
         <Button kind={profile==='CONSERVATIVE'?'primary':'secondary'} disabled={!canOperate(session)} onClick={()=>sendCommand('set_profile',false,'CONSERVATIVE')}>CONSERVATIVE (18°/25°) — An toàn cao</Button>
        </div>
       </div>
       <div style={{marginTop:14}}>
        <Button kind="ghost" disabled={!canOperate(session)||!hasPreviousProfile} onClick={()=>sendCommand('rollback')}>
         {hasPreviousProfile ? `Khôi phục cấu hình trước (${previousProfile})` : 'Khôi phục cấu hình (Không có bản trước)'}
        </Button>
        <small className="muted" style={{display:'block',marginTop:5}}>Rollback khôi phục cấu hình hợp lệ trước đó và tăng số phiên bản config_version.</small>
       </div>
      </Panel>

      <Panel title="Lệnh điều khiển thiết bị" tag="Supervisor / Admin">
       <p className="micro">Các lệnh kiểm tra và hiệu chuẩn thiết bị giám sát tại chỗ.</p>
       <div className="button-line">
        <Button disabled={!canOperate(session)} onClick={()=>sendCommand('calibrate_zero')}>Hiệu chuẩn điểm 0 (30s tĩnh)</Button>
        <Button kind="secondary" disabled={!canOperate(session)} onClick={()=>sendCommand('request_snapshot')}>Yêu cầu chụp viễn trắc (180s)</Button>
       </div>
       <p className="note" style={{marginTop:12}}>
        <b>Quy tắc an toàn:</b> Calibrate Zero kiểm tra phương sai trong 30s và chỉ chấp nhận khi tín hiệu ở trạng thái tĩnh (S0 - Biển êm, σ ≤ 1.0°). Nếu tàu đang lắc ở các kịch bản khác, lệnh sẽ bị <code>REJECTED: NOT_STATIC</code>. Lệnh Snapshot trích xuất chuỗi 180s và lưu trực tiếp vào Mock State.
       </p>
      </Panel>

      {latestSnapshot && (
       <Panel title="Bản chụp dữ liệu động học (180s)" tag="Mock State Artifact">
        <dl className="kv">
         <dt>Mã Snapshot</dt><dd>{latestSnapshot.snapshot_id}</dd>
         <dt>Thời điểm tạo</dt><dd>{time(latestSnapshot.timestamp)}</dd>
         <dt>Độ dài cửa sổ</dt><dd>{latestSnapshot.window_s}s ({latestSnapshot.sample_count} mẫu)</dd>
         <dt>Giới hạn Roll</dt><dd>{format(latestSnapshot.roll_min)} .. {format(latestSnapshot.roll_max)}</dd>
         <dt>RMS Roll</dt><dd>{format(latestSnapshot.rms_roll_deg)}</dd>
         <dt>MAI Snapshot</dt><dd>{latestSnapshot.mai}</dd>
         <dt>Người yêu cầu</dt><dd>{latestSnapshot.triggered_by}</dd>
         <dt>Trạng thái</dt><dd className="text-success" style={{fontWeight:600}}>Đã lưu trạng thái mô phỏng</dd>
        </dl>
       </Panel>
      )}

      <details className="panel" style={{marginBottom:16}}>
       <summary style={{fontWeight:600,fontSize:'0.82rem',color:'var(--text-muted)',cursor:'pointer',padding:'4px 0'}}>
        Tiện ích kiểm thử giao diện (Chỉ dành cho Mock) • Nhấp để mở rộng
       </summary>
       <div style={{marginTop:10}}>
        <p className="micro">Tiện ích giả lập sự cố kết nối phục vụ kiểm thử giao diện & vòng đời lệnh TIMEOUT:</p>
        <div className="button-line">
         <Button kind="ghost" disabled={!canOperate(session)} onClick={()=>sendCommand('test_timeout')}>[TEST UTILITY] Thử nghiệm TIMEOUT (TTL 30s)</Button>
        </div>
       </div>
      </details>
     </div>

     <div>
      <Panel title="Quản trị mô phỏng & AI" tag="Admin Only">
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

    <Panel title="Lịch sử thực thi lệnh" tag="Sent → Delivered → Applied / Rejected / Timeout">
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
      <span className="eyebrow">Báo cáo hành trình</span>
      <h1>Báo cáo hành trình</h1>
      <p>Quản lý hành trình, thống kê chuyển động học và phân bố nhận dạng rủi ro.</p>
     </div>
     <Pill kind="normal">Dữ liệu mô phỏng</Pill>
    </div>

    {/* Voyage Selector Tabs */}
    <Panel title="Danh sách chuyến đi mô phỏng" tag="Chọn chuyến">
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
     <Metric label="Thời lượng" value={`${v.durationMinutes} phút`} note={`${v.sampleCount} mẫu`} tone="cyan"/>
     <Metric label="Sự kiện cảnh báo" value={String(v.alarms)} note={v.alarms>0?'Cần xem xét':'Bình thường'} tone={v.alarms>0?'amber':'green'}/>
     <Metric label="Góc lắc ngang cực đại |°|" value={`${v.maxAbsRollDeg.toFixed(1)}°`} note={v.maxAbsRollDeg>15?'Vượt ngưỡng 15°':'An toàn'} tone={v.maxAbsRollDeg>15?'red':'amber'}/>
     <Metric label="Góc lắc ngang RMS" value={`${v.rmsRollDeg.toFixed(2)}°`} note="Độ lệch chuẩn lắc ngang" tone="cyan"/>
    </div>

    <div className="metrics">
     <Metric label="Phân vị 95 lắc ngang (P95)" value={`${v.p95AbsRollDeg.toFixed(2)}°`} note="Phân vị 95% biên độ" tone="cyan"/>
     <Metric label="Góc chúi cực đại / RMS" value={`${v.maxAbsPitchDeg.toFixed(1)}° / ${v.rmsPitchDeg.toFixed(2)}°`} note="Lắc dọc thân tàu" tone="cyan"/>
     <Metric label="MAI cực đại" value={`${v.maiMax} / 100`} note="Chỉ số MAI lớn nhất" tone={v.maiMax>=70?'red':v.maiMax>=35?'amber':'green'}/>
     <Metric label="MAI trung bình" value={`${v.maiAvg} / 100`} note={`Thời gian vượt ngưỡng: ${v.maiCautionMinutes} phút`} tone={v.maiAvg>=70?'red':v.maiAvg>=35?'amber':'green'}/>
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
      <Panel title="Phân bố nhận dạng Random Forest" tag={`${v.agreementPercent}% ĐỒNG THUẬN BASELINE B`}>
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
      <Panel title="Thao tác hành trình" tag="M4-05">
       <p className="micro">Xem chi tiết báo cáo kiểm toán số liệu hoặc mở công cụ phát lại đồng bộ chuỗi thời gian:</p>
       <div className="button-line" style={{flexDirection:'column',alignItems:'stretch'}}>
        <Button onClick={()=>goto('report-detail')}>Xem chi tiết báo cáo kiểm toán →</Button>
        <Button kind="secondary" onClick={()=>goto('replay')}>Mở Phát lại & Thẩm định chuỗi thời gian →</Button>
        <DownloadCSV rows={REPLAY_SAMPLES} allowed={canOperate(session)} voyageId={v.id}/>
       </div>
       <div className="note" style={{marginTop:16}}>
        <b>Dữ liệu kiểm toán:</b> Số liệu của chuyến <code>V-2026-001</code> được đối chứng chuẩn xác từ chuỗi dữ liệu gốc <code>telemetry_demo.csv</code>.
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
       <Button kind="ghost" onClick={()=>goto('reports')}>← Quay lại Báo cáo hành trình</Button>
      </div>
      <span className="eyebrow">Audit Dossier / {v.id}</span>
      <h1>Chi tiết báo cáo hành trình: {v.id}</h1>
      <p>{v.name} • {v.route}</p>
     </div>
     <Pill kind="normal">Kiểm toán hoàn tất</Pill>
    </div>

    <Panel title="Thông tin hành trình kiểm toán" tag="Metadata">
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
      <Panel title="Kiểm toán động học chuyển động" tag="Số liệu gốc">
       <dl className="kv">
        <dt>Tổng số mẫu telemetry (sample_count)</dt><dd>{v.sampleCount} mẫu (chu kỳ 5s)</dd>
        <dt>Roll cực đại (|max_abs_roll_deg|)</dt><dd className={v.maxAbsRollDeg>15?'text-danger':'text-info'} style={{fontWeight:600}}>{v.maxAbsRollDeg.toFixed(2)}°</dd>
        <dt>Độ lệch bình phương trung bình (rms_roll_deg)</dt><dd className="text-info" style={{fontWeight:600}}>{v.rmsRollDeg.toFixed(2)}° (7.083967° chuẩn)</dd>
        <dt>Phân vị 95% biên độ roll (p95_abs_roll_deg)</dt><dd>{v.p95AbsRollDeg.toFixed(2)}°</dd>
        <dt>Pitch cực đại (|max_abs_pitch_deg|)</dt><dd>{v.maxAbsPitchDeg.toFixed(2)}°</dd>
        <dt>RMS Pitch (rms_pitch_deg)</dt><dd>{v.rmsPitchDeg.toFixed(2)}°</dd>
       </dl>
       <div className="note success" style={{marginTop:14}}>
        <b>✓ Dữ liệu chuẩn xác:</b> Số liệu kiểm toán trùng khớp 100% với chuỗi dữ liệu gốc <code>telemetry_demo.csv</code> và báo cáo hành trình.
       </div>
      </Panel>

      {/* MAI and Cargo Risk Evidence */}
      <Panel title="Chỉ số bất thường MAI & Bằng chứng rủi ro hàng hóa" tag="Evidence">
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
      <Panel title="Nhật ký cảnh báo hành trình" tag={`${alarms.length} sự kiện`}>
       {alarms.map(a => renderAlarm(a, true))}
      </Panel>

      {/* Export Cluster */}
      <Panel title="Xuất báo cáo & Ký số" tag="Export Cluster">
       <p className="micro">Các tùy chọn kết xuất dữ liệu và báo cáo hành trình:</p>
       <div className="button-line" style={{flexDirection:'column',alignItems:'stretch'}}>
        <DownloadCSV rows={REPLAY_SAMPLES} allowed={canOperate(session)} voyageId={v.id}/>
        <Button kind="secondary" onClick={()=>window.print()}>Xem trước / In báo cáo (HTML Print)</Button>
       </div>
       <div className="note" style={{marginTop:14}}>
        <b>Trạng thái PDF chính thức:</b><br/>
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
      <span className="eyebrow">Bộ ghi viễn trắc chuỗi thời gian / {v.id}</span>
      <h1>Phát lại & Thẩm định</h1>
      <p>Phát lại đồng bộ chuỗi thời gian chuyển động học và thẩm định cảnh báo trực ca.</p>
     </div>
     <Pill kind={playing?'normal':'caution'}>
      {playing ? `ĐANG PHÁT (×${speed})` : 'TẠM DỪNG'}
     </Pill>
    </div>

    {/* Top HUD Readout Bar */}
    <div className="metrics">
     <Metric label="Mốc thời gian" value={`T+${currentPoint.t_sim_s}s`} note={`Mẫu ${replayIndex + 1} / ${REPLAY_SAMPLES.length} (Tổng 600s)`} tone="cyan"/>
     <Metric label="Góc lắc ngang" value={format(currentPoint.roll)} note="Dao động ngang" tone={Math.abs(currentPoint.roll)>12?'red':'cyan'}/>
     <Metric label="Góc lắc dọc" value={format(currentPoint.pitch)} note="Dao động dọc" tone="amber"/>
     <Metric label="Chỉ số MAI" value={`${currentPoint.mai} / 100`} note={`Nhận dạng: ${getRFClassNameVi(currentPoint.class_rf)}`} tone={currentPoint.mai>=70?'red':currentPoint.mai>=35?'amber':'green'}/>
    </div>

    {/* 2D Vessel Visualizer Synchronized with Playhead */}
    <Panel title="Trực quan hóa thân tàu" tag="Mô hình đồng bộ">
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

    {/* Transport Deck & Time Scrubber (Directly above Waveform) */}
    <Panel title="Bàn điều khiển phát lại" tag="Điều khiển đồng bộ">
     <div style={{marginBottom:12}}>
      <label htmlFor="replay-slider" className="micro" style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
       <span>Kéo thanh thời gian</span>
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

    {/* Waveform with needle & markers */}
    <Panel title={`Đồ thị dao động theo thời gian (${v.id})`} tag="Biểu đồ chuỗi">
     <ReplayChart
      samples={REPLAY_SAMPLES}
      currentIndex={replayIndex}
      onSeek={(idx)=>setReplayIndex(idx)}
     />
    </Panel>

    {/* Watchstander Event Review Section */}
    <Panel title="Thẩm định cảnh báo bởi sĩ quan trực ca" tag="Đánh giá ca trực">
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
      <span className="eyebrow">Chẩn đoán phần cứng</span>
      <h1>Tình trạng thiết bị</h1>
      <p>Chẩn đoán vi điều khiển ESP32, cảm biến IMU MPU6050, bus I2C và hàng đợi dữ liệu.</p>
     </div>
     <Pill kind={health.healthStatus === 'HEALTHY' ? 'normal' : health.healthStatus === 'DEGRADED' ? 'caution' : 'critical'}>
      {health.healthStatus === 'HEALTHY' ? 'Sức khỏe: 100% Tốt' : health.healthStatus === 'DEGRADED' ? 'Sức khỏe: 45% Cảm biến lỗi' : 'Sức khỏe: 15% Offline'}
     </Pill>
    </div>

    {/* Callout banners */}
    {isOffline ? (
     <div className="note danger" style={{marginBottom:18}}>
      <b>Mất kết nối với thiết bị (OFFLINE):</b> Thiết bị giám sát mất kết nối MQTT (&gt;30s). Dữ liệu cảm biến không khả dụng. Hệ thống tuân thủ nguyên tắc không tự tạo dữ liệu mới để hiển thị như dữ liệu thật. Dữ liệu đang được tự động lưu vào bộ đệm Flash ngoại tuyến trên ESP32 và sẽ đồng bộ bù khi tái kết nối.
     </div>
    ) : isSensorFault ? (
     <div className="note warning" style={{marginBottom:18}}>
      <b>Lỗi giao tiếp cảm biến (SENSOR FAULT):</b> Phát hiện 3 lỗi I2C NACK với cảm biến MPU6050. Tín hiệu đo không khả dụng, hệ thống không suy diễn trạng thái NORMAL.
     </div>
    ) : (
     <div className="note success" style={{marginBottom:18}}>
      <b>Thiết bị hoạt động tốt (100% Health):</b> ESP32 kết nối ổn định qua MQTT QoS 0/1. Cảm biến MPU6050 hoạt động chuẩn xác với chu kỳ đo 5.0s.
     </div>
    )}

    {/* 4 Primary Diagnostic Metrics */}
    <div className="metrics">
     <Metric
      label="Điểm sức khỏe thiết bị"
      value={`${health.healthScore} / 100`}
      note={health.healthStatus}
      tone={health.healthScore >= 80 ? 'green' : health.healthScore >= 40 ? 'amber' : 'red'}
     />
     <Metric
      label="Trạng thái cảm biến"
      value={health.sensor}
      note={health.sensor === 'OK' ? 'MPU6050 kết nối tốt' : health.sensor === 'FAULT' ? 'Lỗi bus I2C' : 'Chưa rõ / Offline'}
      tone={health.sensor === 'OK' ? 'green' : health.sensor === 'FAULT' ? 'amber' : 'red'}
     />
     <Metric
      label="Lỗi bus I2C"
      value={String(health.i2cErrors)}
      note={health.i2cErrors > 0 ? 'NACK timeout phát hiện' : '0 lỗi bus (Chuẩn)'}
      tone={health.i2cErrors > 0 ? 'red' : 'green'}
     />
     <Metric
      label="Free Heap (ESP32)"
      value={`${health.freeHeapKb} KB`}
      note={`Tối thiểu: ${health.minFreeHeapKb} KB`}
      tone={health.freeHeapKb < 80 ? 'amber' : 'cyan'}
     />
    </div>

    {/* Secondary Metrics */}
    <div className="metrics">
     <Metric
      label="WiFi RSSI"
      value={health.rssiDbm !== null ? `${health.rssiDbm} dBm` : '—'}
      note={health.rssiDbm !== null ? 'Cường độ thu phát tốt' : 'Mất kết nối'}
      tone={health.rssiDbm !== null ? 'cyan' : 'red'}
     />
     <Metric
      label="Uptime thiết bị"
      value={`${health.uptimeMinutes} phút`}
      note={`${Math.floor(health.uptimeMinutes/60)} giờ ${health.uptimeMinutes%60} phút`}
      tone="cyan"
     />
     <Metric
      label="Bộ đệm ngoại tuyến"
      value={`${health.bufferUsed} / ${health.bufferCapacity}`}
      note={`Đang lưu: ${((health.bufferUsed / health.bufferCapacity) * 100).toFixed(1)}%`}
      tone={health.bufferUsed > 0 ? 'amber' : 'green'}
     />
     <Metric
      label="Độ trễ hàng đợi"
      value={`${health.queueLatencyMs} ms`}
      note={health.bufferStatus === 'BUFFERING' ? 'Đang lưu bù Flash' : 'Đồng bộ trực tiếp'}
      tone={health.queueLatencyMs > 100 ? 'amber' : 'green'}
     />
    </div>

    <div className="columns">
     <div>
      {/* Hardware & Bus Panel */}
      <Panel title="Chẩn đoán phần cứng & Bus truyền thông" tag="ESP32 • MPU6050">
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

      {/* Heel Zero Calibration */}
      <Panel title="Hiệu chuẩn điểm 0 độ nghiêng tĩnh" tag="Hiệu chuẩn IMU">
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
      <Panel title="Bộ đệm Flash ngoại tuyến & Đồng bộ bù" tag="Bộ nhớ Flash">
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
        <b>Nguyên tắc an toàn khi Offline:</b> Khi mất kết nối MQTT, thiết bị vẫn duy trì cảnh báo cục bộ độc lập qua còi buzzer và đèn LED trên bo mạch phần cứng, đồng thời lưu trữ chuỗi thời gian vào Flash để tự động đồng bộ bù khi mạng phục hồi.
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
       <span className="eyebrow">Giới hạn quyền truy cập</span>
       <h1>Model Monitor</h1>
       <p>Theo dõi mô hình học máy Random Forest và đối chiếu Baseline B</p>
      </div>
      <Pill kind="warning">Sĩ quan trực ca: Không có quyền truy cập</Pill>
     </div>
     <div className="note warning" style={{padding:20}}>
      <h3>Quyền truy cập bị giới hạn</h3>
      <p style={{marginTop:8}}>
       Màn hình Giám sát mô hình TinyML chuyên sâu dành riêng cho vai trò <b>Giám sát viên (Supervisor)</b> và <b>Quản trị viên (Admin)</b>.
      </p>
      <div className="button-line" style={{marginTop:16}}>
       <Button kind="primary" onClick={()=>goto('overview')}>Quay lại Trang Chủ (Overview) →</Button>
       <Button kind="secondary" onClick={logout}>Đăng xuất để đăng nhập với quyền Supervisor / Admin →</Button>
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
      <span className="eyebrow">Trí tuệ nhân tạo biên & Suy luận hàng hải</span>
      <h1>Giám sát mô hình</h1>
      <p>Theo dõi chất lượng mô hình học máy Random Forest & đối chiếu Baseline B shadow • Không suy luận AI trên Frontend</p>
     </div>
     <Pill kind="normal">DỮ LIỆU MÔ PHỎNG • ĐỒNG THUẬN {modelInfo.agreementPercent}%</Pill>
    </div>

    {/* 4 Summary Metrics */}
    <div className="metrics">
     <Metric
      label="Mô hình chính (Chính)"
      value={modelInfo.activeModelId === 'RF' ? 'Random Forest' : 'Baseline B'}
      note={modelInfo.version}
      tone="cyan"
     />
     <Metric
      label="Dự đoán hiện tại (Chính)"
      value={getRFClassNameVi(currentPredPrimary)}
      note={telemetry?.sensor_ok ? 'Từ mẫu telemetry hiện hành' : 'Cảm biến lỗi/Offline'}
      tone={currentPredPrimary === 'NORMAL' ? 'green' : currentPredPrimary === 'HIGH_ROLL' || currentPredPrimary === 'AMPLITUDE_GROWTH' ? 'red' : 'amber'}
     />
     <Metric
      label="Độ đồng thuận chung"
      value={`${modelInfo.agreementPercent}%`}
      note="Kiểm toán trên V-2026-001"
      tone="green"
     />
     <Metric
      label="Độ ổn định phân phối (PSI)"
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
      <Panel title="So sánh dự đoán mẫu hiện hành" tag="Mẫu hiện hành">
       <dl className="kv">
        <dt>Mô hình quyết định chính (Active)</dt><dd className="text-info" style={{fontWeight:600}}>{modelInfo.active}</dd>
        <dt>Dự đoán mô hình chính</dt><dd className={currentPredPrimary==='NORMAL'?'text-success':'text-warning'} style={{fontWeight:'bold'}}>{currentPredPrimary}</dd>
        <dt>Mô hình bóng (Shadow Mode)</dt><dd className="text-warning" style={{fontWeight:600}}>{modelInfo.baseline}</dd>
        <dt>Dự đoán mô hình bóng</dt><dd className={currentPredShadow==='NORMAL'?'text-success':'text-warning'} style={{fontWeight:600}}>{currentPredShadow}</dd>
        <dt>Trạng thái so sánh (Concordance)</dt>
        <dd className={agree===null?'text-muted':agree?'text-success':'text-warning'} style={{fontWeight:'bold'}}>
         {agree === null ? 'Không khả dụng' : agree ? '✓ Đồng thuận' : '⚠ Bất đồng'}
        </dd>
       </dl>
       {scenario === 'S0b' && !agree && (
        <div className="note warning" style={{marginTop:14}}>
         <b>Phát hiện bất đồng có chủ đích (Kịch bản S0b):</b> Baseline B dựa trên ngưỡng góc tức thời nên phát nhãn <code>HIGH_ROLL</code> khi có gió giật; trong khi Random Forest học đặc trưng chuỗi thời gian của quá trình tự hồi phục góc nghiêng nên nhận diện chuẩn xác nhãn <code>NORMAL</code>.
        </div>
       )}
      </Panel>

      {/* Model Registry Specs */}
      <Panel title="Thông tin đặc tả mô hình TinyML" tag="Thông số biên ESP32">
       <dl className="kv">
        <dt>Tên và phiên bản mô hình</dt><dd>{modelInfo.version}</dd>
        <dt>Kiến trúc giải thuật</dt><dd>{modelInfo.algorithm}</dd>
        <dt>Thời gian suy luận trên ESP32</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.inferenceMs} ms / mẫu</dd>
        <dt>Chiếm dụng bộ nhớ Flash</dt><dd>{modelInfo.flashKb} KB (trong phân vùng 4MB)</dd>
        <dt>Chiếm dụng bộ nhớ RAM</dt><dd>{modelInfo.ramKb} KB (trong 320KB SRAM)</dd>
        <dt>Số đặc trưng đầu vào (Input Features)</dt><dd>{modelInfo.featuresCount} đặc trưng động học (60s & 180s)</dd>
        <dt>Vectơ đặc trưng</dt><dd style={{fontSize:'0.68rem',color:'var(--telemetry-accent)',fontWeight:600}}>23 đặc trưng (8 Roll 60s, 12 Roll 180s, 3 Pitch 60s) • {CONTRACT_ID} v{CONTRACT_VERSION}</dd>
       </dl>
      </Panel>
     </div>

     <div>
      {/* Concordance Breakdown */}
      <Panel title="Tỷ lệ đồng thuận theo lớp động học" tag={`${modelInfo.agreementPercent}% Tổng thể`}>
       <p className="micro">Phân tích mức độ đồng thuận giữa Random Forest và Baseline B theo từng trạng thái biển:</p>
       <dl className="kv">
        <dt>Lớp Bình thường (Biển êm / S0)</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.concordanceBreakdown.normal}%</dd>
        <dt>Lớp Lắc ngang lớn (Biển động / S1)</dt><dd>{modelInfo.concordanceBreakdown.highRoll}%</dd>
        <dt>Lớp Nghiêng lệch kéo dài (Gió một mạn / S2)</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.concordanceBreakdown.persistentOffset}%</dd>
        <dt>Lớp Biên độ dao động tăng (Cộng hưởng / S3)</dt><dd>{modelInfo.concordanceBreakdown.amplitudeGrowth}%</dd>
       </dl>
       <small className="muted" style={{display:'block',marginTop:10}}>
        Số liệu được kiểm toán trên chuỗi thời gian 121 mẫu hành trình V-2026-001.
       </small>
      </Panel>

      {/* Data Drift & PSI */}
      <Panel title="Theo dõi độ lệch phân phối dữ liệu (PSI)" tag="Độ ổn định phân phối">
       <dl className="kv">
        <dt>Chỉ số PSI hiện tại (Population Stability Index)</dt><dd className="text-success" style={{fontWeight:'bold'}}>{modelInfo.psi}</dd>
        <dt>Đánh giá độ ổn định phân phối</dt><dd className="text-success" style={{fontWeight:600}}>{modelInfo.psiStatus}</dd>
        <dt>Mô hình Isolation Forest (Phát hiện bất thường)</dt><dd className="text-warning" style={{fontWeight:600}}>Chờ kết nối Backend TV3</dd>
        <dt>Phân tích phân phối tần suất FFT</dt><dd>Chờ dữ liệu TV2 / TV3</dd>
       </dl>
       <div className="note" style={{marginTop:14}}>
        <b>Lưu ý phạm vi hệ thống:</b> Chỉ số PSI và thuật toán Isolation Forest được tính toán định kỳ tại máy chủ Backend TV3 từ cơ sở dữ liệu lịch sử. Giao diện Frontend tuân thủ nghiêm ngặt nguyên tắc <b>không tự huấn luyện và không chạy suy luận TinyML trên trình duyệt</b>.
       </div>
      </Panel>
     </div>
    </div>

    {/* Dedicated 23 Kinematic Features Vector Panel */}
    <div style={{marginTop:16}}>
     {(() => {
      const effectiveValidCount = modelInfo.featureSummary?.validCount ?? (telemetry?.sensor_ok && scenario !== 'OFFLINE' ? TOTAL_FEATURES : 0);
      return (
       <Panel title="Danh mục 23 đặc trưng động học" tag={`${effectiveValidCount}/${TOTAL_FEATURES} VALID • v${CONTRACT_VERSION}`}>
        {/* Contract & Integrity Status Bar */}
        <div style={{display:'flex',gap:10,alignItems:'center',flexWrap:'wrap',padding:'10px 14px',background:'var(--panel-alt)',borderRadius:8,marginBottom:14,border:'1px solid var(--border-subtle)'}}>
         <span className="micro" style={{color:'var(--text-muted)'}}>
          Hợp đồng: <b style={{color:'var(--text-main)'}}>{CONTRACT_ID}</b> (v{CONTRACT_VERSION})
         </span>
         <span className="micro" style={{color:'var(--text-muted)'}}>•</span>
         <span className="micro" style={{color:'var(--text-muted)'}}>
          Tổng: <b style={{color:'var(--text-main)'}}>{TOTAL_FEATURES} đặc trưng</b>
         </span>
         <span className="micro" style={{color:'var(--text-muted)'}}>•</span>
         <span className="micro" style={{color: effectiveValidCount > 0 ? '#10B981' : '#EF4444'}}>
          Hợp lệ: <b>{effectiveValidCount}</b>
         </span>
         {modelInfo.featureSummary && modelInfo.featureSummary.missingCount > 0 && (
          <>
           <span className="micro" style={{color:'var(--text-muted)'}}>•</span>
           <span className="micro" style={{color:'#D97706'}}>
            Không khả dụng: <b>{modelInfo.featureSummary.missingCount}</b>
           </span>
          </>
         )}
         {modelInfo.featureSummary && modelInfo.featureSummary.invalidCount > 0 && (
          <>
           <span className="micro" style={{color:'var(--text-muted)'}}>•</span>
           <span className="micro" style={{color:'#EF4444'}}>
            Lỗi: <b>{modelInfo.featureSummary.invalidCount}</b>
           </span>
          </>
         )}
         <span className="micro" style={{color:'var(--text-muted)',marginLeft:'auto'}}>
          Nguồn export: <code>{CONTRACT_SOURCE_EXPORT}</code>
         </span>
        </div>

      {/* 3 Summary Group Cards */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(240px, 1fr))',gap:12,marginBottom:16}}>
       <div style={{background:'var(--panel-alt)',border:'1px solid var(--border-subtle)',borderRadius:10,padding:'12px 14px'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
         <b style={{color:'var(--telemetry-accent)',fontSize:'0.82rem'}}>Roll Ngắn hạn (60s)</b>
         <span className="pill normal" style={{padding:'2px 8px',fontSize:'0.68rem'}}>8 đặc trưng</span>
        </div>
        <p className="micro" style={{color:'var(--text-secondary)',margin:0}}>
         Động học lắc ngang ngắn hạn: RMS, STD, Mean, Peak-to-Peak, P95, Max, IQR và RMS vi phân d(roll)/dt.
        </p>
       </div>
       <div style={{background:'var(--panel-alt)',border:'1px solid var(--border-subtle)',borderRadius:10,padding:'12px 14px'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
         <b style={{color:'#10B981',fontSize:'0.82rem'}}>Roll Dài hạn & Trend (180s)</b>
         <span className="pill normal" style={{padding:'2px 8px',fontSize:'0.68rem'}}>12 đặc trưng</span>
        </div>
        <p className="micro" style={{color:'var(--text-secondary)',margin:0}}>
         Xu hướng dài hạn & chỉ dấu lệch tải (Heel offset): Mean, Median, Abs, Sign ratio, Segment STD, Shift, Early/Late RMS, Ratio, Slope, R² và P95 Slope.
        </p>
       </div>
       <div style={{background:'var(--panel-alt)',border:'1px solid var(--border-subtle)',borderRadius:10,padding:'12px 14px'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
         <b style={{color:'#D97706',fontSize:'0.82rem'}}>Pitch Ngắn hạn (60s)</b>
         <span className="pill normal" style={{padding:'2px 8px',fontSize:'0.68rem'}}>3 đặc trưng</span>
        </div>
        <p className="micro" style={{color:'var(--text-secondary)',margin:0}}>
         Động học nhồi/chúi thân tàu ngắn hạn: Pitch RMS, Pitch STD và Pitch Peak-to-Peak.
        </p>
       </div>
      </div>

      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:10,marginBottom:14}}>
       <div className="button-line" style={{margin:0}}>
        <Button kind={featureGroupFilter==='ALL'?'primary':'secondary'} onClick={()=>setFeatureGroupFilter('ALL')}>Tất cả (23)</Button>
        <Button kind={featureGroupFilter==='roll_60s'?'primary':'secondary'} onClick={()=>setFeatureGroupFilter('roll_60s')}>Roll 60s (8)</Button>
        <Button kind={featureGroupFilter==='roll_180s'?'primary':'secondary'} onClick={()=>setFeatureGroupFilter('roll_180s')}>Roll 180s (12)</Button>
        <Button kind={featureGroupFilter==='pitch_60s'?'primary':'secondary'} onClick={()=>setFeatureGroupFilter('pitch_60s')}>Pitch 60s (3)</Button>
       </div>
       <div className="button-line" style={{margin:0}}>
        <Button kind="secondary" onClick={()=>downloadFeaturesCSV(modelInfo.featureItems || [])} title="Xuất toàn bộ 23 đặc trưng dạng CSV theo đúng thứ tự hợp đồng">
         Xuất CSV 23 Đặc trưng (v{CONTRACT_VERSION})
        </Button>
       </div>
      </div>
      <div style={{overflowX:'auto'}}>
       <table style={{width:'100%',borderCollapse:'collapse',fontSize:'0.76rem'}}>
        <thead>
         <tr style={{background:'var(--panel-alt)',borderBottom:'1px solid var(--border-subtle)',color:'var(--text-main)',textAlign:'left'}}>
          <th style={{padding:'8px 10px',width:'36px',fontVariantNumeric:'tabular-nums'}}>#</th>
          <th style={{padding:'8px 10px'}}>Tên đặc trưng & Ký hiệu</th>
          <th style={{padding:'8px 10px'}}>Nhóm & Cửa sổ</th>
          <th style={{padding:'8px 10px',textAlign:'right',fontVariantNumeric:'tabular-nums'}}>Giá trị mẫu (CSV)</th>
          <th style={{padding:'8px 10px',textAlign:'center'}}>Đơn vị</th>
          <th style={{padding:'8px 10px',textAlign:'center'}}>Trạng thái</th>
          <th style={{padding:'8px 10px'}}>Ý nghĩa động học hàng hải</th>
         </tr>
        </thead>
        <tbody>
         {(modelInfo.featureItems || []).filter(f => featureGroupFilter === 'ALL' || f.group === featureGroupFilter).map(f => (
          <tr key={f.name} style={{borderBottom:'1px solid var(--border-subtle)'}}>
           <td style={{padding:'8px 10px',color:'var(--text-muted)',fontVariantNumeric:'tabular-nums'}}>{f.index + 1}</td>
           <td style={{padding:'8px 10px',color:'var(--text-main)'}}>
            <div style={{fontWeight:600,fontSize:'0.78rem'}}>{f.displayName || FEATURE_NAMES_VI[f.name]?.titleVi || f.name}</div>
            <code style={{fontSize:'0.7rem',color:'var(--text-muted)'}}>{f.name}</code>
           </td>
           <td style={{padding:'8px 10px'}}>
            <span style={{
             display:'inline-block',padding:'2px 8px',borderRadius:4,fontSize:'0.68rem',fontWeight:500,
             background: f.group==='roll_60s'?'rgba(2,132,199,0.12)':f.group==='roll_180s'?'rgba(16,185,129,0.12)':'rgba(245,158,11,0.12)',
             color: f.group==='roll_60s'?'var(--telemetry-accent)':f.group==='roll_180s'?'#10B981':'#D97706'
            }}>
             {f.group==='roll_60s'?'Roll 60s (Ngắn hạn)':f.group==='roll_180s'?'Roll 180s (Dài hạn/Trend)':'Pitch 60s (Nhồi/chúi)'}
            </span>
           </td>
           <td style={{padding:'8px 10px',textAlign:'right',fontVariantNumeric:'tabular-nums',fontWeight:600,color:'var(--text-main)'}}>
            {f.value !== null && f.value !== undefined ? f.value.toFixed(4) : 'N/A'}
           </td>
           <td style={{padding:'8px 10px',textAlign:'center',color:'var(--text-secondary)',fontSize:'0.72rem'}}>
            <code style={{padding:'1px 4px'}}>{f.unit}</code>
           </td>
           <td style={{padding:'8px 10px',textAlign:'center'}}>
            <span className={`pill ${f.status === 'VALID' ? 'normal' : f.status === 'WARNING' ? 'caution' : f.status === 'NOT_APPLICABLE' ? 'neutral' : 'critical'}`} style={{padding:'2px 8px',fontSize:'0.68rem',fontWeight:700}}>
             {f.status}
            </span>
           </td>
           <td style={{padding:'8px 10px',color:'var(--text-secondary)',fontSize:'0.73rem',lineHeight:1.4}}>
            <div>{f.description}</div>
            {f.reason && (
             <div className="micro" style={{color:'var(--text-muted)',fontStyle:'italic',marginTop:2}}>
              {f.reason}
             </div>
            )}
           </td>
          </tr>
         ))}
        </tbody>
       </table>
      </div>
     </Panel>
    );})()}
   </div>
   </>;
  }
  case 'more':return <><header className="page-heading"><h1>Chức năng khác</h1><p>Các chức năng hệ thống bổ trợ và tài khoản người dùng.</p></header>
   <Panel title="Giao diện hiển thị" tag={theme==='light'?'Giao diện Sáng':'Giao diện Tối'}>
    <p className="micro">Tùy chọn phong cách màu sắc giao diện hệ thống:</p>
    <div className="button-line">
     <Button kind={theme==='light'?'primary':'secondary'} onClick={()=>setTheme('light')}>☀ Giao diện Sáng</Button>
     <Button kind={theme==='dark'?'primary':'secondary'} onClick={()=>setTheme('dark')}>🌙 Giao diện Tối</Button>
    </div>
   </Panel>
   <Panel title="Công cụ giám sát"><div className="more-list">{NAV.filter(n=>['control','replay','health','model'].includes(n.key)).map(n=><button type="button" key={n.key} onClick={()=>goto(n.key)}>{n.label}<span>→</span></button>)}</div></Panel><Panel title="Tài khoản"><dl className="kv"><dt>Tên đăng nhập</dt><dd>{session?.username}</dd><dt>Vai trò</dt><dd>{getRoleNameVi(session?.role)} ({session?.role})</dd><dt>Chế độ</dt><dd>Mô phỏng (DEMO AUTH)</dd></dl><Button kind="danger" onClick={logout}>Đăng xuất</Button></Panel></>;
  }
 };
  if (!session) {
    return (
      <div className="auth-layout">
        <div className="auth-brand">
          <span style={{display:'none'}} aria-hidden="true" className="reticle-tl reticle-br">ACCESS CONTROL LEVEL 1 • RSA-4096 BRIDGE HARDWARE KEY ENCRYPTED • Bảng 3.1</span>
          <div className="brand-mark">≋</div>
          <span className="eyebrow">IoT • Edge AI • An toàn Hàng hải</span>
          <h1>Smart Vessel<br/>Motion Guard</h1>
          <p>Hệ thống giám sát động học chuyển động tàu thời gian thực và phát hiện bất thường TinyML trên ESP32.</p>
          <span className="stamp" style={{marginTop: 18}}>Bàn điều khiển Hàng hải • An toàn Hàng hải</span>
        </div>

        {authView === 'login' && (
          <form className="auth-card" onSubmit={submitLogin}>


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
                Key Recovery
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



            {loginError && <div className="error" role="alert">{loginError}</div>}

            <button className="btn primary full" type="submit" disabled={authLoading}>
              {authLoading ? 'Đang xác thực...' : 'Đăng nhập hệ thống →'}
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
              <strong>Vai trò hệ thống: Operator (Sĩ quan trực ca)</strong>
              <p>
                <b>Phân quyền tài khoản:</b> Người dùng tự đăng ký có quyền Sĩ quan trực ca (Operator). Quyền Supervisor (Giám sát bờ) và Admin (Quản trị viên) do quản trị hệ thống phê duyệt và cấp quyền riêng.
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
                Xác nhận đăng ký →
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
              <span className="auth-badge">Key Recovery Protocol</span>
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
                Gửi yêu cầu đặt lại mật mã →
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
 return <div className="app-layout"><aside className="sidebar"><div className="brand"><div className="brand-mark">≋</div><div><strong>Smart Vessel</strong><small>Motion Guard</small></div></div><span className="nav-label">Vận hành</span><nav aria-label="Menu chính">{NAV.map(n=>{const isRestricted=n.key==='model'&&session.role==='Operator';return <button key={n.key} className={page===n.key||(page==='report-detail'&&n.key==='reports')?'active':''} onClick={()=>goto(n.key)} title={isRestricted?'Chỉ dành cho Supervisor / Admin':undefined}><span style={{display:'inline-flex',alignItems:'center',gap:6}}>{n.label}{isRestricted&&<span style={{fontSize:'0.65rem',opacity:0.75}}>🔒</span>}</span></button>})}</nav><div className="sidebar-bottom"><small>{getRoleNameVi(session.role)} · {session.username}</small><Button kind="ghost" onClick={logout}>Đăng xuất</Button></div></aside><div className="workspace"><div className="topbar"><div><b>SV<span>MG</span></b><span className="topbar-name">Tàu MV SVMG-01</span></div><div className="topbar-right"><div className="theme-selector" role="group" aria-label="Giao diện hiển thị"><button type="button" className={`theme-opt-btn ${theme==='light'?'active':''}`} onClick={()=>setTheme('light')} title="Giao diện Sáng (Mặc định)">☀ Sáng</button><button type="button" className={`theme-opt-btn ${theme==='dark'?'active':''}`} onClick={()=>setTheme('dark')} title="Giao diện Tối">🌙 Tối</button></div><Pill kind="caution">Dữ liệu mô phỏng</Pill><span className="micro">{getRoleNameVi(session.role)} · {session.username}</span></div></div>{notice&&<div className="toast" role="status"><span>{notice}</span><button onClick={()=>setNotice('')} aria-label="Đóng thông báo">×</button></div>}<main className="main"><div key={page} className="page-transition">{renderPage()}</div><div className="disclaimer">SMART VESSEL MOTION GUARD • PHIÊN BẢN MÔ PHỎNG GIAO DIỆN TV4 • Không thay thế hệ thống cảnh báo hàng hải chính thức</div></main><nav className="mobile-nav" aria-label="Điều hướng điện thoại">{([{key:'overview',label:'Tổng quan'},{key:'motion',label:'Chuyển động'},{key:'alarms',label:'Cảnh báo'},{key:'reports',label:'Báo cáo'},{key:'more',label:'Thêm'}] as const).map(n=><button key={n.key} className={page===n.key||(n.key==='reports'&&page==='report-detail')||(n.key==='more'&&['control','replay','health','model'].includes(page))?'active':''} onClick={()=>goto(n.key)}>{n.label}</button>)}</nav></div></div>
}
