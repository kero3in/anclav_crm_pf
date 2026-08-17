import { useState, useEffect } from 'react';

export default function MenuConstructor() {
    const [items, setItems] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Пока стучимся в текущую ручку меню.
        // Позже мы добавим в api.py специальный эндпоинт /api/admin/menu,
        // который будет отдавать абсолютно все товары, включая скрытые (is_available = false).
        fetch('/api/menu')
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                // Разворачиваем сгруппированное меню в плоский массив для таблицы
                const flatItems = Object.values(data.menu).flat();
                setItems(flatItems);
            }
            setIsLoading(false);
        });
    }, []);

    const cardStyle = { background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px rgba(60, 80, 67, 0.05)', border: '1px solid rgba(156, 169, 157, 0.2)' };
    const titleStyle = { margin: '0 0 1.5rem 0', color: '#9ca99d', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' };

    return (
        <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h2 style={{ fontWeight: 'normal', letterSpacing: '1px', margin: 0 }}>КОНСТРУКТОР МЕНЮ</h2>
        <button style={{ background: '#3c5043', color: 'white', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
        + Добавить позицию
        </button>
        </div>

        <div style={cardStyle}>
        <h3 style={titleStyle}>УПРАВЛЕНИЕ АССОРТИМЕНТОМ</h3>
        {isLoading ? <p style={{ color: '#9ca99d' }}>Загрузка...</p> : (
            <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
            <tr style={{ background: 'rgba(156, 169, 157, 0.1)', color: '#9ca99d', textTransform: 'uppercase' }}>
            <th style={{ padding: '0.8rem', textAlign: 'left' }}>Название</th>
            <th style={{ padding: '0.8rem', textAlign: 'left' }}>Категория</th>
            <th style={{ padding: '0.8rem', textAlign: 'left' }}>Цены (по объемам)</th>
            <th style={{ padding: '0.8rem', textAlign: 'center' }}>Статус</th>
            <th style={{ padding: '0.8rem', textAlign: 'right' }}>Действия</th>
            </tr>
            </thead>
            <tbody>
            {items.map((item, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid rgba(156, 169, 157, 0.2)' }}>
                <td style={{ padding: '0.8rem', color: '#3c5043', fontWeight: 'bold' }}>{item.name}</td>
                <td style={{ padding: '0.8rem', color: '#3c5043' }}>{item.category}</td>
                <td style={{ padding: '0.8rem', color: '#3c5043' }}>
                {Object.entries(item.prices).map(([vol, price]) => (
                    <div key={vol}>{vol} мл: {price} ₽</div>
                ))}
                </td>
                <td style={{ padding: '0.8rem', textAlign: 'center' }}>
                <span style={{
                    background: item.is_available ? 'rgba(39, 174, 96, 0.1)' : 'rgba(231, 76, 60, 0.1)',
                                       color: item.is_available ? '#27ae60' : '#e74c3c',
                                       padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', fontSize: '0.8rem'
                }}>
                {item.is_available ? 'Доступен' : 'Скрыт'}
                </span>
                </td>
                <td style={{ padding: '0.8rem', textAlign: 'right' }}>
                <button style={{ background: 'none', border: 'none', color: '#3498db', cursor: 'pointer', fontWeight: 'bold' }}>Редактировать</button>
                </td>
                </tr>
            ))}
            </tbody>
            </table>
            </div>
        )}
        </div>
        </div>
    );
}
