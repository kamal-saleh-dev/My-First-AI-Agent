# sql_templates.py — SQL Database templates (works with any DB)

SQL_SYSTEM_PROMPT = """You are a senior database architect.
RULES:
- Write clean, production-ready SQL
- Use proper indexes, constraints, and foreign keys
- Return ONLY one ```sql code block per file
- No explanations outside code blocks
- Default to PostgreSQL syntax unless told otherwise
- Always include created_at / updated_at timestamps
"""

SQL_PLANNING_PROMPT = """You are a senior database architect.
List the SQL files needed for: {task}

Output ONLY this format (one per line):
FileName:role

Roles: schema, table, seed, procedure, view, index, migration

RULES:
- Always start with: schema:schema
- One file per table/feature
- Max 6 files

Example for "products store":
schema:schema
products_table:table
orders_table:table
users_table:table
seed_data:seed
indexes:index
"""

SQL_TEMPLATES = {

    "schema": """-- schema.sql — Database schema setup
-- Run this first to create the database structure

-- Drop and recreate (development only)
-- DROP SCHEMA IF EXISTS public CASCADE;
-- CREATE SCHEMA public;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Utility function: auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""",

    "table": """-- {name}.sql — Table definition

CREATE TABLE IF NOT EXISTS {name} (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Auto-update timestamp
CREATE TRIGGER {name}_updated_at
    BEFORE UPDATE ON {name}
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Basic index on name
CREATE INDEX IF NOT EXISTS idx_{name}_name ON {name}(name);
CREATE INDEX IF NOT EXISTS idx_{name}_active ON {name}(is_active);
""",

    "migration": """-- migration_{name}.sql — Migration script
-- Version: 001
-- Description: {name}

BEGIN;

-- ↑ UP migration
ALTER TABLE your_table ADD COLUMN IF NOT EXISTS new_column VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_new ON your_table(new_column);

-- To rollback (↓ DOWN):
-- ALTER TABLE your_table DROP COLUMN IF EXISTS new_column;

COMMIT;
""",

    "seed": """-- seed_{name}.sql — Seed data for development/testing

BEGIN;

-- Clear existing seed data (dev only)
-- TRUNCATE TABLE {name} RESTART IDENTITY CASCADE;

INSERT INTO {name} (name, description, is_active) VALUES
    ('Item One',   'First sample item',   TRUE),
    ('Item Two',   'Second sample item',  TRUE),
    ('Item Three', 'Third sample item',   FALSE)
ON CONFLICT (id) DO NOTHING;

COMMIT;

SELECT COUNT(*) AS seeded_rows FROM {name};
""",

    "view": """-- view_{name}.sql — Database view

CREATE OR REPLACE VIEW v_{name} AS
SELECT
    t.id,
    t.name,
    t.description,
    t.is_active,
    t.created_at,
    -- Add JOINs here as needed:
    -- other_table.field AS related_field,
    COUNT(*) OVER() AS total_count
FROM {name} t
WHERE t.is_active = TRUE
ORDER BY t.created_at DESC;

-- Usage: SELECT * FROM v_{name};
""",

    "index": """-- indexes.sql — Performance indexes

-- Example indexes — adjust table/column names as needed:

-- Single column indexes
CREATE INDEX IF NOT EXISTS idx_users_email      ON users(email);
CREATE INDEX IF NOT EXISTS idx_products_name    ON products(name);
CREATE INDEX IF NOT EXISTS idx_orders_status    ON orders(status);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_orders_user_date ON orders(user_id, created_at DESC);

-- Partial indexes (only active records)
CREATE INDEX IF NOT EXISTS idx_products_active  ON products(id) WHERE is_active = TRUE;

-- Full text search index
-- CREATE INDEX IF NOT EXISTS idx_products_fts ON products USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '')));
""",

    "procedure": """-- procedure_{name}.sql — Stored procedures and functions

-- Function: get paginated results
CREATE OR REPLACE FUNCTION get_{name}_page(
    p_limit  INT DEFAULT 20,
    p_offset INT DEFAULT 0,
    p_search TEXT DEFAULT ''
)
RETURNS TABLE(
    id          INT,
    name        VARCHAR,
    description TEXT,
    is_active   BOOLEAN,
    created_at  TIMESTAMP,
    total_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id, t.name, t.description, t.is_active, t.created_at,
        COUNT(*) OVER() AS total_count
    FROM {name} t
    WHERE (p_search = '' OR t.name ILIKE '%' || p_search || '%')
    ORDER BY t.created_at DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Usage: SELECT * FROM get_{name}_page(20, 0, 'search term');

-- Procedure: soft delete
CREATE OR REPLACE PROCEDURE soft_delete_{name}(p_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE {name} SET is_active = FALSE, updated_at = NOW()
    WHERE id = p_id;
END;
$$;

-- Usage: CALL soft_delete_{name}(1);
""",

    "full_schema": """-- full_schema.sql — Complete database schema

BEGIN;

-- ═══════════════════════════════════
-- EXTENSIONS
-- ═══════════════════════════════════
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════
-- UTILITY
-- ═══════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════
-- TABLES
-- ═══════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    email      VARCHAR(255) UNIQUE NOT NULL,
    name       VARCHAR(200) NOT NULL,
    password   VARCHAR(255) NOT NULL,
    role       VARCHAR(50) DEFAULT 'user',
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {name} (
    id          SERIAL PRIMARY KEY,
    user_id     INT REFERENCES users(id) ON DELETE SET NULL,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    price       DECIMAL(10,2) DEFAULT 0,
    stock       INT DEFAULT 0,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════
-- TRIGGERS
-- ═══════════════════════════════════
CREATE TRIGGER users_updated_at   BEFORE UPDATE ON users   FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER {name}_updated_at  BEFORE UPDATE ON {name}  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ═══════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_users_email     ON users(email);
CREATE INDEX IF NOT EXISTS idx_{name}_user     ON {name}(user_id);
CREATE INDEX IF NOT EXISTS idx_{name}_active   ON {name}(is_active);

COMMIT;
""",
}

SQL_TEMPLATED_ROLES = set(SQL_TEMPLATES.keys())

SQL_ROLE_KEYWORDS = {
    "schema":     ["schema", "setup", "init", "database"],
    "table":      ["table", "entity", "model"],
    "migration":  ["migration", "alter", "update", "change"],
    "seed":       ["seed", "data", "fixture", "sample"],
    "view":       ["view", "report", "summary"],
    "index":      ["index", "indexes", "performance"],
    "procedure":  ["procedure", "function", "proc", "sp_"],
    "full_schema":["full", "complete", "all"],
}

def get_sql_role(name: str) -> str:
    nl = name.lower()
    for role, keywords in SQL_ROLE_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            return role
    if "_table" in nl:    return "table"
    if "migration" in nl: return "migration"
    if "seed" in nl:      return "seed"
    return "table"

def get_sql_template(name: str, role: str = None) -> str:
    if role is None:
        role = get_sql_role(name)
    tpl = SQL_TEMPLATES.get(role, SQL_TEMPLATES["table"])
    return tpl.format(name=name.lower().replace(" ", "_"))
