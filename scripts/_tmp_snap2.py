import pymysql,json
c=pymysql.connect(host="192.168.3.124",port=3306,user="root",password="Yvns!niwo^coc57Qpoi",database="hermes-hq",charset="utf8mb4",cursorclass=pymysql.cursors.DictCursor)
cur=c.cursor()
tid="0878254c-7e10-47ce-a673-cb1e02a210ad"
cur.execute("SELECT task_id,status,current_phase,LEFT(IFNULL(error_message,''),120) err,updated_at FROM hermes_tasks WHERE task_id=%s",(tid,))
print("TASK", json.dumps(cur.fetchone(),ensure_ascii=False,default=str))
cur.execute("SELECT status,COUNT(*) n FROM collect_phase_steps WHERE task_id=%s GROUP BY status",(tid,))
print("STEPS", list(cur.fetchall()))
cur.execute("SELECT step_key,status,LEFT(IFNULL(message,''),80) m FROM collect_phase_steps WHERE task_id=%s AND status<>'pending' ORDER BY step_order",(tid,))
print("ACTIVE", json.dumps(list(cur.fetchall()),ensure_ascii=False,default=str))
cur.execute("SELECT COUNT(*) c FROM hermes_tool_outputs WHERE task_id=%s",(tid,))
print("tools", cur.fetchone())
c.close()
