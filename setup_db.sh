#!/bin/bash
# Skrypt zakłada bazę PostgreSQL i użytkownika dla Master Data.
# Uruchom raz: bash setup_db.sh
# Wymaga: sudo -u postgres (lub uruchom jako użytkownik postgres).

set -e
DB_NAME="${DB_NAME:-masterdata_mebloszyk}"
DB_USER="${DB_USER:-masterdata_app}"
if [ -z "$PGPASSWORD_MASTERDATA" ]; then
  PGPASSWORD_MASTERDATA=$(openssl rand -hex 16)
  echo "Wygenerowane haslo do bazy (zapisz je): $PGPASSWORD_MASTERDATA"
fi

sudo -u postgres psql -v ON_ERROR_STOP=1 <<EOSQL
CREATE USER $DB_USER WITH PASSWORD '$PGPASSWORD_MASTERDATA' CREATEDB;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
EOSQL

echo ""
echo "Baza utworzona: $DB_NAME, uzytkownik: $DB_USER"
ENV_FILE="$(dirname "$0")/.env"
echo "DATABASE_URL=postgresql://$DB_USER:$PGPASSWORD_MASTERDATA@localhost:5432/$DB_NAME" > "$ENV_FILE"
echo "Zapisano DATABASE_URL do $ENV_FILE"
