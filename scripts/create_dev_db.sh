#!/usr/bin/env bash
#
# CREATE THE LOCAL DEVELOPMENT MariaDB DATABASE, USER AND GRANT.
#
# THE TARGET NAME, USER AND PASSWORD COME FROM .env (SEE .env.example) SO NO
# PASSWORD IS EVER COMMITTED. THE MariaDB ADMIN PASSWORD IS TYPED IN AT THE
# PROMPT AND NEVER STORED.
#
# USAGE:
#     bash scripts/create_dev_db.sh              # ADMIN USER DEFAULTS TO root
#     DB_ADMIN_USER=admin bash scripts/create_dev_db.sh
#
# RE-RUNNING IS SAFE: EXISTING DATABASES AND USERS ARE LEFT ALONE, AND THE
# PASSWORD AND GRANT ARE RE-APPLIED TO MATCH .env.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
DB_ADMIN_USER="${DB_ADMIN_USER:-root}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "No .env found at ${ENV_FILE}" >&2
    echo "Copy .env.example to .env and set DB_NAME, DB_USER and DB_PASSWORD first." >&2
    exit 1
fi

# READ .env WITHOUT SOURCING IT, SO A STRAY COMMAND IN THE FILE CANNOT RUN HERE.
read_env() {
    local key="$1"
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "${ENV_FILE}" | tail -1 | tr -d '"'"'"'\r'
}

DB_NAME="$(read_env DB_NAME)"
DB_USER="$(read_env DB_USER)"
DB_PASSWORD="$(read_env DB_PASSWORD)"

for required in DB_NAME DB_USER DB_PASSWORD; do
    if [[ -z "${!required}" ]]; then
        echo "${required} is missing from ${ENV_FILE}" >&2
        exit 1
    fi
done

if ! command -v mariadb >/dev/null 2>&1; then
    echo "mariadb client not found on PATH — install MariaDB first (brew install mariadb)." >&2
    exit 1
fi

echo "Creating database '${DB_NAME}' and user '${DB_USER}'@'localhost' as '${DB_ADMIN_USER}'."
echo "You will be prompted for the MariaDB ${DB_ADMIN_USER} password."

# THE VALUES ARE INTERPOLATED INTO SQL, SO QUOTE THEM THE WAY MariaDB EXPECTS:
# BACKTICKS FOR THE IDENTIFIER, SINGLE QUOTES FOR THE LITERALS.
mariadb -u "${DB_ADMIN_USER}" -p <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "Done. Check it with:  mariadb -u ${DB_USER} -p ${DB_NAME} -e 'SELECT DATABASE();'"
