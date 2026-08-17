import { useState, useEffect } from 'react';
import { Line, Bar } from 'react-chartjs-2';

const TERMINAL_NAMES = {
    '1010625022006769': 'Точка №1 (ул. Калининградская, 1)',
    '1010977707053285': 'Точка №2 (ул. Ленина, 18)'
};

export default function Points({ startDate, endDate }) {
    const [pointsData, setPointsData] = useState(null);
    const [selectedTerminal, setSelectedTerminal] = useState(null);

    const [dailyData, setDailyData] = useState(null);
    const [hourlyData, setHourlyData] = useState(null);

    // Загрузка общей статистики по точкам для кнопок
    useEffect(() => {
        const queryParams = `?start_date=${startDate}&end_date=${endDate}`;
        fetch(`/api/dashboard/points${queryParams}`)
        .then(res => res.json())
        .then(data => {
            if (!data.error && Array.isArray(data)) {
                setPointsData(data);
                if (data.length > 0 && !selectedTerminal) {
                    setSelectedTerminal(data[0].terminal_id);
                }
            }
        });
    }, [startDate, endDate]);

    // Загрузка графиков для выбранной точки
    useEffect(() => {
        if (!selectedTerminal) return;
        const queryParams = `?start_date=${startDate}&end_date=${endDate}&terminal_id=${selectedTerminal}`;

        // Обновленный запрос: теперь рисуем две линии (Выручка и Прибыль)
        fetch(`/api/dashboard/daily_revenue${queryParams}`)
        .then(res => res.json())
        .then(data => {
            if (!data.error && Array.isArray(data)) {
                setDailyData({
                    labels: data.map(item => item.date),
                             datasets: [
                                 {
                                     label: 'Выручка (₽)',
                             data: data.map(item => item.revenue),
                             borderColor: '#3c5043',
                             backgroundColor: 'rgba(156, 169, 157, 0.1)',
                             fill: true,
                             tension: 0.4
                                 },
                                 {
                                     label: 'Прибыль (₽)',
                             data: data.map(item => item.profit),
                             borderColor: '#27ae60',
                             backgroundColor: 'rgba(39, 174, 96, 0.2)',
                             fill: true,
                             tension: 0.4
                                 }
                             ]
                });
            }
        });

        fetch(`/api/dashboard/hourly${queryParams}`)
        .then(res => res.json())
        .then(data => {
            if (!data.error && Array.isArray(data)) {
                setHourlyData({
                    labels: data.map(item => item.hour),
                              datasets: [{ label: 'Выручка по часам (₽)', data: data.map(item => item.revenue), backgroundColor: '#9ca99d', borderRadius: 4 }]
                });
            }
        });
    }, [startDate, endDate, selectedTerminal]);

    const cardStyle = { background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px rgba(60, 80, 67, 0.05)', border: '1px solid rgba(156, 169, 157, 0.2)' };
    const titleStyle = { margin: '0 0 1.5rem 0', color: '#9ca99d', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' };

    return (
        <div>
        <h2 style={{ marginBottom: '2rem', fontWeight: 'normal', letterSpacing: '1px' }}>ДЕТАЛЬНАЯ АНАЛИТИКА ПО ТОЧКАМ</h2>

        {pointsData && (
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
            {pointsData.map(point => (
                <button
                key={point.terminal_id}
                onClick={() => setSelectedTerminal(point.terminal_id)}
                style={{
                    flex: '1 1 100%',
                    padding: '1rem 1.5rem', cursor: 'pointer', borderRadius: '8px', fontWeight: 'bold', border: 'none',
                    background: selectedTerminal === point.terminal_id ? '#3c5043' : 'white',
                    color: selectedTerminal === point.terminal_id ? 'white' : '#3c5043',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)', transition: 'all 0.2s'
                }}
                >
                {TERMINAL_NAMES[point.terminal_id] || point.terminal_id}
                <div style={{ fontSize: '0.8rem', opacity: 0.8, marginTop: '0.5rem', fontWeight: 'normal' }}>
                Выручка: {point.total_revenue.toLocaleString('ru-RU')} ₽
                </div>
                </button>
            ))}
            </div>
        )}

        {selectedTerminal && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <div style={cardStyle}>
            <h3 style={titleStyle}>ДИНАМИКА ВЫРУЧКИ И ПРИБЫЛИ</h3>
            {dailyData ? (
                <div style={{ height: '300px' }}>
                {/* Включили легенду (legend: true), чтобы было понятно, где какая линия */}
                <Line data={dailyData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } } }} />
                </div>
            ) : <p style={{ color: '#9ca99d' }}>Ожидание данных...</p>}
            </div>

            <div style={cardStyle}>
            <h3 style={titleStyle}>ЗАГРУЗЕННОСТЬ ПО ЧАСАМ</h3>
            {hourlyData ? (
                <div style={{ height: '250px' }}>
                <Bar data={hourlyData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }} />
                </div>
            ) : <p style={{ color: '#9ca99d' }}>Ожидание данных...</p>}
            </div>
            </div>
        )}
        </div>
    );
}
