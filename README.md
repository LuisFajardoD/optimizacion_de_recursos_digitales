# Optimizacion de Recursos Digitales - Proyecto VIII

MVP para optimizar imagenes por lote (video es fase futura). Incluye frontend en React + Vite + TS y backend en Django + DRF con worker local.

## Estructura
- /frontend
- /backend
- /docs

## Requisitos
- Node.js 18+
- Python 3.9+

## Configuracion local

### 1) Backend
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

### 2) Worker local (otra terminal)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py worker
```

### 3) Frontend
```powershell
cd frontend
npm install
npm run dev
```

## Make-like (opcional)
```powershell
# Backend
backend\.venv\Scripts\python -m pip install -r backend/requirements.txt
backend\.venv\Scripts\python backend/manage.py makemigrations
backend\.venv\Scripts\python backend/manage.py migrate
backend\.venv\Scripts\python backend/manage.py runserver

# Worker
backend\.venv\Scripts\python backend/manage.py worker

# Frontend
npm --prefix frontend install
npm --prefix frontend run dev
```

## Endpoints
- POST /api/jobs/
- GET /api/jobs/
- GET /api/jobs/{id}/
- GET /api/jobs/{id}/download/

## Notas
- CORS abierto para desarrollo local.
- Archivos locales en backend/media.
