import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

WEBHOOK_SECRET = "my_secret_token_123"
MAX_DOLLAR_RISK = 50.0  # Max loss per trade in dollars

class AlertPayload(BaseModel):
    secret: str
    ticker: str
    action: str
    entry: float
    stop: float
    target: float

@app.get("/")
def home():
    return {"status": "Bridge is running 24/7"}

@app.post("/webhook")
async def trade_webhook(payload: AlertPayload):
    # Security check
    if payload.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

    per_share_risk = payload.entry - payload.stop
    if per_share_risk <= 0:
        raise HTTPException(status_code=400, detail="Stop must be below entry")

    # Position sizing: Max Risk / Risk per share
    shares = int(MAX_DOLLAR_RISK // per_share_risk)
    total_cost = round(shares * payload.entry, 2)

    print(f"\n[ALERT] {payload.action} {shares} {payload.ticker} @ ${payload.entry}")
    print(f"Stop: ${payload.stop} | Target: ${payload.target} | Total Cost: ${total_cost}\n")

    return {
        "status": "PROCESSED",
        "ticker": payload.ticker,
        "shares": shares,
        "cost": total_cost
    }
  
