import asyncio
import sys
import os
import logging

# Ensure we can import backend modules
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.services.llm.pipeline import DualModelAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_pipeline():
    print("🚀 Starting Full Pipeline Test...")
    
    analyzer = DualModelAnalyzer()
    
    # Mock bill for testing
    bill_text = """
    The City Council of San Jose hereby ordains:
    Section 1. Rent Stabilization.
    Annual rent increases for all multi-family dwelling units built before 1995 shall be capped at 3% or the CPI, whichever is lower.
    Landlords may pass through 50% of capital improvement costs, amortized over 10 years.
    """
    bill_number = "TEST-BILL-2025"
    jurisdiction = "San Jose"
    
    print(f"\nAnalyzing {bill_number}...")
    try:
        result = await analyzer.analyze(bill_text, bill_number, jurisdiction)
        
        print("\n✅ Analysis Complete!")
        print(f"Summary: {result.summary[:100]}...")
        print(f"Impacts Found: {len(result.impacts)}")
        for impact in result.impacts:
            print(f" - {impact.description} (${impact.p50}/yr)")
            
    except Exception as e:
        print(f"❌ Pipeline Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipeline())
