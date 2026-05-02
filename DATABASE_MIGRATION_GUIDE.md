# Database Migration Guide: SQLite to PostgreSQL

## Overview

This guide walks you through migrating your Django application from SQLite (development) to PostgreSQL (production). The updated `settings.py` now supports both databases via environment configuration.

## Current Status

- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL (to be configured)
- **Configuration**: Environment-based switching via `DB_ENGINE`

## Prerequisites

### For PostgreSQL Setup

1. **PostgreSQL Server** (version 12+)
   - Windows: Download from https://www.postgresql.org/download/windows/
   - macOS: `brew install postgresql`
   - Linux: `sudo apt-get install postgresql postgresql-contrib`

2. **Python PostgreSQL Adapter**
   ```bash
   pip install psycopg2-binary
   ```

3. **Environment Variables** (see `.env` setup below)

## Step-by-Step Migration

### Phase 1: Prepare Development Environment

#### 1.1 Update `.env` File

Add these variables to your `backend/.env`:

```env
# Database Configuration
DB_ENGINE=sqlite3
DB_NAME=supplica_db
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Other existing variables
SECRET_KEY=your-secret-key
DEBUG=True
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

#### 1.2 Install PostgreSQL Adapter

```bash
cd backend
pip install psycopg2-binary
```

#### 1.3 Verify Current SQLite Setup

```bash
# Check current database
python manage.py dbshell

# You should see SQLite prompt
sqlite>
```

### Phase 2: Export Data from SQLite

#### 2.1 Create Data Dump

```bash
cd backend

# Export all data to JSON
python manage.py dumpdata > data_backup.json

# Or export specific apps
python manage.py dumpdata categories > categories_data.json
python manage.py dumpdata identity > identity_data.json
python manage.py dumpdata enquiry > enquiry_data.json
```

#### 2.2 Backup SQLite Database

```bash
# Create backup copy
cp db.sqlite3 db.sqlite3.backup
```

### Phase 3: Set Up PostgreSQL

#### 3.1 Create PostgreSQL Database and User

**On Windows (using psql):**
```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE supplica_db;

-- Create user
CREATE USER supplica_user WITH PASSWORD 'your_secure_password';

-- Grant privileges
ALTER ROLE supplica_user SET client_encoding TO 'utf8';
ALTER ROLE supplica_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE supplica_user SET default_transaction_deferrable TO on;
ALTER ROLE supplica_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE supplica_db TO supplica_user;

-- Exit
\q
```

**On macOS/Linux:**
```bash
# Create database
createdb -U postgres supplica_db

# Create user
psql -U postgres -d supplica_db -c "CREATE USER supplica_user WITH PASSWORD 'your_secure_password';"

# Grant privileges
psql -U postgres -d supplica_db -c "ALTER ROLE supplica_user SET client_encoding TO 'utf8';"
psql -U postgres -d supplica_db -c "ALTER ROLE supplica_user SET default_transaction_isolation TO 'read committed';"
psql -U postgres -d supplica_db -c "GRANT ALL PRIVILEGES ON DATABASE supplica_db TO supplica_user;"
```

#### 3.2 Verify PostgreSQL Connection

```bash
# Test connection
psql -U supplica_user -d supplica_db -h localhost

# You should see PostgreSQL prompt
supplica_db=>
```

### Phase 4: Migrate to PostgreSQL

#### 4.1 Update `.env` to Use PostgreSQL

```env
DB_ENGINE=postgresql
DB_NAME=supplica_db
DB_USER=supplica_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
```

#### 4.2 Run Migrations

```bash
cd backend

# Create tables in PostgreSQL
python manage.py migrate

# Verify migrations
python manage.py showmigrations
```

#### 4.3 Load Data from Backup

```bash
# Load all data
python manage.py loaddata data_backup.json

# Or load specific apps
python manage.py loaddata categories_data.json
python manage.py loaddata identity_data.json
python manage.py loaddata enquiry_data.json
```

#### 4.4 Create Superuser

```bash
python manage.py createsuperuser
```

#### 4.5 Verify Data

```bash
# Check database connection
python manage.py dbshell

# You should see PostgreSQL prompt
supplica_db=>

# List tables
\dt

# Exit
\q
```

### Phase 5: Test Application

#### 5.1 Run Development Server

```bash
python manage.py runserver
```

#### 5.2 Test API Endpoints

```bash
# Test login
curl -X POST http://localhost:8000/api/admin/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}'

# Test products
curl http://localhost:8000/api/categories/products/

# Test categories
curl http://localhost:8000/api/categories/
```

#### 5.3 Test Admin Panel

- Navigate to `http://localhost:8000/admin/`
- Login with superuser credentials
- Verify all data is present

### Phase 6: Production Deployment

#### 6.1 Environment Variables for Production

```env
# Production Database
DB_ENGINE=postgresql
DB_NAME=supplica_db_prod
DB_USER=supplica_prod_user
DB_PASSWORD=very_secure_password_here
DB_HOST=your-postgres-server.com
DB_PORT=5432

# Security
DEBUG=False
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# CORS
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

#### 6.2 Production Database Setup

```bash
# On production server
createdb -U postgres supplica_db_prod

# Create user with strong password
psql -U postgres -d supplica_db_prod -c "CREATE USER supplica_prod_user WITH PASSWORD 'very_secure_password_here';"

