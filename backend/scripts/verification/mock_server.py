from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/legislation/{jurisdiction}")
def get_legislation(jurisdiction: str):
    return {
        "jurisdiction": jurisdiction,
        "count": 1,
        "legislation": [
            {
                "id": 1,
                "bill_number": "25-1234",
                "title": "Ordinance Amending Municipal Code",
                "status": "Active",
                "impacts": [
                    {
                        "impact_description": "Increases development costs by 5%",
                        "relevant_clause": "Sec 4.2",
                        "confidence_score": 0.9,
                        "p50": 1500000
                    }
                ]
            }
        ]
    }

@app.get("/admin/traces")
def list_traces():
    return ["trace_" + str(uuid.uuid4())]

@app.get("/admin/traces/{query_id}")
def get_trace(query_id: str):
    return [
        {
            "tool": "TaskPlanner",
            "task_id": "t1",
            "result": {"plan": "execute"},
            "args": {"query": "Analyze"},
            "timestamp": time.time() * 1000
        },
        {
            "tool": "WebSearch",
            "task_id": "t2",
            "result": {"status": "found"},
            "args": {"query": "housing"},
            "timestamp": time.time() * 1000 + 100
        }
    ]

@app.post("/scrape/{jurisdiction}")
def scrape(jurisdiction: str):
    return {"status": "success", "processed": 1}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
