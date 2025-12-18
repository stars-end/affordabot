from typing import Optional, Dict, Any

class PluralClient:
    """
    Client for Plural Policy API (Mocked for MVP).
    """
    def __init__(self, api_key: str = "mock_key"):
        self.api_key = api_key
        self.base_url = "https://api.pluralpolicy.com/v1"

    async def get_bill(self, jurisdiction: str, bill_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetch bill details from Plural.
        """
        # Mock response
        if jurisdiction == "california" and bill_number == "SB-423":
            return {
                "bill_number": "SB-423",
                "title": "Streamlined housing approvals: multifamily housing developments",
                "status": "Chaptered",
                "text": "Existing law, the Planning and Zoning Law, requires a city or county to...",
                "source": "plural"
            }
        return None
