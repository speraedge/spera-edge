"""Minimal independent Cloudflare D1 client for SPERA EDGE.

All credentials are EDGE-specific. This module never references SPERA source credentials.
"""
import os
import requests


class D1ConstraintError(RuntimeError):
    """A recognized database integrity rejection, not an HTTP/network failure."""


def d1_query(sql, params=(), *, account_id=None, database_id=None, token=None, session=None):
    account_id=account_id or os.getenv("EDGE_CF_ACCOUNT_ID")
    database_id=database_id or os.getenv("EDGE_D1_DATABASE_ID")
    token=token or os.getenv("EDGE_CF_API_TOKEN")
    if not all((account_id,database_id,token)):
        raise RuntimeError("EDGE D1 credentials not configured")
    url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"
    response=(session or requests).post(url,headers={
        "Authorization":f"Bearer {token}","Content-Type":"application/json"},
        json={"sql":sql,"params":list(params)},timeout=40)
    payload=response.json()
    if not payload.get("success") or not payload.get("result") or any(not x.get("success") for x in payload["result"]):
        messages = [str(error.get('message', '')) for error in (payload.get('errors') or []) if isinstance(error, dict)]
        messages += [str(result.get('error', '')) for result in (payload.get('result') or []) if isinstance(result, dict)]
        if any('Private records are append-only' in message for message in messages):
            raise D1ConstraintError('Private append-only constraint enforced')
        response.raise_for_status()
        raise RuntimeError("EDGE D1 query rejected")
    response.raise_for_status()
    return payload["result"][0].get("results",[])
