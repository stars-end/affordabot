from fastapi import FastAPI
from services.scraper.saratoga import SaratogaScraper
from services.llm.analyzer import LegislationAnalyzer

app = FastAPI(title="AffordaBot API")

@app.get("/")
async def root():
    return {"message": "Welcome to AffordaBot API"}

@app.post("/scrape/saratoga")
async def trigger_saratoga_scrape():
    # 1. Scrape
    scraper = SaratogaScraper()
    bills = await scraper.scrape()
    
    # 2. Analyze (just the first one for MVP testing)
    if not bills:
        return {"status": "no bills found"}
        
    bill = bills[0]
    analyzer = LegislationAnalyzer()
    
    try:
        analysis = await analyzer.analyze(
            bill_text=bill.text,
            bill_number=bill.bill_number,
            jurisdiction="City of Saratoga"
        )
        return {
            "status": "success", 
            "bill": bill,
            "analysis": analysis
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "bill": bill
        }
