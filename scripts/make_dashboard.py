"""Write a static copy of the dashboard to output/dashboard.html (no server needed). Usage: python scripts/make_dashboard.py [YYYY-MM-DD]"""
import sys, os; sys.path.insert(0, ".")
from rtoguard import data, dashboard
from rtoguard.engine import Engine
df, _ = data.load_orders()
model_path = "output/model_backtest.json" if os.path.exists("output/model_backtest.json") else "config/model.json"
html = dashboard.render(Engine(model_path=model_path), df, sys.argv[1] if len(sys.argv) > 1 else None)
open("output/dashboard.html", "w").write(html); print("wrote output/dashboard.html")
