import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Points from './pages/Points';
import Barista from './pages/Barista';
import Products from './pages/Products';
import CrmAnalytics from './pages/CrmAnalytics';
import MenuConstructor from './pages/MenuConstructor';

function NavItem({ to, icon, label, onClick }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <li onClick={onClick}>
    <Link to={to} style={{
      display: 'block', color: isActive ? '#3c5043' : 'white',
      backgroundColor: isActive ? 'rgba(255, 255, 255, 0.8)' : 'transparent',
          textDecoration: 'none', fontSize: '1.1rem', padding: '0.75rem 1rem',
          borderRadius: '8px', fontWeight: isActive ? 'bold' : 'normal', transition: 'all 0.2s'
    }}>
    {icon} {label}
    </Link>
    </li>
  );
}

function App() {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [limits, setLimits] = useState({ min: '', max: '' });
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  useEffect(() => {
    fetch('/api/dashboard/date_limits')
    .then(res => res.json())
    .then(data => {
      if (!data.error && data.min_date && data.max_date) {
        setLimits({ min: data.min_date, max: data.max_date });
        const maxDateObj = new Date(data.max_date);
        const thirtyDaysAgo = new Date(maxDateObj.setDate(maxDateObj.getDate() - 30)).toISOString().split('T')[0];

        setEndDate(data.max_date);
        setStartDate(thirtyDaysAgo < data.min_date ? data.min_date : thirtyDaysAgo);
      }
    });
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('admin_token');
    if (token) {
      localStorage.setItem('admin_token', token);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handleDateChange = (type, value) => {
    let newVal = value;
    if (limits.min && newVal < limits.min) newVal = limits.min;
    if (limits.max && newVal > limits.max) newVal = limits.max;

    if (type === 'start') setStartDate(newVal);
    else setEndDate(newVal);
  };

    const inputStyle = {
      padding: '0.5rem', borderRadius: '6px', border: '1px solid #9ca99d',
      color: '#3c5043', backgroundColor: 'white', outline: 'none', fontFamily: 'inherit'
    };

    return (
      <BrowserRouter>
      <div className="app-layout" style={{ fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif' }}>

      {/* Мобильная шапка (Бургер слева, Логотип и Текст справа) */}
      <div className="mobile-header">
      <button className="burger-btn" onClick={() => setIsMenuOpen(true)}>☰</button>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <img src="/logo.svg" alt="Логотип" style={{ height: '32px', objectFit: 'contain' }} />
      <h2 style={{ margin: 0, fontSize: '1.2rem', letterSpacing: '2px', fontWeight: 'normal' }}>АНКЛАВ</h2>
      </div>
      </div>

      {/* Сайдбар (ПК версия) */}
      <nav className={`sidebar ${isMenuOpen ? 'open' : ''}`} style={{ background: '#9ca99d', color: 'white', padding: '2rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '15px', marginBottom: '2rem' }}>
      <img src="/logo.svg" alt="Логотип" style={{ height: '55px', objectFit: 'contain' }} />
      <div style={{ textAlign: 'left' }}>
      <h2 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 'normal', letterSpacing: '2px' }}>АНКЛАВ</h2>
      <p style={{ margin: 0, fontSize: '0.8rem', letterSpacing: '1px', opacity: 0.9 }}>КОФЕ</p>
      </div>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <NavItem to="/" icon="📊" label="Сводка" onClick={() => setIsMenuOpen(false)} />
      <NavItem to="/points" icon="🏪" label="Точки" onClick={() => setIsMenuOpen(false)} />
      <NavItem to="/barista" icon="🧑‍🍳" label="Бариста" onClick={() => setIsMenuOpen(false)} />
      <NavItem to="/products" icon="🥐" label="Товары" onClick={() => setIsMenuOpen(false)} />
      <NavItem to="/crm" icon="👥" label="CRM" onClick={() => setIsMenuOpen(false)} />
      <NavItem to="/menu-editor" icon="📋" label="Меню" onClick={() => setIsMenuOpen(false)} />
      </ul>
      </nav>

      {/* Оверлей для затемнения фона на мобильных */}
      <div className={`overlay ${isMenuOpen ? 'show' : ''}`} onClick={() => setIsMenuOpen(false)}></div>

      {/* Основной контент */}
      <div className="main-content" style={{ background: '#f4f6f4' }}>
      <header style={{ padding: '1.5rem 2rem', background: 'white', borderBottom: '1px solid rgba(156, 169, 157, 0.2)', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
      <span style={{ color: '#3c5043', fontWeight: 'bold' }}>Период аналитики:</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <input type="date" value={startDate} min={limits.min} max={limits.max} onChange={(e) => handleDateChange('start', e.target.value)} style={inputStyle} />
      <span style={{ color: '#9ca99d' }}>—</span>
      <input type="date" value={endDate} min={limits.min} max={limits.max} onChange={(e) => handleDateChange('end', e.target.value)} style={inputStyle} />
      </div>
      </header>

      <main style={{ padding: '2rem', color: '#3c5043' }}>
      {startDate && endDate ? (
        <Routes>
        <Route path="/" element={<Dashboard startDate={startDate} endDate={endDate} />} />
        <Route path="/points" element={<Points startDate={startDate} endDate={endDate} />} />
        <Route path="/barista" element={<Barista startDate={startDate} endDate={endDate} />} />
        <Route path="/products" element={<Products startDate={startDate} endDate={endDate} />} />
        <Route path="/crm" element={<CrmAnalytics startDate={startDate} endDate={endDate} />} />
        <Route path="/menu-editor" element={<MenuConstructor />} />
        </Routes>
      ) : <p>Загрузка календаря...</p>}
      </main>
      </div>
      </div>
      </BrowserRouter>
    );
}

export default App;
