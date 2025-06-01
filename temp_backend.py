
import sys
sys.path.insert(0, r"C:\Users\zhm_2\Documents\Code\koreader_sync_statistic_analysis")
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)
