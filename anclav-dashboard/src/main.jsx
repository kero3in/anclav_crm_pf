import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const WebApp = window.Telegram?.WebApp;
if (WebApp) {
  WebApp.ready();
  WebApp.expand();
}

const originalFetch = window.fetch;
window.fetch = async (url, options = {}) => {
  if (url.startsWith('/api/')) {
    const adminToken = localStorage.getItem('admin_token');
    let authHeader = '';

    if (adminToken) {
      authHeader = `Bearer ${adminToken}`;
    }
    else if (window.Telegram?.WebApp?.initData) {
      authHeader = `tma ${window.Telegram.WebApp.initData}`;
    }

    options.headers = {
      ...options.headers,
      'Authorization': authHeader
    };
  }
  return originalFetch(url, options);
};

createRoot(document.getElementById('root')).render(
  <StrictMode>
  <App />
  </StrictMode>,
)
