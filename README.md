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

Для локального дипломного стенда `Vagrantfile` создаёт три Ubuntu 22.04 VM:

| VM | IP | CPU | RAM | Назначение |
|---|---|---:|---:|---|
| `control` | `192.168.56.5` | 2 | 2 ГБ | Управляющий узел Ansible |
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
vagrant ssh control
vagrant ssh jenkins
vagrant ssh app
```

`control` получает отдельный SSH-ключ, а его публичная часть автоматически
добавляется пользователю `vagrant` на двух управляемых машинах. Проверить связь
после создания или повторного provisioning всех VM можно так:

```powershell
vagrant ssh control -c "cd /home/vagrant/ansible && ansible managed -m ping"
```

Если `jenkins` и `app` были созданы старой версией `Vagrantfile`, примените к
ним новые provisioner после создания `control`:

```powershell
vagrant up control
vagrant provision jenkins
vagrant provision app
```

Управлять машинами можно отдельно:

```powershell
vagrant halt app
vagrant reload jenkins
vagrant provision app
```

Остановить весь стенд можно командой `vagrant halt`. Команда
`vagrant destroy` безвозвратно удаляет все три VM и их локальные диски.

Vagrant создаёт машины и сеть, устанавливает Ansible на `control` и формирует
inventory `/home/vagrant/ansible/inventory.ini`. Установка Jenkins, Docker и
остальных компонентов выполняется отдельными Ansible playbook. На управляемых
VM заранее устанавливаются Python, `python3-apt`, `curl` и корневые сертификаты.

## Деплой через Jenkins

Инфраструктура стенда находится в отдельном репозитории
`InvestHelper.Infrastructure`. Все стадии Jenkinsfile выполняются на `ci`:

1. **Prepare**: установка Python/npm-зависимостей и формирование уникального тега.
2. **Lint**: Ruff для backend и CI-скриптов, ESLint/TypeScript для frontend.
3. **Build**: компиляция backend, сборка frontend и двух Docker-образов.
4. **Test built application**: запуск именно собранных образов в отдельном
   Compose-проекте со случайным локальным портом; проверки backend через nginx,
   HTML/JS/CSS, маршрутизации SPA и валидации некорректных API-запросов.
5. **Publish artifacts**: публикация обоих образов в `192.168.56.10:5000`
   для каждой ветки; сохранение frontend-архива, отчёта JUnit, логов контейнеров
   и метаданных образов в Jenkins с fingerprint.
6. **Deploy**: автоматический SSH-запуск Docker Compose на VM `app`
   (`192.168.56.20`) только для `main`/`master`, после успешных предыдущих стадий.

Коммиты отслеживаются через polling SCM каждые две минуты, а multibranch job
периодически обнаруживает новые ветки. Webhook и доступ GitHub к локальному
Jenkins для этого не требуются. Параметр `RUN_DEPLOY` удалён: основная ветка
деплоится автоматически. Остальные ветки проходят CI без деплоя.

Параметры запуска: `APP_VERSION` — префикс тега образов,
`DEPLOY_ENV=prod` — порт 8080, `DEPLOY_ENV=staging` — порт 8082.
По умолчанию выбран `prod`. Номер сборки, Git SHA и хеш имени ветки добавляются
к тегу автоматически. Frontend-образ содержит результат `npm run build` этой
же сборки. Pipeline сообщает об успехе деплоя после проверки готовности
контейнеров и HTTP health endpoints.
Секреты backend берутся из `/opt/investhelper/.env` на `app`.

Тесты не используют настоящие финансовые токены и не обращаются к внешним API.
При завершении тестовые контейнеры и сеть удаляются; логи сохраняются даже при
ошибке. Провал линтера, сборки или тестов блокирует публикацию и деплой.
Артефакты Jenkins хранятся для последних 20 сборок; образы остаются в registry.

Для существующего стенда выполните `vagrant provision control` из репозитория
инфраструктуры (устанавливает в том числе плагин `junit`), затем отправьте
изменения приложения в Git. Jenkins получает pipeline из Git, а не из локальной
папки Windows. Параметры branch job могли сохраниться от предыдущей версии:
выберите `DEPLOY_ENV=prod` для первого запуска новой версии.

**Невыполненный обязательный пункт:** внешние уведомления о сборке и деплое
пока пропущены по согласованию. Сообщение в console log Jenkins их не заменяет.

## Переменные приложения

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
