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
- `OPENAI_API_KEY`
- `OPENAI_CATEGORY_MODEL`

Uploaded user media and the local SQLite database are intentionally ignored.
