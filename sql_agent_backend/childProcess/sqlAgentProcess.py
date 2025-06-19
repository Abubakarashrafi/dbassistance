import sys, json
from sql_agent import SQLAgent
from langgraph.checkpoint.postgres import PostgresSaver
import os
DB_URI = os.getenv("CHECKPOINT_URL")
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    agent = SQLAgent(checkpointer)
    message = sys.argv[1]
    thread_id = "cd5c8c6b-ac45-4190-ae22-c55b3d43405f"
    output = agent.run(message)
    print(json.dumps(output))