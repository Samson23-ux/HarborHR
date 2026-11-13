from alembic import op


def enable_rls(table: str, column: str = "organization_id"):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON {table}
        USING ({column} = NULLIF(current_setting('app.current_org', true), '')::uuid)
    """)


def disable_rls(table: str):
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
