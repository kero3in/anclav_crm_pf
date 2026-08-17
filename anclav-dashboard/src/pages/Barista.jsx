import { useState, useEffect } from 'react';

const TERMINAL_NAMES = {
    '1010625022006769': 'Точка №1 (ул. Калининградская, 1)',
    '1010977707053285': 'Точка №2 (ул. Ленина, 18)'
};

export default function Barista({ startDate, endDate }) {
    const [groupedData, setGroupedData] = useState(null);

    useEffect(() => {
        const queryParams = `?start_date=${startDate}&end_date=${endDate}`;
        fetch(`/api/dashboard/barista${queryParams}`)
        .then((res) => res.json())
        .then((data) => {
            if (!data.error && Array.isArray(data)) {
                const groups = data.reduce((acc, curr) => {
                    if (!acc[curr.terminal_id]) acc[curr.terminal_id] = [];
                    acc[curr.terminal_id].push(curr);
                    return acc;
                }, {});
                setGroupedData(groups);
            }
        });
    }, [startDate, endDate]);

    const tableHeaderStyle = { textAlign: 'left', padding: '1rem', color: '#9ca99d', textTransform: 'uppercase', fontSize: '0.9rem', borderBottom: '2px solid #9ca99d' };
    const tableCellStyle = { padding: '1rem', color: '#3c5043', borderBottom: '1px solid rgba(156, 169, 157, 0.2)', fontWeight: '500' };
    const cardStyle = { background: 'white', borderRadius: '12px', boxShadow: '0 4px 6px rgba(60, 80, 67, 0.05)', overflow: 'hidden', marginBottom: '2rem' };

    return (
        <div>
        <h2 style={{ marginBottom: '2rem', fontWeight: 'normal', letterSpacing: '1px' }}>РЕЙТИНГ БАРИСТА ПО ТОЧКАМ</h2>

        {!groupedData ? (
            <p style={{ color: '#9ca99d' }}>Ожидание данных...</p>
        ) : (
            Object.keys(groupedData).map((terminalId) => (
                <div key={terminalId} style={cardStyle}>
                <div style={{ background: '#f4f6f4', padding: '1rem 1.5rem', borderBottom: '1px solid rgba(156, 169, 157, 0.2)' }}>
                <h3 style={{ margin: 0, color: '#3c5043', fontSize: '1.1rem' }}>
                {TERMINAL_NAMES[terminalId] || `Терминал: ${terminalId}`}
                </h3>
                </div>

                {/* Обертка для скролла на мобильных */}
                <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                <tr>
                <th style={tableHeaderStyle}>Сотрудник</th>
                <th style={tableHeaderStyle}>Смены</th>
                <th style={tableHeaderStyle}>Выручка</th>
                <th style={tableHeaderStyle}>Чеки</th>
                <th style={tableHeaderStyle}>Ср. чек</th>
                </tr>
                </thead>
                <tbody>
                {groupedData[terminalId].map((person, index) => (
                    <tr key={index} style={{ transition: 'background 0.2s' }}>
                    <td style={tableCellStyle}>{person.cashier_name}</td>
                    <td style={tableCellStyle}>{person.shifts_count}</td>
                    <td style={tableCellStyle}>{person.total_revenue.toLocaleString('ru-RU')} ₽</td>
                    <td style={tableCellStyle}>{person.receipts_count}</td>
                    <td style={tableCellStyle}>
                    {person.receipts_count > 0 ? Math.round(person.total_revenue / person.receipts_count) : 0} ₽
                    </td>
                    </tr>
                ))}
                </tbody>
                </table>
                </div>
                </div>
            ))
        )}
        </div>
    );
}
