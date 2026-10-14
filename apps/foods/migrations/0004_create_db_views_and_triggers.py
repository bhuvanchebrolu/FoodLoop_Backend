from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('foods', '0003_alter_fooditem_options_and_more'),
        ('shares', '0001_initial'),
    ]

    operations = [
        # 1. Create SQL View for Food Dashboard Analytics with CTEs & GROUP BY
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE VIEW v_food_dashboard_analytics AS
            WITH user_pantry AS (
                SELECT 
                    id, 
                    user_id, 
                    category, 
                    storage_location, 
                    estimated_value,
                    status,
                    quantity
                FROM foods_fooditem
            ),
            active_pantry AS (
                SELECT * FROM user_pantry WHERE status != 'CONSUMED' AND quantity > 0
            )
            SELECT 
                user_id,
                COUNT(*) AS total_food_items,
                COUNT(CASE WHEN status = 'AVAILABLE' THEN 1 END) AS available_items,
                COUNT(CASE WHEN status = 'EXPIRING_SOON' THEN 1 END) AS expiring_soon,
                COUNT(CASE WHEN status = 'EXPIRED' THEN 1 END) AS expired_items,
                SUM(estimated_value) AS total_estimated_value
            FROM active_pantry
            GROUP BY user_id;
            """,
            reverse_sql="DROP VIEW IF EXISTS v_food_dashboard_analytics;"
        ),
        # 2. Create SQL View for Community Leaderboard with Window Functions (DENSE_RANK)
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE VIEW v_user_community_leaderboard AS
            WITH user_stats AS (
                SELECT 
                    u.id AS user_id,
                    u.full_name,
                    u.apartment_id,
                    COALESCE(SUM(s.initial_quantity), 0.0) AS total_shared_kg,
                    COUNT(s.id) AS completed_shares_count
                FROM users_customuser u
                LEFT JOIN shares_foodshare s ON u.id = s.owner_id AND s.status = 'COMPLETED'
                GROUP BY u.id, u.full_name, u.apartment_id
            )
            SELECT 
                user_id,
                full_name,
                apartment_id,
                total_shared_kg,
                completed_shares_count,
                DENSE_RANK() OVER (ORDER BY total_shared_kg DESC) AS global_rank,
                DENSE_RANK() OVER (PARTITION BY apartment_id ORDER BY total_shared_kg DESC) AS apartment_rank
            FROM user_stats;
            """,
            reverse_sql="DROP VIEW IF EXISTS v_user_community_leaderboard;"
        )
    ]
