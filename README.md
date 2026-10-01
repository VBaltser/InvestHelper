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

## Запуск в Docker

Для контейнерного запуска нужны Docker и Docker Compose.

```bash
cp .env.example .env
# Укажите TINKOFF_TOKEN в .env
docker compose up --build -d
```

Приложение будет доступно по адресу http://localhost:8080. Значение порта можно
изменить через `APP_PORT` в корневом `.env`.

Проверка состояния и просмотр журналов:

```bash
docker compose ps
docker compose logs -f
```

Остановка приложения:

```bash
docker compose down
```

Compose запускает два сервиса: FastAPI backend и Nginx с собранным React
frontend. Nginx проксирует запросы `/api` во внутренний backend, поэтому наружу
публикуется только один HTTP-порт. Секреты читаются из `.env` при запуске и не
добавляются в Docker-образы.

## Виртуальные машины в VirtualBox

Для локального дипломного стенда `Vagrantfile` создаёт две Ubuntu 22.04 VM:

| VM | IP | CPU | RAM | Назначение |
|---|---|---:|---:|---|
| `jenkins` | `192.168.56.10` | 2 | 4 ГБ | Jenkins и сборка приложения |
| `app` | `192.168.56.20` | 2 | 4 ГБ | Docker Compose и InvestHelper |

Перед запуском установите VirtualBox и Vagrant, затем выполните из корня
репозитория:

```powershell
vagrant up
```

Проверка состояния и подключение к машинам:

```powershell
vagrant status
vagrant ssh jenkins
vagrant ssh app
```

Управлять машинами можно отдельно:

```powershell
vagrant halt app
vagrant reload jenkins
vagrant provision app
```

Остановить весь стенд можно командой `vagrant halt`. Команда
`vagrant destroy` безвозвратно удаляет обе VM и их локальные диски.

Vagrant создаёт машины и сеть, а установка Jenkins, Docker и остальных
компонентов выполняется отдельными Ansible playbook. На обеих VM заранее
устанавливаются Python, `python3-apt`, `curl` и корневые сертификаты, необходимые
для последующей настройки через Ansible.

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
