import os
import sys
import time
import json
from typing import Optional

import requests
from sqlalchemy import create_engine, text


def mask(value: Optional[str], keep: int = 4) -> str:
    if not value:
        return "<missing>"
    return value[:keep] + "…" + value[-keep:]


def check_env_vars() -> None:
    print("[1/5] Environment variables:")
    openai_key = os.environ.get("OPENAI_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    database_url = os.environ.get("DATABASE_URL")
    print(f"  OPENAI_API_KEY:    {mask(openai_key)}")
    print(f"  OPENROUTER_API_KEY:{mask(openrouter_key)}")
    print(f"  DATABASE_URL:      {('<set>' if database_url else '<missing>')}\n")


def check_config_keys() -> None:
    print("[1b/5] Config (rag.config) resolution:")
    try:
        from rag.config import OPENAI_API_KEY as C_OPENAI, OPENROUTER_API_KEY as C_OR, DATABASE_URL as C_DB
        print(f"  cfg OPENAI_API_KEY:     {mask(C_OPENAI)}")
        print(f"  cfg OPENROUTER_API_KEY: {mask(C_OR)}")
        print(f"  cfg DATABASE_URL:       {('<set>' if C_DB else '<missing>')}\n")
    except Exception as e:
        print(f"  ERROR importing rag.config: {type(e).__name__}: {e}\n")


def check_db_connection() -> None:
    print("[2/5] Database connectivity:")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("  ERROR: DATABASE_URL is not set")
        return
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            # check tables
            has_chunks = conn.exec_driver_sql(
                "SELECT to_regclass('public.document_chunks') IS NOT NULL"
            ).scalar()
            print(f"  SELECT 1:          ok")
            print(f"  document_chunks:   {'present' if has_chunks else 'missing'}\n")
    except Exception as e:
        print(f"  ERROR connecting to DB: {e}\n")


def check_openai_embeddings() -> None:
    print("[3/5] OpenAI embeddings API:")
    try:
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            try:
                from rag.config import OPENAI_API_KEY as C_OPENAI
                key = C_OPENAI
            except Exception:
                key = None
        client = OpenAI(api_key=key)
        resp = client.embeddings.create(model="text-embedding-3-small", input=["hello"])
        dim = len(resp.data[0].embedding) if resp and resp.data else 0
        print(f"  embeddings ok, dim={dim}\n")
    except Exception as e:
        print(f"  ERROR calling embeddings: {type(e).__name__}: {e}\n")


def check_openrouter_chat() -> None:
    print("[4/5] OpenRouter chat API:")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        try:
            from rag.config import OPENROUTER_API_KEY as C_OR
            api_key = C_OR
        except Exception:
            api_key = None
    if not api_key:
        print("  ERROR: OPENROUTER_API_KEY is not set\n")
        return
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
                "temperature": 0
            },
            timeout=15,
        )
        print(f"  status {r.status_code}")
        if r.status_code >= 400:
            print(f"  body: {r.text[:200]}\n")
        else:
            print("  chat ok\n")
    except Exception as e:
        print(f"  ERROR calling OpenRouter: {type(e).__name__}: {e}\n")


def check_rag_chain() -> None:
    print("[5/5] RAG chain initialization and invoke:")
    try:
        from rag.langchain_rag import get_langchain_rag_system
        rag = get_langchain_rag_system()
        result = rag.invoke("hello", session_id="test_env", k=1)
        keys = list(result.keys())
        print(f"  rag.invoke ok, keys={keys}, answer_len={len(result.get('answer',''))}\n")
    except Exception as e:
        print(f"  ERROR rag chain: {type(e).__name__}: {e}\n")


def main() -> int:
    print("== HiveScribe RAG environment self-test ==\n")
    check_env_vars()
    check_config_keys()
    check_db_connection()
    check_openai_embeddings()
    check_openrouter_chat()
    check_rag_chain()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())



