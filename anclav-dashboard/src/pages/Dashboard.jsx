import { useState, useEffect } from 'react';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import {
    Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
    BarElement, ArcElement, Title, Tooltip, Legend, Filler
} from 'chart.js';

ChartJS.register(
    CategoryScale, LinearScale, PointElement, LineElement,
    BarElement, ArcElement, Title, Tooltip, Legend, Filler
);

export default function Dashboard({ startDate, endDate }) {
    const [summary, setSummary] = useState(null);
    const [dailyData, setDailyData] = useState(null);
    const [hourlyData, setHourlyData] = useState(null);
    const [crmData, setCrmData] = useState(null);

    useEffect(() => {
        const queryParams = `?start_date=${startDate}&end_date=${endDate}`;

        fetch(`/api/dashboard/summary${queryParams}`)
        .then(res => res.json())
        .then(data => {
            if (!data.error) setSummary(data);
        });

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
                                 fill: true, tension: 0.4
                                     },
                                     {
                                         label: 'Прибыль (₽)',
                                 data: data.map(item => item.profit),
                                 borderColor: '#27ae60',
                                 backgroundColor: 'rgba(39, 174, 96, 0.2)',
                                 fill: true, tension: 0.4
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
                                  datasets: [{
                                      label: 'Выручка по часам (₽)',
                                  data: data.map(item => item.revenue),
                                  backgroundColor: '#9ca99d',
                                  borderRadius: 4
                                  }]
                    });
                }
            });

            fetch(`/api/dashboard/crm_stats${queryParams}`)
            .then(res => res.json())
            .then(data => {
                if (!data.error && Array.isArray(data)) {
                    setCrmData({
                        labels: data.map(item => item.type),
                               datasets: [{
                                   data: data.map(item => item.total_revenue),
                               backgroundColor: ['#3c5043', '#d5dbd6'],
                               borderWidth: 0
                               }]
                    });
                }
            });
    }, [startDate, endDate]);

    const baseCardStyle = {
        background: 'white', padding: '1.5rem', borderRadius: '12px',
        boxShadow: '0 4px 6px rgba(60, 80, 67, 0.05)', border: '1px solid rgba(156, 169, 157, 0.2)',
        textAlign: 'center'
    };
    const titleStyle = { margin: '0 0 0.5rem 0', color: '#9ca99d', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' };
    const valueStyle = { fontSize: '2.2rem', fontWeight: 'bold', margin: 0, color: '#3c5043', whiteSpace: 'nowrap' };
    const profitStyle = { fontSize: '2.2rem', fontWeight: 'bold', margin: 0, color: '#27ae60', whiteSpace: 'nowrap' };

    return (
        <div>
        <h2 style={{ marginBottom: '2rem', fontWeight: 'normal', letterSpacing: '1px' }}>ОБЩАЯ СВОДКА</h2>

        {summary ? (
            <>
            {/* Верхний ряд: 3 карточки */}
            <div style={{ display: 'flex', gap: '2rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
            <div style={{ ...baseCardStyle, flex: '1 1 calc(33.333% - 2rem)', minWidth: '220px' }}>
            <h3 style={titleStyle}>Общая выручка</h3>
            <p style={valueStyle}>{summary.total_revenue?.toLocaleString('ru-RU')} ₽</p>
            </div>
            <div style={{ ...baseCardStyle, flex: '1 1 calc(33.333% - 2rem)', minWidth: '220px' }}>
            <h3 style={titleStyle}>Чистая прибыль</h3>
            <p style={profitStyle}>{summary.total_profit?.toLocaleString('ru-RU')} ₽</p>
            </div>
            <div style={{ ...baseCardStyle, flex: '1 1 calc(33.333% - 2rem)', minWidth: '220px' }}>
            <h3 style={titleStyle}>Рентабельность</h3>
            <p style={profitStyle}>{summary.margin_percent}%</p>
            </div>
            </div>

            {/* Нижний ряд: 1 широкая карточка */}
            <div style={{ display: 'flex', marginBottom: '2rem' }}>
            <div style={{ ...baseCardStyle, flex: '1 1 100%' }}>
            <h3 style={titleStyle}>Средний чек (UPT: {summary.upt})</h3>
            <p style={valueStyle}>
            {summary.total_receipts > 0 ? (summary.total_revenue / summary.total_receipts).toFixed(0) : 0} ₽
            </p>
            </div>
            </div>
            </>
        ) : <p style={{ color: '#9ca99d' }}>Загрузка...</p>}

        <div style={{ ...baseCardStyle, flex: '1 1 100%', minWidth: '280px', padding: '2rem', marginBottom: '2rem', textAlign: 'left' }}>
        <h3 style={{ ...titleStyle, marginBottom: '1.5rem' }}>ДИНАМИКА ВЫРУЧКИ И ПРИБЫЛИ</h3>
        {dailyData ? (
            <div style={{ height: '300px' }}>
            <Line data={dailyData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } } }} />
            </div>
        ) : <p style={{ color: '#9ca99d' }}>Ожидание данных...</p>}
        </div>

        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
        <div style={{ ...baseCardStyle, flex: '1 1 100%', minWidth: '280px', textAlign: 'left' }}>
        <h3 style={{ ...titleStyle, marginBottom: '1.5rem' }}>ЗАГРУЗЕННОСТЬ ПО ЧАСАМ (ВЫРУЧКА)</h3>
        {hourlyData ? (
            <div style={{ height: '250px' }}>
            <Bar data={hourlyData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }} />
            </div>
        ) : <p style={{ color: '#9ca99d' }}>Ожидание данных...</p>}
        </div>

        <div style={{ ...baseCardStyle, flex: '1 1 100%', minWidth: '280px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <h3 style={{ ...titleStyle, marginBottom: '1.5rem', alignSelf: 'flex-start' }}>ДОЛЯ ЛОЯЛЬНОСТИ (ВЫРУЧКА)</h3>
        {crmData ? (
            <div style={{ height: '200px', width: '200px' }}>
            <Doughnut data={crmData} options={{ responsive: true, maintainAspectRatio: false }} />
            </div>
        ) : <p style={{ color: '#9ca99d' }}>Ожидание данных...</p>}
        </div>
        </div>
        </div>
    );
}
