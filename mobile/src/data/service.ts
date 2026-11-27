/**
 * MOCK data provider (offline demo accounts + generated telemetry).
 * Dữ liệu thật (LIVE) không đi qua file này: xem liveApi.ts / liveMapper.ts / useLiveBackend.ts,
 * được App.tsx chọn khi đăng nhập ở chế độ LIVE. LIVE không bao giờ rơi về MOCK khi lỗi.
 */
import { Scenario, Session, Telemetry } from '../types/domain';
import { createTelemetry, mockLogin, mockRegister, mockForgotPassword } from './mock';
export interface DataService {
  readonly name: 'mock' | 'live';
  authenticateDemo(username:string,password:string): Session|null;
  registerDemo(username:string,password:string,displayName:string): { success: boolean; message: string; error?: string };
  forgotPasswordDemo(identifier:string): { success: boolean; message: string; error?: string };
  getDemoTelemetry(scenario:Scenario,tick:number):Telemetry;
}
export const MockDataService:DataService={
  name:'mock',
  authenticateDemo:mockLogin,
  registerDemo:mockRegister,
  forgotPasswordDemo:mockForgotPassword,
  getDemoTelemetry:createTelemetry
};
