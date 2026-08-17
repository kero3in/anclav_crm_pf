import { useState, useEffect } from 'react';
import { Doughnut } from 'react-chartjs-2';

export default function CrmAnalytics({ startDate, endDate }) {
    const [crmData, setCrmData] = useState(null);

    useEffect(() => {
        const queryParams = `?start_date=${startDate}&end_date=${endDate}`;
        fetch(`/api/dashboard/rfm_cohorts${queryParams}`)
        .then(res => res.json())
        .then(data => {
            if (!data.error) setCrmData(data);
        });
    }, [startDate, endDate]);

    const cardStyle = { background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px rgba(60, 80, 67, 0.05)', border: '1px solid rgba(156, 169, 157, 0.2)' };
    const titleStyle = { margin: '0 0 1.5rem 0', color: '#9ca99d', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' };

    if (!crmData) return <p style={{ color: '#9ca99d', padding: '2rem' }}>Загрузка данных...</p>;

    return (
        <div>
        <h2 style={{ marginBottom: '2rem', fontWeight: 'normal', letterSpacing: '1px' }}>КЛИЕНТСКАЯ АНАЛИТИКА</h2>

        {!crmData.has_data ? (
            <div style={{ ...cardStyle, textAlign: 'center', padding: '4rem 2rem' }}>
            <h3 style={{ color: '#3c5043', fontSize: '1.5rem', marginBottom: '1rem' }}>Недостаточно данных для CRM аналитики</h3>
            <p style={{ color: '#9ca99d', maxWidth: '500px', margin: '0 auto' }}>
            В выбранном периоде нет ни одной транзакции с авторизованным гостем. Графики RFM-сегментации и Когортного удержания появятся здесь автоматически, как только бариста начнут сканировать Telegram-бот клиентов на кассе.
            </p>
            </div>
        ) : (
            <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
            <div style={{ ...cardStyle, flex: '1 1 100%', minWidth: '280px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <h3 style={{ ...titleStyle, alignSelf: 'flex-start' }}>RFM-СЕГМЕНТАЦИЯ БАЗЫ</h3>
            <div style={{ height: '300px', width: '300px' }}>
            <Doughnut
            data={{
                labels: crmData.rfm.map(s => s.segment),
             datasets: [{ data: crmData.rfm.map(s => s.count), backgroundColor: ['#27ae60', '#3498db', '#f1c40f', '#e67e22', '#e74c3c'], borderWidth: 0 }]
            }}
            options={{ responsive: true, maintainAspectRatio: false }}
            />
            </div>
            </div>

            <div style={{ ...cardStyle, flex: '1 1 100%', minWidth: '280px' }}>
            <h3 style={titleStyle}>КОГОРТНЫЙ АНАЛИЗ (УДЕРЖАНИЕ)</h3>
            <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
            <tr style={{ background: 'rgba(156, 169, 157, 0.1)', color: '#9ca99d' }}>
            <th style={{ padding: '0.8rem', textAlign: 'left' }}>Когорта (Первый визит)</th>
            <th style={{ padding: '0.8rem', textAlign: 'left' }}>Месяц активности</th>
            <th style={{ padding: '0.8rem', textAlign: 'center' }}>Вернулось клиентов</th>
            </tr>
            </thead>
            <tbody>
            {crmData.cohorts.map((c, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid rgba(156, 169, 157, 0.2)' }}>
                <td style={{ padding: '0.8rem', color: '#3c5043', fontWeight: 'bold' }}>{c.cohort}</td>
                <td style={{ padding: '0.8rem', color: '#3c5043' }}>{c.activity}</td>
                <td style={{ padding: '0.8rem', color: '#3c5043', textAlign: 'center' }}>{c.users}</td>
                </tr>
            ))}
            </tbody>
            </table>
            </div>
            </div>
            </div>
        )}
        </div>
    );
}
