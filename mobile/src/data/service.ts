/**
 * Separation boundary between screens and data providers.
 * The UI uses AppData/AppActions, NOT network APIs. TV3 API/WS contract is pending.
 * This scaffold currently runs the MockDataService only.
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
// Deliberate fail-closed placeholder: no invented TV3 endpoints and no false success.
export const LiveDataService:DataService={
 name:'live',
 authenticateDemo(){throw new Error('NOT_CONFIGURED: Backend TV3 authentication contract unavailable')},
 registerDemo(){throw new Error('NOT_CONFIGURED: Backend TV3 authentication contract unavailable')},
 forgotPasswordDemo(){throw new Error('NOT_CONFIGURED: Backend TV3 authentication contract unavailable')},
 getDemoTelemetry(){throw new Error('NOT_CONFIGURED: Backend TV3 telemetry/WebSocket contract unavailable')}
};
