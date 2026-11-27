// Lớp dữ liệu LIVE: polling các endpoint GET thật của FastAPI. Không bao giờ thay dữ liệu lỗi bằng MOCK.
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {ApiError,apiRequest} from '../api';
import type {AlarmOut,AlarmStats,CargoOut,DeviceHealthSummary,DeviceOut,LiveTelemetry} from '../api';

export interface Resource<T>{data:T|null;error:string;status:number|null;loading:boolean;updatedAt:number|null;reload:()=>void}

/** GET định kỳ một endpoint. path=null → không gọi. 401 → onUnauthorized (đăng xuất), không lặp lại. */
export function useResource<T>(token:string|null,path:string|null,intervalMs:number,onUnauthorized:()=>void):Resource<T>{
 const [data,setData]=useState<T|null>(null);
 const [error,setError]=useState('');
 const [status,setStatus]=useState<number|null>(null);
 const [loading,setLoading]=useState(false);
 const [updatedAt,setUpdatedAt]=useState<number|null>(null);
 const [nonce,setNonce]=useState(0);
 const unauthorized=useRef(onUnauthorized);
 unauthorized.current=onUnauthorized;
 useEffect(()=>{
  setData(null);setError('');setStatus(null);setUpdatedAt(null);
  if(!token||!path){setLoading(false);return;}
  let cancelled=false,pending=false;
  const load=async()=>{
   if(pending)return;
   pending=true;
   try{
    const d=await apiRequest<T>(token,path);
    if(!cancelled){setData(d);setError('');setStatus(200);setUpdatedAt(Date.now());}
   }catch(e){
    if(cancelled)return;
    const code=e instanceof ApiError?e.status:0;
    if(code===401){cancelled=true;unauthorized.current();return;}
    setStatus(code);setError(e instanceof Error?e.message:'Lỗi không xác định');
   }finally{
    pending=false;
    if(!cancelled)setLoading(false);
   }
  };
  setLoading(true);
  void load();
  const id=intervalMs>0?window.setInterval(()=>{void load();},intervalMs):undefined;
  return()=>{cancelled=true;if(id!==undefined)window.clearInterval(id);};
 },[token,path,intervalMs,nonce]);
 const reload=useCallback(()=>setNonce(n=>n+1),[]);
 return {data,error,status,loading,updatedAt,reload};
}

export function useNow(intervalMs=1000):number{
 const [now,setNow]=useState(Date.now());
 useEffect(()=>{const id=window.setInterval(()=>setNow(Date.now()),intervalMs);return()=>window.clearInterval(id);},[intervalMs]);
 return now;
}

/** ISO từ backend có múi giờ (UTCDateTime); nếu thiếu thì coi là UTC để tuổi dữ liệu không lệch theo múi giờ trình duyệt. */
export function parseTime(iso?:string|null):number{
 if(!iso)return NaN;
 return Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso)?iso:`${iso}Z`);
}

export type LinkState='API_ERROR'|'NO_DATA'|'STALE'|'SENSOR_FAULT'|'ONLINE';
export interface LinkInfo{state:LinkState;label:string;kind:string;ageS:number|null;staleAfterS:number;latest:LiveTelemetry|null;fresh:LiveTelemetry|null}

/** Phân biệt mất kết nối (Backend lỗi / thiết bị im lặng) với lỗi cảm biến (dữ liệu mới nhưng sensor_ok=false).
 *  Ngưỡng cũ = max(30 s, 3 × chu kỳ gửi trung vị quan sát được), để không gắn nhãn cũ sai khi report_interval lớn. */
export function linkInfo(rows:LiveTelemetry[]|null,apiError:string,healthStale:boolean|null,now:number):LinkInfo{
 const latest=rows&&rows.length?rows[0]:null;
 const gaps:number[]=[];
 for(let i=0;rows&&i<Math.min(rows.length-1,20);i++){
  if(rows[i].boot_id!==rows[i+1].boot_id)break;
  const g=(parseTime(rows[i].server_rx_time)-parseTime(rows[i+1].server_rx_time))/1000;
  if(Number.isFinite(g)&&g>0)gaps.push(g);
 }
 gaps.sort((a,b)=>a-b);
 const staleAfterS=Math.max(30,3*(gaps.length?gaps[Math.floor(gaps.length/2)]:0));
 const t=parseTime(latest?.server_rx_time);
 const ageS=Number.isFinite(t)?Math.max(0,Math.round((now-t)/1000)):null;
 const base={ageS,staleAfterS,latest};
 if(apiError)return {...base,state:'API_ERROR',label:'MẤT KẾT NỐI BACKEND',kind:'critical',fresh:null};
 if(!latest)return {...base,state:'NO_DATA',label:'CHƯA CÓ TELEMETRY',kind:'fault',fresh:null};
 if(ageS===null||ageS>staleAfterS||healthStale===true)return {...base,state:'STALE',label:`THIẾT BỊ OFFLINE / DỮ LIỆU CŨ (${ageS??'?'}s)`,kind:'critical',fresh:null};
 if(!latest.sensor_ok)return {...base,state:'SENSOR_FAULT',label:'LỖI CẢM BIẾN (sensor_ok=false)',kind:'fault',fresh:latest};
 return {...base,state:'ONLINE',label:'● TRỰC TUYẾN (LIVE)',kind:'normal',fresh:latest};
}

export type CargoState='NO_NODE'|'API_ERROR'|'NO_DATA'|'STALE'|'SENSOR_FAULT'|'ONLINE';
export interface CargoInfo{state:CargoState;label:string;kind:string;ageS:number|null;staleAfterS:number;node:DeviceOut|null;latest:CargoOut|null;fresh:CargoOut|null}

