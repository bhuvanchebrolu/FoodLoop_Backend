from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('foods', '0004_create_db_views_and_triggers'),
        ('apartments', '0003_apartment_latitude_apartment_longitude'),
    ]

    operations = [
        # 1. PostgreSQL Trigram Extension for Fuzzy Search
        migrations.RunSQL(
            sql="""
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            CREATE INDEX IF NOT EXISTS idx_fooditem_trgm_name ON foods_fooditem USING gin (name gin_trgm_ops);
            CREATE INDEX IF NOT EXISTS idx_foodshare_trgm_title ON shares_foodshare USING gin (title gin_trgm_ops);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_fooditem_trgm_name;
            DROP INDEX IF EXISTS idx_foodshare_trgm_title;
            """
        ),
        # 2. Materialized View for Eco-Badges and Percentile Rankings
        migrations.RunSQL(
            sql="""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mview_user_eco_badges AS
            WITH user_totals AS (
                SELECT 
                    u.id AS user_id,
                    u.full_name,
                    COALESCE(SUM(s.initial_quantity), 0.0) AS total_shared_kg,
                    COUNT(s.id) AS completed_shares_count
                FROM users_customuser u
                LEFT JOIN shares_foodshare s ON u.id = s.owner_id AND s.status = 'COMPLETED'
                GROUP BY u.id, u.full_name
            )
            SELECT 
                user_id,
                full_name,
                total_shared_kg,
                completed_shares_count,
                PERCENT_RANK() OVER (ORDER BY total_shared_kg ASC) AS percentile,
                NTILE(4) OVER (ORDER BY total_shared_kg DESC) AS quartile
            FROM user_totals;
            """,
            reverse_sql="DROP MATERIALIZED VIEW IF EXISTS mview_user_eco_badges;"
        ),
        # 3. Partitioned Audit Activity Log & Trigger Procedure
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS audit_activitylog (
                id BIGSERIAL,
                user_id INT,
                action VARCHAR(100),
                entity_type VARCHAR(100),
                entity_id INT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, created_at)
            ) PARTITION BY RANGE (created_at);

            CREATE TABLE IF NOT EXISTS audit_activitylog_y2026 PARTITION OF audit_activitylog
                FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');

            CREATE OR REPLACE FUNCTION fn_audit_fooditem_changes()
            RETURNS TRIGGER AS $$
            BEGIN
                INSERT INTO audit_activitylog(user_id, action, entity_type, entity_id)
                VALUES (NEW.user_id, 'FOOD_ITEM_' || TG_OP, 'FoodItem', NEW.id);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_audit_fooditem ON foods_fooditem;
            CREATE TRIGGER trg_audit_fooditem
            AFTER INSERT OR UPDATE ON foods_fooditem
            FOR EACH ROW EXECUTE FUNCTION fn_audit_fooditem_changes();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_audit_fooditem ON foods_fooditem;
            DROP FUNCTION IF EXISTS fn_audit_fooditem_changes();
            DROP TABLE IF EXISTS audit_activitylog CASCADE;
            """
        )
    ]
