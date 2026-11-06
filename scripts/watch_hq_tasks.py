# -*- coding: utf-8 -*-
import time, json
from datetime import datetime
import pymysql

DB=dict(host="192.168.3.124",port=3306,user="root",password="Yvns!niwo^coc57Qpoi",database="hermes-hq",charset="utf8mb4",cursorclass=pymysql.cursors.DictCursor)
print("[%s] watch hermes-hq start" % datetime.now().strftime("%H:%M:%S"), flush=True)
last=None
while True:
    try:
        c=pymysql.connect(**DB)
        cur=c.cursor()
        cur.execute("SELECT task_id,status,task_type,current_phase,LEFT(IFNULL(error_message,''),80) err,created_at,updated_at FROM hermes_tasks ORDER BY created_at DESC LIMIT 5")
        tasks=list(cur.fetchall())
        snap=[]
        for t in tasks:
            tid=t["task_id"]
            cur.execute("SELECT status, COUNT(*) n FROM collect_phase_steps WHERE task_id=%s GROUP BY status",(tid,))
            st={r["status"]:r["n"] for r in cur.fetchall()}
            cur.execute("SELECT step_key,status FROM collect_phase_steps WHERE task_id=%s AND status='running' ORDER BY step_order",(tid,))
            running=[r["step_key"] for r in cur.fetchall()]
            snap.append({"task":t,"steps":st,"running":running})
        c.close()
        s=json.dumps(snap,ensure_ascii=False,default=str)
        if s!=last:
            print("[%s] ---" % datetime.now().strftime("%H:%M:%S"), flush=True)
            print(s, flush=True)
            last=s
    except Exception as e:
        print("[%s] err %s" % (datetime.now().strftime("%H:%M:%S"), e), flush=True)
    time.sleep(5)
