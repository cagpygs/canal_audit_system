import crud
conn = crud.get_connection()
cur = conn.cursor()
tables = [
    "contract_management_admin_financial_sanction",
    "contract_management_technical_sanction",
    "contract_management_tender_award_contract",
    "contract_management_contract_master",
    "contract_management_payments_recoveries",
    "contract_management_budget_summary"
]
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}" WHERE master_id IS NULL')
    cnt = cur.fetchone()[0]
    print(f"{t}: {cnt} orphaned rows")
crud.release_connection(conn)
