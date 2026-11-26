import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
// Dev: /api đi qua proxy tới FastAPI (giống Nginx trong Docker) để chế độ LIVE dùng cùng origin, không cần CORS.
// Đổi đích bằng biến môi trường SVMG_API_TARGET (mặc định http://localhost:8000).
export default defineConfig(({mode})=>{
  const apiTarget=loadEnv(mode,'.','').SVMG_API_TARGET||'http://localhost:8000';
  return {plugins:[react()],server:{port:5173,proxy:{'/api':{target:apiTarget,changeOrigin:true}}}};
});