/** Trạng thái RIÊNG của Cargo Node (ESP32 thứ 2): độc lập với kết nối của tàu chính.
 *  Dữ liệu cũ/offline → fresh=null, không hiển thị số cuối như thời gian thực. Lỗi DHT22 (sensor_ok=false) vẫn giữ mực nước (chiết áp) nhưng nhiệt độ/độ ẩm là null. */
export function cargoInfo(rows:CargoOut[]|null,apiError:string,node:DeviceOut|null,healthStale:boolean|null,now:number):CargoInfo{
 const latest=rows&&rows.length?rows[0]:null;
 const gaps:number[]=[];
 for(let i=0;rows&&i<Math.min(rows.length-1,20);i++){
  if(rows[i].device_id!==rows[i+1].device_id||rows[i].boot_id!==rows[i+1].boot_id)continue;
  const g=(parseTime(rows[i].server_rx_time)-parseTime(rows[i+1].server_rx_time))/1000;
  if(Number.isFinite(g)&&g>0)gaps.push(g);
 }
 gaps.sort((a,b)=>a-b);
 const staleAfterS=Math.max(30,3*(gaps.length?gaps[Math.floor(gaps.length/2)]:0));
 const t=parseTime(latest?.server_rx_time);
 const ageS=Number.isFinite(t)?Math.max(0,Math.round((now-t)/1000)):null;
 const base={ageS,staleAfterS,node,latest};
 if(apiError)return {...base,state:'API_ERROR',label:'MẤT KẾT NỐI BACKEND (HẦM HÀNG)',kind:'critical',fresh:null};
 if(!node)return {...base,state:'NO_NODE',label:'CHƯA GẮN CARGO NODE',kind:'neutral',fresh:null};
 if(!latest)return {...base,state:'NO_DATA',label:'CHƯA CÓ DỮ LIỆU HẦM HÀNG',kind:'fault',fresh:null};
 if(ageS===null||ageS>staleAfterS||healthStale===true)return {...base,state:'STALE',label:`CARGO NODE OFFLINE / DỮ LIỆU CŨ (${ageS??'?'}s)`,kind:'critical',fresh:null};
 if(!latest.sensor_ok)return {...base,state:'SENSOR_FAULT',label:'LỖI DHT22 (sensor_ok=false)',kind:'fault',fresh:latest};
 return {...base,state:'ONLINE',label:'● CARGO NODE TRỰC TUYẾN',kind:'normal',fresh:latest};
}

/** Tàu chính = thiết bị KHÔNG phải Cargo Node. */
export const isMotionNode=(d:DeviceOut)=>d.node_type!=='CARGO';

export interface LiveCore{
 cargo:Resource<CargoOut[]>;cargoLink:CargoInfo;
 devices:Resource<DeviceOut[]>;telemetry:Resource<LiveTelemetry[]>;alarms:Resource<AlarmOut[]>;alarmStats:Resource<AlarmStats>;
 health:Resource<DeviceHealthSummary[]>;deviceId:string|null;link:LinkInfo;now:number;reloadAll:()=>void;
}

/** Dữ liệu dùng chung mọi màn hình LIVE (đặt ở App để không mất khi đổi trang). token=null → không gọi API (chế độ MOCK). */
export function useLiveCore(token:string|null,selectedDevice:string|null,onUnauthorized:()=>void):LiveCore{
 const devices=useResource<DeviceOut[]>(token,'/api/v1/devices',30000,onUnauthorized);
 const deviceId=useMemo(()=>{
  const list=(devices.data??[]).filter(isMotionNode);   // Cargo Node không bao giờ là "tàu chính"
  if(selectedDevice&&list.some(d=>d.device_id===selectedDevice))return selectedDevice;
  const sorted=[...list].sort((a,b)=>(parseTime(b.last_seen)||0)-(parseTime(a.last_seen)||0));
  return sorted[0]?.device_id??null;
 },[devices.data,selectedDevice]);
 const enc=deviceId?encodeURIComponent(deviceId):null;
 const telemetry=useResource<LiveTelemetry[]>(token,enc?`/api/v1/devices/${enc}/telemetry?limit=120`:null,5000,onUnauthorized);
 const alarms=useResource<AlarmOut[]>(token,enc?`/api/v1/alarms?device_id=${enc}&limit=100`:null,5000,onUnauthorized);
 const alarmStats=useResource<AlarmStats>(token,enc?`/api/v1/alarms/stats?device_id=${enc}`:null,10000,onUnauthorized);
 const cargo=useResource<CargoOut[]>(token,enc?`/api/v1/devices/${enc}/cargo?limit=60`:null,5000,onUnauthorized);
 const health=useResource<DeviceHealthSummary[]>(token,token?'/api/v1/health/devices':null,10000,onUnauthorized);
 const now=useNow(1000);
 const healthStale=health.data?.find(h=>h.device_id===deviceId)?.stale??null;
 const link=linkInfo(telemetry.data,telemetry.error,healthStale,now);
 const cargoNode=(devices.data??[]).find(d=>d.node_type==='CARGO'&&d.parent_device_id===deviceId)??null;
 const cargoHealthStale=cargoNode?health.data?.find(h=>h.device_id===cargoNode.device_id)?.stale??null:null;
 const cargoLink=cargoInfo(cargo.data,cargo.error,cargoNode,cargoHealthStale,now);
 const reloadAll=useCallback(()=>{telemetry.reload();alarms.reload();alarmStats.reload();health.reload();cargo.reload();},[telemetry.reload,alarms.reload,alarmStats.reload,health.reload,cargo.reload]);
 return {devices,telemetry,alarms,alarmStats,health,cargo,cargoLink,deviceId,link,now,reloadAll};
}
