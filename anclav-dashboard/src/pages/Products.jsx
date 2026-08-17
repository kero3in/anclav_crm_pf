import { useState, useEffect } from 'react';
import { Chart, Doughnut } from 'react-chartjs-2';

const TERMINAL_NAMES = {
    '': 'Все точки',
    '1010625022006769': 'Точка №1 (ул. Калининградская, 1)',
    '1010977707053285': 'Точка №2 (ул. Ленина, 18)'
};

export default function Products({ startDate, endDate }) {
    const [selectedTerminal, setSelectedTerminal] = useState('');
    const [categories, setCategories] = useState(null);
    const [abcData, setAbcData] = useState(null);
    const [basketData, setBasketData] = useState(null);

    // Состояния для поиска связок (Cross-Sell)
    const [searchTerm, setSearchTerm] = useState('');
    const [crossSellData, setCrossSellData] = useState(null);
    const [isSearching, setIsSearching] = useState(false);

    useEffect(() => {
        const terminalQuery = selectedTerminal ? `&terminal_id=${selectedTerminal}` : '';
        const queryParams = `?start_date=${startDate}&end_date=${endDate}${terminalQuery}`;

        fetch(`/api/dashboard/categories${queryParams}`).then(res => res.json()).then(data => {
            if (!data.error && Array.isArray(data)) {
                setCategories({
                    labels: data.map(d => d.category),
                              datasets: [{ data: data.map(d => d.revenue), backgroundColor: ['#3c5043', '#9ca99d', '#d5dbd6', '#e0b896', '#8a9a8c', '#5a7062'], borderWidth: 0 }]
                });
            }
        });

        fetch(`/api/dashboard/abc${queryParams}`).then(res => res.json()).then(data => {
            if (!data.error && Array.isArray(data)) {
                setAbcData({
                    labels: data.map(d => d.item),
                           datasets: [
                               { type: 'line', label: 'Кумулятивная доля (%)', data: data.map(d => d.cum_percent), borderColor: '#e74c3c', backgroundColor: '#e74c3c', borderWidth: 2, tension: 0.3, yAxisID: 'y1' },
                           { type: 'bar', label: 'Выручка (₽)', data: data.map(d => d.revenue), backgroundColor: '#9ca99d', yAxisID: 'y' }
                           ]
                });
            }
        });

        fetch(`/api/dashboard/basket${queryParams}`).then(res => res.json()).then(data => {
            if (!data.error && Array.isArray(data)) setBasketData(data);
        });

            // Сброс результатов поиска при смене дат или точек
            if (searchTerm) {
                handleCrossSellSearch();
            }

    }, [startDate, endDate, selectedTerminal]);

    const handleCrossSellSearch = () => {
        if (!searchTerm.trim()) return;
        setIsSearching(true);
        const terminalQuery = selectedTerminal ? `&terminal_id=${selectedTerminal}` : '';
        const queryParams = `?start_date=${startDate}&end_date=${endDate}${terminalQuery}&item_name=${encodeURIComponent(searchTerm)}`;

        fetch(`/api/dashboard/cross_sell${queryParams}`)
        .then(res => res.json())
        .then(data => {
            if (!data.error) setCrossSellData(data);
            setIsSearching(false);
        })
        .catch(() => setIsSearching(false));
    };

    const cardStyle = { background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px rgba(60, 80, 67, 0.05)', border: '1px solid rgba(156, 169, 157, 0.2)' };
    const titleStyle = { margin: '0 0 1.5rem 0', color: '#9ca99d', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' };

    return (
        <div>
        <h2 style={{ marginBottom: '1rem', fontWeight: 'normal', letterSpacing: '1px' }}>ТОВАРНАЯ АНАЛИТИКА</h2>

        {/* Фильтр по точкам */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
        {Object.entries(TERMINAL_NAMES).map(([id, name]) => (
            <button
            key={id}
            onClick={() => setSelectedTerminal(id)}
            style={{
                padding: '0.8rem 1.5rem', cursor: 'pointer', borderRadius: '8px', fontWeight: 'bold', border: 'none',
                background: selectedTerminal === id ? '#3c5043' : 'white',
                color: selectedTerminal === id ? 'white' : '#3c5043',
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)', transition: 'all 0.2s'
            }}
            >
            {name}
            </button>
        ))}
        </div>

        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
        <div style={{ ...cardStyle, flex: '1 1 100%', minWidth: '280px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <h3 style={{ ...titleStyle, alignSelf: 'flex-start' }}>СТРУКТУРА ВЫРУЧКИ</h3>
        {categories ? <div style={{ height: '300px', width: '300px' }}><Doughnut data={categories} options={{ responsive: true, maintainAspectRatio: false }} /></div> : <p style={{ color: '#9ca99d' }}>Загрузка...</p>}
        </div>

        <div style={{ ...cardStyle, flex: '1 1 100%', minWidth: '280px' }}>
        <h3 style={titleStyle}>ПОИСК СВЯЗОК (CROSS-SELL)</h3>
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
        <input
        type="text"
        placeholder="Например: Сырник"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleCrossSellSearch()}
        style={{ flex: 1, padding: '0.8rem', borderRadius: '6px', border: '1px solid #9ca99d', outline: 'none' }}
        />
        <button
        onClick={handleCrossSellSearch}
        style={{ padding: '0.8rem 1.5rem', background: '#3c5043', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
        >
        Искать
        </button>
        </div>

        {isSearching ? <p style={{ color: '#9ca99d' }}>Поиск...</p> :
        crossSellData ? (
            crossSellData.length > 0 ? (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <tbody>
                {crossSellData.map((item, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(156, 169, 157, 0.2)' }}>
                    <td style={{ padding: '0.8rem', color: '#3c5043' }}>Вместе с <b>{searchTerm}</b> берут <b>{item.item}</b></td>
                    <td style={{ padding: '0.8rem', color: '#3c5043', textAlign: 'right' }}>{item.frequency} чеков</td>
                    </tr>
                ))}
                </tbody>
                </table>
            ) : <p style={{ color: '#9ca99d' }}>Совместных покупок не найдено.</p>
        ) : (
            <p style={{ color: '#9ca99d', fontSize: '0.9rem' }}>Введите название товара, чтобы узнать, с чем его покупают чаще всего.</p>
        )}
        </div>
        </div>

        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
        <div style={{ ...cardStyle, flex: '1 1 100%', minWidth: '280px' }}>
        <h3 style={titleStyle}>ТОП-15 ПОПУЛЯРНЫХ СВЯЗОК (В ЦЕЛОМ)</h3>
        {basketData ? (
            <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
            <tr style={{ background: 'rgba(156, 169, 157, 0.1)', color: '#9ca99d', textTransform: 'uppercase' }}>
            <th style={{ padding: '0.8rem', textAlign: 'left' }}>Товар 1</th>
            <th style={{ padding: '0.8rem', textAlign: 'left' }}>Товар 2</th>
            <th style={{ padding: '0.8rem', textAlign: 'center' }}>Совместных чеков</th>
            </tr>
            </thead>
            <tbody>
            {basketData.map((pair, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid rgba(156, 169, 157, 0.2)' }}>
                <td style={{ padding: '0.8rem', color: '#3c5043' }}>{pair.item_a}</td>
                <td style={{ padding: '0.8rem', color: '#3c5043' }}>{pair.item_b}</td>
                <td style={{ padding: '0.8rem', color: '#3c5043', textAlign: 'center', fontWeight: 'bold' }}>{pair.frequency}</td>
                </tr>
            ))}
            </tbody>
            </table>
            </div>
        ) : <p style={{ color: '#9ca99d' }}>Загрузка...</p>}
        </div>
        </div>

        <div style={{ ...cardStyle, padding: '2rem' }}>
        <h3 style={titleStyle}>ABC-АНАЛИЗ (ТОП-50 ПОЗИЦИЙ)</h3>
        {abcData ? (
            <div style={{ height: '400px' }}>
            <Chart type='bar' data={abcData} options={{ responsive: true, maintainAspectRatio: false, scales: { y: { type: 'linear', display: true, position: 'left' }, y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, max: 105 }, x: { ticks: { display: false } } }, plugins: { tooltip: { callbacks: { title: (context) => context[0].label } } } }} />
            </div>
        ) : <p style={{ color: '#9ca99d' }}>Загрузка...</p>}
        </div>
        </div>
    );
}