# Grant privileges
psql -U postgres -d supplica_db_prod -c "GRANT ALL PRIVILEGES ON DATABASE supplica_db_prod TO supplica_prod_user;"
```

#### 6.3 Deploy Application

```bash
# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Load data (if needed)
python manage.py loaddata data_backup.json

# Restart application server
# (depends on your deployment setup - Gunicorn, uWSGI, etc.)
```

## Configuration Reference

### Database Engine Options

**SQLite (Development)**
```python
DB_ENGINE=sqlite3
```

**PostgreSQL (Production)**
```python
DB_ENGINE=postgresql
DB_NAME=supplica_db
DB_USER=supplica_user
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_ENGINE` | `sqlite3` | Database engine (sqlite3 or postgresql) |
| `DB_NAME` | `supplica_db` | Database name (PostgreSQL only) |
| `DB_USER` | `postgres` | Database user (PostgreSQL only) |
| `DB_PASSWORD` | `` | Database password (PostgreSQL only) |
| `DB_HOST` | `localhost` | Database host (PostgreSQL only) |
| `DB_PORT` | `5432` | Database port (PostgreSQL only) |

## Troubleshooting

### Issue: "psycopg2 not installed"

**Solution:**
```bash
pip install psycopg2-binary
```

### Issue: "FATAL: Ident authentication failed for user"

**Solution:** Update PostgreSQL `pg_hba.conf` to use password authentication:
```
# Change from 'ident' to 'md5' or 'scram-sha-256'
local   all             all                                     md5
```

Then restart PostgreSQL:
```bash
# Windows
net stop postgresql-x64-15
net start postgresql-x64-15

# macOS
brew services restart postgresql

# Linux
sudo systemctl restart postgresql
```

### Issue: "Database does not exist"

**Solution:** Create the database:
```bash
createdb -U postgres supplica_db
```

### Issue: "Permission denied for schema public"

**Solution:** Grant schema privileges:
```bash
psql -U postgres -d supplica_db -c "GRANT ALL ON SCHEMA public TO supplica_user;"
```

### Issue: "Connection refused"

**Solution:** Verify PostgreSQL is running:
```bash
# Windows
Get-Service postgresql-x64-15

# macOS
brew services list

# Linux
sudo systemctl status postgresql
```

### Issue: Data not loading after migration

**Solution:** Check for foreign key constraints:
```bash
# Disable constraints during load
python manage.py loaddata data_backup.json --disable-constraints

# Or reload with specific order
python manage.py loaddata categories_data.json
python manage.py loaddata identity_data.json
python manage.py loaddata enquiry_data.json
```

## Rollback Plan

If you need to rollback to SQLite:

### 1. Update `.env`
```env
DB_ENGINE=sqlite3
```

### 2. Restore SQLite Database
```bash
cp db.sqlite3.backup db.sqlite3
```

### 3. Restart Application
```bash
python manage.py runserver
```

## Performance Considerations

### SQLite
- ✅ Zero configuration
- ✅ Good for development
- ❌ Limited concurrency
- ❌ Not suitable for production

### PostgreSQL
- ✅ Excellent concurrency
- ✅ Better performance at scale
- ✅ Advanced features (JSON, arrays, etc.)
- ✅ Production-ready
- ❌ Requires server setup

## Best Practices

1. **Always backup before migration**
   ```bash
   python manage.py dumpdata > backup.json
   cp db.sqlite3 db.sqlite3.backup
   ```

2. **Test in development first**
   - Set up PostgreSQL locally
   - Run full test suite
   - Verify all features work

3. **Use strong passwords**
   - Generate secure passwords for production
   - Store in secure environment variables
   - Never commit to version control

4. **Monitor performance**
   - Check query performance
   - Monitor connection pool
   - Set up logging and alerts

5. **Regular backups**
   ```bash
   # Daily backup
   pg_dump -U supplica_user -d supplica_db > backup_$(date +%Y%m%d).sql
   ```

## Useful PostgreSQL Commands

```bash
# Connect to database
psql -U supplica_user -d supplica_db -h localhost

# List databases
\l

# List tables
\dt

# Describe table
\d table_name

# Show table size
SELECT pg_size_pretty(pg_total_relation_size('table_name'));

# Show database size
SELECT pg_size_pretty(pg_database_size('supplica_db'));

# Backup database
pg_dump -U supplica_user -d supplica_db > backup.sql

# Restore database
psql -U supplica_user -d supplica_db < backup.sql

# Exit
\q
```

## Next Steps

1. ✅ Install PostgreSQL
2. ✅ Update `.env` with PostgreSQL credentials
3. ✅ Install `psycopg2-binary`
4. ✅ Backup SQLite data
5. ✅ Create PostgreSQL database and user
6. ✅ Run migrations
7. ✅ Load data
8. ✅ Test application
9. ✅ Deploy to production

## Support

For issues or questions:
- Check PostgreSQL logs: `pg_log/` directory
- Check Django logs: `backend/logs/error.log`
- Review Django documentation: https://docs.djangoproject.com/en/5.2/ref/databases/
- PostgreSQL documentation: https://www.postgresql.org/docs/

---

**Last Updated**: April 28, 2026
**Version**: 1.0.0
**Status**: Ready for Implementation
