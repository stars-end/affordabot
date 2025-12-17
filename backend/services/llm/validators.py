from typing import List
import re

class CitationValidator:
    """
    Validates that citations in the analysis actually exist in the source text.
    Programmatic check to reduce hallucinations.
    """
    
    @staticmethod
    def validate_citations(analysis_text: str, source_text: str) -> List[str]:
        """
        Returns a list of warning messages for invalid citations.
        Assumes citations are in format [Source X] or similar.
        """
        warnings = []
        # Naive check for now: Verify quoted text exists in source
        # This is a placeholder for more complex logic (fuzzy matching)
        
        quotes = re.findall(r'"([^"]+)"', analysis_text)
        for quote in quotes:
            if len(quote) > 20 and quote not in source_text:
                warnings.append(f"Quote not found in source: \"{quote[:50]}...\"")
                
        return warnings
