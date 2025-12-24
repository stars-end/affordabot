"""
Visual E2E Stories for Affordabot Admin UI.

Defines 10 stories for browser-based verification with screenshots.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Story:
    """A visual E2E test story."""
    id: str
    name: str
    url: str
    wait_for: str  # CSS selector to wait for before screenshot
    assertions: List[Tuple[str, str, str]] = field(default_factory=list)  # (selector, op, value)
    screenshot_name: str = ""
    description: str = ""
    
    def __post_init__(self):
        if not self.screenshot_name:
            self.screenshot_name = f"{self.id}_{self.name.lower().replace(' ', '_')}.webp"


# Affordabot Admin UI Stories
STORIES = [
    Story(
        id="A1",
        name="Admin Dashboard Loads",
        url="/admin",
        wait_for="h1",
        assertions=[
            ("h1", "contains", "Admin"),
            (".stats-card, .MuiCard-root", "count_gte", "1"),
        ],
        description="Verify admin dashboard loads with stats cards"
    ),
    Story(
        id="A2",
        name="Jurisdictions Table",
        url="/admin/jurisdictions",
        wait_for="table, .MuiTable-root",
        assertions=[
            ("table, .MuiTable-root", "visible", "true"),
            ("tr, .MuiTableRow-root", "count_gte", "2"),
        ],
        description="Verify jurisdictions table displays with data"
    ),
    Story(
        id="A3",
        name="Scrapes Table",
        url="/admin/scrapes",
        wait_for="table, .MuiTable-root",
        assertions=[
            ("table, .MuiTable-root", "visible", "true"),
        ],
        description="Verify scrapes table shows recent scrape jobs"
    ),
    Story(
        id="A4",
        name="Discovery Controls",
        url="/admin",
        wait_for="button",
        assertions=[
            ("button", "count_gte", "1"),
        ],
        description="Verify discovery action buttons are present"
    ),
    Story(
        id="A5",
        name="Scrape Controls",
        url="/admin/scrapes",
        wait_for="button",
        assertions=[
            ("button", "count_gte", "1"),
        ],
        description="Verify scrape action buttons are present"
    ),
    Story(
        id="A6",
        name="Job Queue Status",
        url="/admin/jobs",
        wait_for=".job-status, .MuiChip-root, table",
        assertions=[
            (".job-status, .MuiChip-root, table", "visible", "true"),
        ],
        description="Verify job queue displays status indicators"
    ),
    Story(
        id="A7",
        name="Document Chunks View",
        url="/admin/chunks",
        wait_for="table, .chunk-list, .MuiTable-root",
        assertions=[
            ("table, .chunk-list, .MuiTable-root", "visible", "true"),
        ],
        description="Verify document chunks are displayed"
    ),
    Story(
        id="A8",
        name="RAG Query Interface",
        url="/admin/rag",
        wait_for="input, textarea, .query-input",
        assertions=[
            ("input, textarea, .query-input", "visible", "true"),
        ],
        description="Verify RAG query input is available"
    ),
    Story(
        id="A9",
        name="Sources Panel",
        url="/admin/rag",
        wait_for=".sources, .citations, .MuiList-root",
        assertions=[],
        description="Verify sources/citations panel exists"
    ),
    Story(
        id="A10",
        name="Error Handling",
        url="/admin/nonexistent",
        wait_for="body",
        assertions=[
            ("body", "no_crash", "true"),
        ],
        description="Verify graceful error handling on invalid routes"
    ),
]


def get_story(story_id: str) -> Story:
    """Get a story by ID."""
    for story in STORIES:
        if story.id == story_id:
            return story
    raise ValueError(f"Story {story_id} not found")


def get_all_stories() -> List[Story]:
    """Get all stories."""
    return STORIES
