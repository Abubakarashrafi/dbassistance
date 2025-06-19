from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage,ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from typing import TypedDict, Annotated, Literal, Optional, Dict
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import uuid

from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import tool
from sqlalchemy import text
import os
from langgraph.checkpoint.postgres import PostgresSaver  

load_dotenv()

class Verdict(BaseModel):
    verdict: Literal['Safe', 'Unsafe', 'Greeting'] = Field(
        description='Check if query is safe, unsafe, or a greeting message'
    )

class State(TypedDict):
    schema: Dict[str, Dict[str, Dict]]
    messages: Annotated[list[AnyMessage], add_messages]
    generated_sql: Annotated[list[AnyMessage],add_messages]
    verdict: str
    tool_output: Optional[str]

class SQLAgent:
    def __init__(self,checkpointer):
        self.db = SQLDatabase.from_uri(
            os.get_env('DATABASE_URL')
        )
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.0-flash',
            google_api_key=os.getenv("GEMINI_API_KEY")
        )
        self.cached_schema = None
        self.schema_cache_time = 0
        self.sql_tool = tool(self._sql_executor_tool)
        self.llm = self.llm.bind_tools(tools=[self.sql_tool])
        self.DB_URI = os.getenv("DB_URI")
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def _sql_executor_tool(self, raw_query: str) -> str:
        """Execute sql query"""
        try:
            with self.db._engine.connect() as connection:
                result = connection.execute(text(raw_query))
                rows = result.fetchall()
                columns = result.keys()
                data = [dict(zip(columns, row)) for row in rows]
                return data
        except Exception as e:
            return f"Query execution failed: {str(e)}"

    def get_schema(self, state: State) -> State:
        
        query = """SELECT
    ns.nspname AS schema,
    cls.relname AS table,
    attr.attname AS column,
    pg_catalog.format_type(attr.atttypid, attr.atttypmod) AS type,
    CASE WHEN pk.contype = 'p' AND attr.attnum = ANY (pk.conkey) THEN 'YES' ELSE 'NO' END AS primary_key,
    fk.confrelid::regclass::text AS foreign_table,
    fa.attname AS foreign_column
    FROM
    pg_attribute attr
    JOIN
    pg_class cls ON cls.oid = attr.attrelid
    JOIN
    pg_namespace ns ON ns.oid = cls.relnamespace
    LEFT JOIN
    pg_attrdef def ON def.adrelid = cls.oid AND def.adnum = attr.attnum
    LEFT JOIN
    pg_constraint pk ON pk.conrelid = cls.oid
        AND pk.contype = 'p'
    LEFT JOIN
    pg_constraint fk ON fk.conrelid = cls.oid
        AND fk.contype = 'f'
        AND attr.attnum = ANY (fk.conkey)
    LEFT JOIN
    pg_attribute fa ON fa.attrelid = fk.confrelid
        AND fa.attnum = fk.confkey[1]
    WHERE
    ns.nspname NOT IN ('pg_catalog', 'information_schema')
    AND cls.relkind = 'r'  -- only tables
    AND attr.attnum > 0
    AND NOT attr.attisdropped
    ORDER BY
    ns.nspname,
    cls.relname,
    attr.attnum;"""  
        with self.db._engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            schema_data = [dict(row._mapping) for row in rows]
        return {"schema": schema_data}

    def model(self, state: State) -> State:
        prompt = PromptTemplate(
            template="""You are an expert SQL assistant made by Abu Bakar. Strictly follow these rules:
        DATABASE SCHEMA:
        {schema}
        RULES:
        1. GREETING DETECTED? 
        - Respond with greeting only not sql if contains greetings
        2. ONLY use tables/columns from the schema above
        3. ONLY generate SELECT queries(no DML/DDL)
        4. NEVER invent column/table names
        4. ALWAYS validate joins against schema relationships
        5. If unsure, ask for clarification
        6. If user query required result from unkown table which is not presented in schema so simply return Database doesnt contain this table
        USER QUESTION: {user_input}
        Generate ONLY the SQL query (no explanations, no markdown):""",  # your prompt here
            input_variables=["schema", "user_input"]
        )
        chain = prompt | self.llm
        resp = chain.invoke({"user_input": state["messages"][-5:], "schema": state["schema"]})
        raw_query = [resp][-1].content.strip().removeprefix('```sql').removesuffix('```').strip()
        return {"messages": state['messages']+[resp], "generated_sql": state["generated_sql"]+ [raw_query]}

    def query_validator(self, state: State) -> State:
        query = state['messages'][-1].content
        parser = PydanticOutputParser(pydantic_object=Verdict)
        
        prompt = PromptTemplate(
        template="""# SQL VALIDATION PROTOCOL
         === RULES ===
        1. ONLY SELECT queries permitted
        2. ABSOLUTELY NO:
        - DML (INSERT/UPDATE/DELETE/TRUNCATE/MERGE)
        - DDL (CREATE/ALTER/DROP/RENAME)
        - TCL (COMMIT/ROLLBACK/SAVEPOINT)
        3. BANNED SYNTAX: ; -- /* */ EXEC CALL DECLARE

        === INPUT ===
        {query}

        === OUTPUT DIRECTIVE ===
        {format_instructions}
        Respond ONLY with valid JSON matching the schema.""",
            input_variables=['query'],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        chain = prompt | self.llm | parser
        
        resp = chain.invoke({"query": query},config={"max_retries": 2})
        return {"verdict": resp.verdict}

    def router(self, state: State) -> str:
        return "create_tool_call" if state["verdict"].lower() == 'safe' else "permission_denied"

    def permission_denied(self, state: State) -> State:
        if state['verdict'].lower() == 'unsafe':
            msg = AIMessage(content="I am not allowed to perform this action")
        elif state['verdict'].lower() == 'greeting':
            msg = AIMessage(content="Hello! How can I assist you with SQL today?")
        else:
            msg = AIMessage(content="Unknown verdict encountered.")
        return {"messages": state["messages"] + [msg]}


    def create_tool_call(self, state: State) -> State:
        raw_query = state['messages'][-1].content.strip().removeprefix('```sql').removesuffix('```').strip()
        return {
            "messages": state['messages'] + [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": self.sql_tool.name,
                        "args": {"raw_query": raw_query},
                        "id": "forced_call_001"
                    }]
                )
            ]
        }

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(State)
        graph.add_node("get_schema", self.get_schema)
        graph.add_node("model", self.model)
        graph.add_node("query_validator", self.query_validator)
        graph.add_node("create_tool_call", self.create_tool_call)
        graph.add_node("execute_sql", ToolNode([self.sql_tool]))
        graph.add_node("permission_denied", self.permission_denied)

        graph.set_entry_point("get_schema")
        graph.add_edge("get_schema", "model")
        graph.add_edge("model", "query_validator")
        graph.add_conditional_edges("query_validator", self.router)
        graph.add_edge("create_tool_call", "execute_sql")
        graph.add_edge("execute_sql", END)
        graph.add_edge("permission_denied", END)
        
        
        return graph.compile(checkpointer=self.checkpointer)

    def get_conversation_history(self, thread_id: str):
        """Retrieve the complete conversation history for a thread"""
        
        checkpoint = self.checkpointer.get({"configurable": {"thread_id": thread_id}})
        
        if not checkpoint or "channel_values" not in checkpoint:

            return []
            
        # Extract messages from the checkpoint
        state = checkpoint["channel_values"]
        messages = state.get("messages", [])
        
        formatted_history = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted_history.append({
                    "type": "user_message",
                    "content": msg.content,
                    "timestamp": msg.additional_kwargs.get("timestamp", "")
                })
            elif isinstance(msg, ToolMessage):
                    formatted_history.append({
                        "type": "Tool_message",
                        "content": msg.content,
                        "timestamp": msg.additional_kwargs.get("timestamp", ""),
                    })
                
        
        return formatted_history

    def run(self, user_input: str, thread_id: Optional[str] = None) -> Dict:
       
        input_state = {
            "messages": [HumanMessage(content=user_input)],
            "schema": '',
            "verdict": '',
            "generated_sql": []
        }

        if not thread_id:
            thread_id = str(uuid.uuid4())

        result = self.graph.invoke(input_state, config={"configurable": {"thread_id": thread_id}})
        
        return {
            "response": result["messages"][-1].content,
            "thread_id": thread_id,
            "generated_sql":result['generated_sql'][-1].content
        }



 