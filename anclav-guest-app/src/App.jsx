import { useState, useEffect } from 'react';

const WebApp = window.Telegram.WebApp;
const API_URL = "";
const TERMINALS = {
  '1010625022006769': 'Калининградская, 1',
  '1010977707053285': 'Ленина, 18'
};

const MODIFIERS_DICT = {
  milk: {
    title: "Выбор молока",
    options: [
      { id: 'cow', name: 'Обычное', price: 0 },
      { id: 'alt', name: 'Растительное', price: 50 },
      { id: 'lactose_free', name: 'Безлактозное', price: 50 }
    ]
  },
  syrup: {
    title: "Сиропы",
    options: [
      { id: 'caramel', name: 'Карамель', price: 30 },
      { id: 'vanilla', name: 'Ваниль', price: 30 },
      { id: 'none', name: 'Без сиропа', price: 0 }
    ]
  }
};

export default function App() {
  const [menu, setMenu] = useState({});
  const [selectedTerminal, setSelectedTerminal] = useState('1010625022006769');
  const [cart, setCart] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastOrder, setLastOrder] = useState(null);
  const [activeItem, setActiveItem] = useState(null);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [selectedVolume, setSelectedVolume] = useState('');
  const [selectedMods, setSelectedMods] = useState({});

  const fetchApi = async (path, options = {}) => {
    const currentInitData = WebApp.initData || "";
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `tma ${currentInitData}`
    };
    const response = await fetch(`${API_URL}${path}`, { ...options, headers });
    return response.json();
  };

  useEffect(() => {
    Promise.all([
      fetchApi('/api/menu'),
                fetchApi('/api/orders/last')
    ]).then(([menuData, lastOrderData]) => {
      if (menuData.status === 'success') {
        setMenu(menuData.menu);
      }
      if (lastOrderData.status === 'success' && lastOrderData.last_order) {
        setLastOrder(lastOrderData.last_order);
      }
      setIsLoading(false);
    });
  }, []);

  const handleRepeatOrder = () => {
    if (!lastOrder) return;

    const allMenuItems = Object.values(menu).flat();

    const repeatedCart = lastOrder.items.map(item => {
      const menuItem = allMenuItems.find(m => m.id === item.menu_item_id);
      if (!menuItem) return null;

      let itemPrice = 0;
      const vol = item.modifiers["Объем"] ? item.modifiers["Объем"].replace(" мл", "") : null;
      if (vol && menuItem.prices[vol]) {
        itemPrice += menuItem.prices[vol];
      } else {
        itemPrice += Math.min(...Object.values(menuItem.prices));
      }

      return {
        cart_id: Math.random().toString(36).substr(2, 9),
                                             menu_item_id: item.menu_item_id,
                                             name: menuItem.name,
                                             quantity: item.quantity,
                                             price: itemPrice,
                                             modifiers: item.modifiers
      };
    }).filter(Boolean);

    setCart([...cart, ...repeatedCart]);
    setSelectedTerminal(lastOrder.terminal_id);
    setIsCartOpen(true);
    WebApp.HapticFeedback.impactOccurred('medium');
  };

  const openItemModal = (item) => {
    setActiveItem(item);
    const volumes = Object.keys(item.prices).sort();
    setSelectedVolume(volumes[0]);

    const initialMods = {};
    if (item.allowed_modifiers) {
      item.allowed_modifiers.forEach(modKey => {
        const zeroOption = MODIFIERS_DICT[modKey]?.options.find(o => o.price === 0);
        if (zeroOption) initialMods[modKey] = zeroOption;
      });
    }
    setSelectedMods(initialMods);
  };

  const handleModChange = (modKey, option) => {
    setSelectedMods(prev => ({ ...prev, [modKey]: option }));
  };

  const calculateActiveItemPrice = () => {
    if (!activeItem) return 0;
    let price = activeItem.prices[selectedVolume] || 0;
    Object.values(selectedMods).forEach(mod => {
      price += mod.price;
    });
    return price;
  };

  const addItemToCart = () => {
    const finalPrice = calculateActiveItemPrice();
    const formattedMods = { "Объем": `${selectedVolume} мл` };
    Object.entries(selectedMods).forEach(([key, opt]) => {
      if (opt.name !== 'Обычное' && opt.name !== 'Без сиропа') {
        formattedMods[MODIFIERS_DICT[key].title] = opt.name;
      }
    });

    const cartItem = {
      cart_id: Math.random().toString(36).substr(2, 9),
      menu_item_id: activeItem.id,
      name: activeItem.name,
      quantity: 1,
      price: finalPrice,
      modifiers: formattedMods
    };

    setCart([...cart, cartItem]);
    setActiveItem(null);
    WebApp.HapticFeedback.impactOccurred('light');
  };

  const removeFromCart = (cartId) => {
    setCart(cart.filter(item => item.cart_id !== cartId));
    WebApp.HapticFeedback.impactOccurred('light');
    if (cart.length === 1) setIsCartOpen(false);
  };

    const checkout = async () => {
      if (cart.length === 0) return;

      const totalAmount = cart.reduce((sum, item) => sum + item.price, 0);
      const payload = {
        terminal_id: selectedTerminal,
        total_amount: totalAmount,
        items: cart.map(item => ({
          menu_item_id: item.menu_item_id,
          quantity: item.quantity,
          modifiers: item.modifiers
        }))
      };

      const res = await fetchApi('/api/orders', { method: 'POST', body: JSON.stringify(payload) });

      if (res.status === 'success') {
        WebApp.HapticFeedback.notificationOccurred('success');
        WebApp.showAlert(`✅ Заказ #${res.order_id} оформлен! Назовите этот номер бариста.`);
        setCart([]);
        setIsCartOpen(false);
        WebApp.close();
      } else {
        WebApp.showAlert(`Ошибка: ${res.error}`);
      }
    };

    if (isLoading) return <div style={{ padding: '2rem', textAlign: 'center' }}>Загрузка меню...</div>;

    const totalCartSum = cart.reduce((sum, item) => sum + item.price, 0);

    return (
      <div style={{ padding: '1rem', position: 'relative', minHeight: '100vh' }}>
      <div style={{ marginBottom: '1.5rem' }}>
      <h3 style={{ margin: '0 0 10px 0', fontSize: '1rem' }}>📍 Точка самовывоза:</h3>
      <div style={{ display: 'flex', gap: '10px' }}>
      {Object.entries(TERMINALS).map(([id, name]) => (
        <button
        key={id}
        onClick={() => setSelectedTerminal(id)}
        style={{
          flex: 1, padding: '12px 8px', borderRadius: '12px', border: 'none',
          background: selectedTerminal === id ? 'var(--accent)' : 'var(--bg-card)',
                                                      color: selectedTerminal === id ? 'white' : 'var(--text-main)',
                                                      fontWeight: 'bold', fontSize: '0.9rem',
                                                      boxShadow: '0 2px 4px rgba(0,0,0,0.05)', transition: '0.2s'
        }}
        >
        {name}
        </button>
      ))}
      </div>
      </div>

      {lastOrder && cart.length === 0 && (
        <div style={{ marginBottom: '2rem' }}>
        <button
        onClick={handleRepeatOrder}
        style={{
          width: '100%', padding: '16px', background: 'var(--bg-card)',
                                          color: 'var(--text-main)', border: '1px solid var(--accent)',
                                          borderRadius: '16px', fontWeight: 'bold', fontSize: '1rem',
                                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                          boxShadow: '0 2px 8px rgba(60, 80, 67, 0.05)'
        }}
        >
        <span>🔄 Повторить прошлый заказ</span>
        <span style={{ color: 'var(--text-muted)' }}>→</span>
        </button>
        </div>
      )}

      {Object.entries(menu).map(([category, items]) => (
        <div key={category} style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>{category}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        {items.map(item => {
          const minPrice = Math.min(...Object.values(item.prices));
          return (
            <div key={item.id} style={{
              background: 'var(--bg-card)', padding: '12px', borderRadius: '16px',
                  display: 'flex', flexDirection: 'column',
                  border: '1px solid var(--border)'
            }}>
            <h4 style={{ margin: '0 0 5px 0', fontSize: '0.95rem' }}>{item.name}</h4>
            <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)', flex: 1, lineHeight: '1.2' }}>
            {item.description}
            </p>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
            <span style={{ fontWeight: 'bold' }}>от {minPrice} ₽</span>
            <button
            onClick={() => openItemModal(item)}
            style={{
              background: 'var(--accent)', color: 'white', border: 'none',
                  borderRadius: '50%', width: '30px', height: '30px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '1.2rem', lineHeight: 1, cursor: 'pointer'
            }}
            >
            +
            </button>
            </div>
            </div>
          )
        })}
        </div>
        </div>
      ))}

      {cart.length > 0 && !activeItem && !isCartOpen && (
        <div style={{ position: 'fixed', bottom: '20px', left: '20px', right: '20px', zIndex: 90 }}>
        <button
        onClick={() => setIsCartOpen(true)}
        style={{
          width: '100%', padding: '16px', background: 'var(--accent)', color: 'white',
                                                         border: 'none', borderRadius: '16px', fontWeight: 'bold', fontSize: '1.1rem',
                                                         boxShadow: '0 4px 15px rgba(60, 80, 67, 0.3)', display: 'flex', justifyContent: 'space-between'
        }}
        >
        <span>В корзине: {cart.length}</span>
        <span>{totalCartSum} ₽</span>
        </button>
        </div>
      )}

      {activeItem && (
        <>
        <div onClick={() => setActiveItem(null)} style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 100
        }}></div>
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, background: 'var(--bg-main)',
                      borderRadius: '24px 24px 0 0', padding: '24px', zIndex: 101,
                      boxShadow: '0 -4px 20px rgba(0,0,0,0.1)'
        }}>
        <h2 style={{ margin: '0 0 5px 0' }}>{activeItem.name}</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '20px' }}>{activeItem.description}</p>

        <h4 style={{ marginBottom: '10px' }}>Объем</h4>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', overflowX: 'auto' }}>
        {Object.keys(activeItem.prices).sort().map(vol => (
          <button
          key={vol}
          onClick={() => setSelectedVolume(vol)}
          style={{
            flex: 1, padding: '10px', borderRadius: '12px', border: 'none',
            background: selectedVolume === vol ? 'var(--accent)' : 'var(--bg-card)',
                                                           color: selectedVolume === vol ? 'white' : 'var(--text-main)',
                                                           fontWeight: 'bold'
          }}
          >
          {vol} мл
          </button>
        ))}
        </div>

        {activeItem.allowed_modifiers?.map(modKey => {
          const modConfig = MODIFIERS_DICT[modKey];
          if (!modConfig) return null;

          return (
            <div key={modKey} style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '10px' }}>{modConfig.title}</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '8px' }}>
            {modConfig.options.map(opt => (
              <button
              key={opt.id}
              onClick={() => handleModChange(modKey, opt)}
              style={{
                padding: '12px', borderRadius: '12px', border: '1px solid var(--border)',
                                           background: selectedMods[modKey]?.id === opt.id ? 'var(--accent)' : 'var(--bg-card)',
                                           color: selectedMods[modKey]?.id === opt.id ? 'white' : 'var(--text-main)',
                                           display: 'flex', justifyContent: 'space-between', fontWeight: 'bold'
              }}
              >
              <span>{opt.name}</span>
              {opt.price > 0 && <span style={{ opacity: 0.8 }}>+{opt.price} ₽</span>}
              </button>
            ))}
            </div>
            </div>
          );
        })}

        <button onClick={addItemToCart} style={{
          width: '100%', padding: '16px', background: 'var(--accent)', color: 'white',
                      border: 'none', borderRadius: '16px', fontWeight: 'bold', fontSize: '1.1rem', marginTop: '10px'
        }}>
        Добавить за {calculateActiveItemPrice()} ₽
        </button>
        </div>
        </>
      )}

      {isCartOpen && (
        <>
        <div onClick={() => setIsCartOpen(false)} style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 100
        }}></div>
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, background: 'var(--bg-main)',
                      borderRadius: '24px 24px 0 0', padding: '24px', zIndex: 101, maxHeight: '80vh', overflowY: 'auto'
        }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>Корзина</h2>
        <button onClick={() => setIsCartOpen(false)} style={{ background: 'none', border: 'none', fontSize: '1.5rem', color: 'var(--text-muted)' }}>×</button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
        {cart.map(item => (
          <div key={item.cart_id} style={{
            background: 'var(--bg-card)', padding: '16px', borderRadius: '16px',
                           display: 'flex', justifyContent: 'space-between', alignItems: 'center'
          }}>
          <div>
          <h4 style={{ margin: '0 0 5px 0' }}>{item.name}</h4>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          {Object.values(item.modifiers).join(', ')}
          </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <span style={{ fontWeight: 'bold' }}>{item.price} ₽</span>
          <button onClick={() => removeFromCart(item.cart_id)} style={{
            background: 'rgba(231, 76, 60, 0.1)', color: '#e74c3c', border: 'none',
                           borderRadius: '8px', padding: '8px 12px', fontWeight: 'bold'
          }}>Удалить</button>
          </div>
          </div>
        ))}
        </div>

        <button onClick={checkout} style={{
          width: '100%', padding: '16px', background: 'var(--accent)', color: 'white',
                      border: 'none', borderRadius: '16px', fontWeight: 'bold', fontSize: '1.1rem'
        }}>
        Оплатить при получении • {totalCartSum} ₽
        </button>
        </div>
        </>
      )}

      </div>
    );
}
