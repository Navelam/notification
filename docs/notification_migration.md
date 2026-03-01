# Notification Module Migration Steps

Use Flask-Migrate/Alembic in your project root:

```bash
flask db migrate -m "add notifications and notification_reads tables"
flask db upgrade
```

If this is your first migration setup:

```bash
flask db init
flask db migrate -m "initial"
flask db upgrade
```

## Manual SQLite check

```bash
sqlite3 instance/app.db ".tables"
```

Expected new tables:
- `notifications`
- `notification_reads`
