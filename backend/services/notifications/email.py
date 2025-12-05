import os
from typing import List, Dict, Any
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import logging

logger = logging.getLogger(__name__)

class EmailNotificationService:
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("FROM_EMAIL", "notifications@affordabot.ai")
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            logger.warning("SendGrid API key not set. Email notifications disabled.")
        else:
            self.client = SendGridAPIClient(self.api_key)
    
    async def send_high_impact_alert(
        self,
        to_email: str,
        jurisdiction: str,
        bill_number: str,
        bill_title: str,
        total_impact: float,
        impacts: List[Dict[str, Any]]
    ):
        """Send alert for high-impact bills (>$500/year)."""
        if not self.enabled:
            logger.info(f"Email disabled. Would send alert to {to_email} for {bill_number}")
            return
        
        subject = f"🚨 High Impact Bill Alert: {bill_number} (${total_impact:,.0f}/year)"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1e40af;">New High-Impact Legislation Detected</h2>
            
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0;">{bill_title}</h3>
                <p><strong>Jurisdiction:</strong> {jurisdiction}</p>
                <p><strong>Bill Number:</strong> {bill_number}</p>
                <p><strong>Estimated Annual Impact:</strong> <span style="color: #dc2626; font-size: 24px; font-weight: bold;">${total_impact:,.0f}</span></p>
            </div>
            
            <h3>Impact Breakdown</h3>
            <ul>
        """
        
        for impact in impacts:
            html_content += f"""
                <li style="margin-bottom: 15px;">
                    <strong>{impact.get('description', 'N/A')}</strong><br>
                    <span style="color: #6b7280;">Median Cost: ${impact.get('p50', 0):,.0f}/year</span><br>
                    <span style="color: #6b7280;">Confidence: {int(impact.get('confidence_factor', 0) * 100)}%</span>
                </li>
            """
        
        html_content += f"""
            </ul>
            
            <div style="margin-top: 30px; padding: 20px; background: #eff6ff; border-radius: 8px;">
                <p style="margin: 0;"><strong>What can you do?</strong></p>
                <p>Visit <a href="https://affordabot.ai/bill/{jurisdiction}/{bill_number}" style="color: #1e40af;">affordabot.ai</a> to:</p>
                <ul>
                    <li>View detailed impact analysis</li>
                    <li>Adjust assumptions with interactive sliders</li>
                    <li>Review evidence and sources</li>
                    <li>Share with your community</li>
                </ul>
            </div>
            
            <p style="color: #6b7280; font-size: 12px; margin-top: 30px;">
                You're receiving this because you subscribed to AffordaBot alerts for {jurisdiction}.
                <a href="https://affordabot.ai/unsubscribe?email={to_email}" style="color: #6b7280;">Unsubscribe</a>
            </p>
        </body>
        </html>
        """
        
        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        try:
            response = self.client.send(message)
            logger.info(f"Email sent to {to_email}: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_weekly_digest(
        self,
        to_email: str,
        jurisdiction: str,
        bills: List[Dict[str, Any]]
    ):
        """Send weekly digest of all new bills."""
        if not self.enabled or not bills:
            return
        
        subject = f"📊 Weekly Legislation Digest: {jurisdiction}"
        
        total_impact = sum(bill.get('total_impact', 0) for bill in bills)
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1e40af;">Your Weekly Legislation Digest</h2>
            <p>{len(bills)} new bills analyzed for {jurisdiction} this week.</p>
            
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; color: #6b7280;">Total Estimated Impact</p>
                <p style="font-size: 32px; font-weight: bold; color: #1e40af; margin: 10px 0;">${total_impact:,.0f}/year</p>
            </div>
            
            <h3>Bills This Week</h3>
        """
        
        for bill in sorted(bills, key=lambda x: x.get('total_impact', 0), reverse=True):
            html_content += f"""
            <div style="border-left: 3px solid #3b82f6; padding-left: 15px; margin-bottom: 20px;">
                <h4 style="margin: 0;">{bill.get('bill_number')}: {bill.get('title', 'Untitled')[:100]}</h4>
                <p style="color: #dc2626; font-weight: bold; margin: 5px 0;">${bill.get('total_impact', 0):,.0f}/year</p>
                <p style="color: #6b7280; font-size: 14px; margin: 5px 0;">{bill.get('impact_count', 0)} impacts identified</p>
            </div>
            """
        
        html_content += """
            <div style="text-align: center; margin-top: 30px;">
                <a href="https://affordabot.ai" style="background: #1e40af; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    View Full Dashboard
                </a>
            </div>
        </body>
        </html>
        """
        
        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        try:
            response = self.client.send(message)
            logger.info(f"Weekly digest sent to {to_email}: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send weekly digest to {to_email}: {e}")
            return False
