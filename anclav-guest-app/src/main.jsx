import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

const WebApp = window.Telegram.WebApp;
// Инициализируем Telegram Web App
WebApp.ready();
WebApp.expand(); // Разворачиваем на всю высоту экрана

// Устанавливаем цвета под тему приложения
WebApp.setHeaderColor('#f4f6f4');
WebApp.setBackgroundColor('#f4f6f4');

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
  <App />
  </React.StrictMode>,
)
