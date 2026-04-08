# Legislative Bill Scraper

Build a scraper module for a specific jurisdiction that fetches active legislative bills from a public government data source and returns them as structured objects.

## Capabilities

### Bill scraping

The scraper must retrieve a list of bills from a government data source.

- Fetching a California-style data source returns a list of structured bill objects with `bill_number`, `title`, `text`, `introduced_date`, and `status` fields [@test](./tests/test_scrape.py)
- Bills without text available have `text` set to `None` rather than raising an error [@test](./tests/test_no_text.py)
- The scraper exposes a `check_health()` method that returns `True` when the upstream source is reachable and `False` otherwise [@test](./tests/test_health.py)
- An empty list is returned (not an exception) when the source returns no bills [@test](./tests/test_empty.py)

## Implementation

[@generates](./src/scraper.py)

## API

```python { #api }
from datetime import date
from typing import List, Optional
from pydantic import BaseModel

class ScrapedBill(BaseModel):
    bill_number: str
    title: str
    text: Optional[str] = None
    introduced_date: Optional[date] = None
    status: Optional[str] = None
    raw_html: Optional[str] = None

class LegislatureScraper:
    jurisdiction_name: str

    async def scrape(self) -> List[ScrapedBill]: ...
    async def check_health(self) -> bool: ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides the `ScrapedBill` data model and `BaseScraper` abstract base class that jurisdiction scrapers must subclass.

[@satisfied-by](affordabot)
