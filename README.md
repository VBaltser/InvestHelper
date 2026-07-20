# InvestHelper

Личный анализатор портфеля Т-Инвестиции. MVP: отображение структуры портфеля по данным T-Invest API.

## Что показывает

- Список ваших брокерских счетов
- Общую стоимость портфеля и доходность
- Структуру по классам активов (акции, облигации, фонды, валюта и т.д.)
- Таблицу позиций с долей в портфеле
- **Скринер облигаций** — цены, доходность, сроки погашения, фильтры

## Требования

- Python 3.10+
- Node.js 18+
- Токен T-Invest API (достаточно readonly)

Токен можно выпустить в [личном кабинете Т-Инвестиций](https://developer.tbank.ru/invest/intro/intro/).

## Быстрый старт

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
# Отредактируйте .env — вставьте свой TINKOFF_TOKEN
```

### 2. Frontend

```bash
cd frontend
npm install
```

### 3. Запуск через ярлык (Windows)

После первой настройки зависимостей:

```powershell
powershell -ExecutionPolicy Bypass -File .\create-desktop-shortcut.ps1
```

На рабочем столе появится ярлык **InvestHelper**. Двойной клик:

1. запускает backend (`http://127.0.0.1:8000`)
2. запускает frontend (`http://localhost:5173`)
3. открывает приложение в браузере

Можно также запускать напрямую: `start.bat` в корне проекта.

Ручной запуск без ярлыка:

```bash
# Backend
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Frontend (в другом терминале)
cd frontend
npm run dev
```

Откройте http://localhost:5173

- `/` — портфель
- `/bonds` — скринер облигаций
- `/dfa` — скринер долговых ЦФА

> Первый запуск скринера занимает ~20–30 сек (загрузка цен и купонов). Данные кэшируются на 30 минут.

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TINKOFF_TOKEN` | Токен доступа T-Invest API |
| `TINKOFF_MODE` | `prod` (боевой) или `sandbox` (песочница) |
| `TINKOFF_SSL_VERIFY` | `true` / `false` — проверка SSL (см. ниже) |
| `TINKOFF_SSL_CA_FILE` | Путь к корневому сертификату организации (опционально) |

### Ошибка SSL (CERTIFICATE_VERIFY_FAILED)

Часто возникает из-за корпоративного прокси или антивируса, который подменяет HTTPS-сертификат.

1. **Быстрое решение** (личное использование): в `backend/.env` добавьте:
   ```
   TINKOFF_SSL_VERIFY=false
   ```
2. **Безопаснее**: экспортируйте корневой сертификат вашей организации и укажите:
   ```
   TINKOFF_SSL_CA_FILE=C:\path\to\corp-ca.pem
   ```

После изменения `.env` перезапустите backend.

## Архитектура

```
backend/   FastAPI + T-Invest REST API
frontend/  React + Vite + Recharts
```

Backend проксирует запросы к T-Invest REST API, чтобы токен не попадал в браузер.

## Дальнейшие шаги

- Анализ по секторам и отраслям
- История изменения структуры
- Сравнение с целевой аллокацией
- Экспорт в Excel/CSV
