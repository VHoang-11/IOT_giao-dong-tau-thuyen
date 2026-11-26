// Thành phần giao diện dùng chung cho cả MOCK và LIVE (tách nguyên văn từ App.tsx, không đổi markup/class).
import type {CSSProperties,ReactNode} from 'react';

export function Pill({children,kind='neutral'}:{children:ReactNode;kind?:string}){return <span className={`pill ${kind.toLowerCase()}`}>{children}</span>}
export function Panel({title,tag,children,footer}:{title:string;tag?:string;children:ReactNode;footer?:ReactNode}){return <section className="panel"><header className="panel-head"><h3>{title}</h3>{tag&&<span className="micro">{tag}</span>}</header>{children}{footer&&<footer className="panel-foot">{footer}</footer>}</section>}
export function Metric({label,value,note,tone='cyan',className}:{label:string;value:string;note?:string;tone?:string;className?:string}){return <div className={`metric ${className||''}`}><span className="label">{label}</span><strong className={`metric-value ${tone}`}>{value}</strong>{note&&<span className="micro">{note}</span>}</div>}
export function Button({children,onClick,disabled=false,kind='primary',title,style}:{children:ReactNode;onClick?:()=>void;disabled?:boolean;kind?:string;title?:string;style?:CSSProperties}){return <button type="button" className={`btn ${kind}`} style={style} onClick={onClick} disabled={disabled} title={title}>{children}</button>}
