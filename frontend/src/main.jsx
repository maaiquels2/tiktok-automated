import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import NewVersionBanner from './versionCheck.jsx';
import './styles.css';
import './design-fixes.css';
import './redesign.css';
import { injectSpeedInsights } from '@vercel/speed-insights';

// Mede LCP/INP/CLS reais no celular (so em producao; precisa estar ligado no painel da Vercel).
if (import.meta.env.PROD) injectSpeedInsights();
createRoot(document.getElementById('root')).render(<React.StrictMode><App/><NewVersionBanner/></React.StrictMode>);
