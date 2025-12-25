#!/usr/bin/env python3
"""
Screenshot Utility for Glass Box Verification.

Captures terminal output and optionally browser screenshots for verification evidence.
Designed to work headless in CI environments.
"""

from datetime import datetime
from pathlib import Path

# Default artifacts directory
ARTIFACTS_DIR = Path(__file__).parent.parent.parent.parent / "artifacts" / "verification"


def ensure_artifacts_dir(custom_dir: str = None) -> Path:
    """Ensure the artifacts directory exists."""
    artifacts_path = Path(custom_dir) if custom_dir else ARTIFACTS_DIR
    artifacts_path.mkdir(parents=True, exist_ok=True)
    return artifacts_path


def capture_text_screenshot(
    phase_name: str,
    content: str,
    status: str = "success",
    artifacts_dir: str = None
) -> str:
    """
    Save text content as a 'screenshot' file (markdown format for readability).
    
    Args:
        phase_name: Name of the phase/story (e.g., 'phase_1_discovery')
        content: Text content to capture
        status: 'success', 'warning', or 'failure'
        artifacts_dir: Optional custom directory
        
    Returns:
        Path to the saved file
    """
    artifacts_path = ensure_artifacts_dir(artifacts_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Sanitize phase name for filename
    safe_name = phase_name.lower().replace(" ", "_").replace("/", "_").replace(":", "_")
    filename = f"{safe_name}_{timestamp}.md"
    filepath = artifacts_path / filename
    
    # Create markdown content with status indicator
    status_emoji = {"success": "✅", "warning": "⚠️", "failure": "❌"}.get(status, "📋")
    
    markdown_content = f"""# {status_emoji} {phase_name}

**Captured**: {datetime.now().isoformat()}
**Status**: {status.upper()}

## Output

```
{content}
```
"""
    
    filepath.write_text(markdown_content)
    print(f"   📸 Screenshot saved: {filepath}")
    return str(filepath)


def capture_browser_screenshot(
    phase_name: str,
    url: str = None,
    page_content: str = None,
    artifacts_dir: str = None
) -> str:
    """
    Capture a browser screenshot using Playwright.
    Falls back to text capture if Playwright is unavailable.
    
    Args:
        phase_name: Name of the phase/story
        url: URL to navigate to (optional)
        page_content: HTML content to render (optional)
        artifacts_dir: Optional custom directory
        
    Returns:
        Path to the saved screenshot
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("   ⚠️  Playwright not installed, falling back to text capture")
        return capture_text_screenshot(
            phase_name,
            f"URL: {url}\n\nPlaywright not available for browser capture.",
            "warning",
            artifacts_dir
        )
    
    artifacts_path = ensure_artifacts_dir(artifacts_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = phase_name.lower().replace(" ", "_").replace("/", "_").replace(":", "_")
    filename = f"{safe_name}_{timestamp}.png"
    filepath = artifacts_path / filename
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            if url:
                page.goto(url, timeout=30000)
            elif page_content:
                page.set_content(page_content)
            else:
                page.set_content("<html><body><h1>No content provided</h1></body></html>")
            
            page.screenshot(path=str(filepath))
            browser.close()
            
        print(f"   📸 Browser screenshot saved: {filepath}")
        return str(filepath)
        
    except Exception as e:
        print(f"   ⚠️  Browser capture failed: {e}")
        return capture_text_screenshot(
            phase_name,
            f"URL: {url}\n\nBrowser capture failed: {e}",
            "warning",
            artifacts_dir
        )


class VerificationReporter:
    """
    Collects verification results and generates a summary report.
    """
    
    def __init__(self, name: str, artifacts_dir: str = None):
        self.name = name
        self.artifacts_dir = ensure_artifacts_dir(artifacts_dir)
        self.phases = []
        self.start_time = datetime.now()
    
    def add_phase(
        self,
        phase_id: int,
        name: str,
        status: str,
        details: str = "",
        screenshot_path: str = None
    ):
        """Record a phase result."""
        self.phases.append({
            "id": phase_id,
            "name": name,
            "status": status,
            "details": details,
            "screenshot": screenshot_path,
            "timestamp": datetime.now().isoformat()
        })
    
    def generate_report(self) -> str:
        """Generate a markdown summary report."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        passed = sum(1 for p in self.phases if p["status"] == "success")
        failed = sum(1 for p in self.phases if p["status"] == "failure")
        total = len(self.phases)
        
        status_emoji = "✅" if failed == 0 else "❌"
        
        report = f"""# {status_emoji} {self.name} Verification Report

**Generated**: {end_time.isoformat()}
**Duration**: {duration:.2f}s
**Result**: {passed}/{total} phases passed

## Summary

| Phase | Name | Status | Screenshot |
|-------|------|--------|------------|
"""
        
        for p in self.phases:
            status_icon = {"success": "✅", "warning": "⚠️", "failure": "❌"}.get(p["status"], "❓")
            screenshot_link = f"[View]({p['screenshot']})" if p["screenshot"] else "N/A"
            report += f"| {p['id']} | {p['name']} | {status_icon} | {screenshot_link} |\n"
        
        report += "\n## Phase Details\n\n"
        
        for p in self.phases:
            status_icon = {"success": "✅", "warning": "⚠️", "failure": "❌"}.get(p["status"], "❓")
            report += f"""### Phase {p['id']}: {p['name']} {status_icon}

{p['details']}

"""
        
        # Save report
        report_path = self.artifacts_dir / f"{self.name.lower().replace(' ', '_')}_report.md"
        report_path.write_text(report)
        print(f"\n📋 Verification Report: {report_path}")
        
        return str(report_path)


if __name__ == "__main__":
    # Test the utilities
    print("Testing screenshot utilities...")
    
    path = capture_text_screenshot(
        "Test Phase",
        "This is test content\nWith multiple lines",
        "success"
    )
    print(f"Created: {path}")
    
    reporter = VerificationReporter("Test Suite")
    reporter.add_phase(1, "Setup", "success", "Environment verified")
    reporter.add_phase(2, "Test", "failure", "Test failed: assertion error")
    reporter.generate_report()
