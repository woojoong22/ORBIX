# ORBIX

ORBIX is a Django project prepared for GitHub and Paperclip integration.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Optional environment variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_USE_WHITENOISE`
- `DJANGO_SECURE_COOKIES`
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_CATEGORY_MODEL`

Uploaded user media and the local SQLite database are intentionally ignored.

## PWA

ORBIX includes a web app manifest and root-scoped service worker:

- Manifest: `/static/posts/manifest.webmanifest`
- Service worker: `/service-worker.js`

After deployment, open the site in a mobile browser and use "Add to Home Screen" to install ORBIX like an app.

## Production deployment

For a Render-style deployment:

1. Connect the GitHub repository.
2. Use the included `render.yaml`, or configure:
   - Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start: `python manage.py migrate && gunicorn mysite.wsgi:application`
3. Set environment variables:
   - `DJANGO_DEBUG=False`
   - `DJANGO_USE_WHITENOISE=True`
   - `DJANGO_SECURE_COOKIES=True`
   - `DJANGO_ALLOWED_HOSTS=<your-domain>,<render-host>`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-domain>,https://<render-host>`
   - `DJANGO_SECRET_KEY=<strong-secret>`
   - `DATABASE_URL=<postgres-connection-url>`

For local development, the defaults continue to use SQLite and `DEBUG=True`.
