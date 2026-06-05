"""Debug team assignment against local DB."""
from utils.db import get_db_connection
from services.team_assignment import add_team_member, get_team_members_for_user, team_assignment_kind_for_target
from models.user import get_user_by_id, normalize_role_key

conn = get_db_connection()

for table in ("manager_clients", "manager_moderators"):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    print(table, cols)

rows = conn.execute(
    "SELECT id, role_key, display_id FROM users ORDER BY id LIMIT 40"
).fetchall()
for r in rows:
    print(f"user {r['id']} role={r['role_key']} display={r['display_id']}")

client = conn.execute(
    """
    SELECT id, role_key FROM users
    WHERE role_key NOT IN ('management','admin','support','moderator','manager')
    LIMIT 1
    """
).fetchone()
mgr = conn.execute("SELECT id FROM users WHERE role_key='manager' LIMIT 1").fetchone()
mod = conn.execute("SELECT id FROM users WHERE role_key='moderator' LIMIT 1").fetchone()

if client and mgr:
    cid, mid = int(client["id"]), int(mgr["id"])
    u = get_user_by_id(conn, cid)
    print("client kind", team_assignment_kind_for_target(u["role_key"]))
    ok, code = add_team_member(conn, cid, mid)
    print("add client<-manager", ok, code)
    try:
        tm = get_team_members_for_user(conn, cid)
        print("team count", len(tm))
    except Exception as exc:
        print("get_team_members error:", exc)

if mgr and mod:
    ok, code = add_team_member(conn, int(mgr["id"]), int(mod["id"]))
    print("add manager<-moderator", ok, code)
    try:
        tm = get_team_members_for_user(conn, int(mgr["id"]))
        print("manager team", len(tm))
    except Exception as exc:
        print("get manager team error:", exc)
