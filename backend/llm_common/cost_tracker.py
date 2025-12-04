from __future__ import annotations
from datetime import datetime, date
from typing import Dict, Optional, Any
from pydantic import BaseModel
from .exceptions import BudgetExceededError

class CostMetrics(BaseModel):
    """Cost metrics for a single request."""
    model: str
    step: Optional[str] = None  # "research", "generate", "review"
    cost_usd: float
    tokens_used: Optional[int] = None
    timestamp: datetime = datetime.now()

class CostTracker:
    """
    Track LLM and web search costs.
    
    Features:
    - Daily/monthly budget enforcement
    - Cost breakdown by model and step
    - Alert thresholds
    """
    
    def __init__(
        self,
        supabase_client: Any,
        daily_budget_usd: Optional[float] = None,
        monthly_budget_usd: Optional[float] = None,
        alert_threshold: float = 0.8
    ):
        """
        Initialize cost tracker.
        
        Args:
            supabase_client: Supabase client for cost storage
            daily_budget_usd: Daily budget limit
            monthly_budget_usd: Monthly budget limit
            alert_threshold: Alert when cost reaches this % of budget
        """
        self.supabase = supabase_client
        self.daily_budget = daily_budget_usd
        self.monthly_budget = monthly_budget_usd
        self.alert_threshold = alert_threshold
    
    async def log_cost(self, metrics: CostMetrics):
        """Log cost to database."""
        self.supabase.table('cost_tracking').insert({
            'model': metrics.model,
            'step': metrics.step,
            'cost_usd': metrics.cost_usd,
            'tokens_used': metrics.tokens_used,
            'timestamp': metrics.timestamp.isoformat()
        }).execute()
        
        # Check budget
        await self._check_budget()
    
    async def _check_budget(self):
        """Check if budget limits are exceeded."""
        today = date.today()
        
        # Daily budget check
        if self.daily_budget:
            daily_cost = await self.get_daily_cost(today)
            if daily_cost >= self.daily_budget:
                raise BudgetExceededError(
                    f"Daily budget exceeded: ${daily_cost:.2f} >= ${self.daily_budget:.2f}"
                )
            elif daily_cost >= self.daily_budget * self.alert_threshold:
                print(f"⚠️  Daily budget alert: ${daily_cost:.2f} / ${self.daily_budget:.2f}")
        
        # Monthly budget check
        if self.monthly_budget:
            monthly_cost = await self.get_monthly_cost(today.year, today.month)
            if monthly_cost >= self.monthly_budget:
                raise BudgetExceededError(
                    f"Monthly budget exceeded: ${monthly_cost:.2f} >= ${self.monthly_budget:.2f}"
                )
    
    async def get_daily_cost(self, date: date) -> float:
        """Get total cost for a specific date."""
        result = self.supabase.rpc('get_daily_cost', {'target_date': date.isoformat()}).execute()
        return result.data[0]['total_cost'] if result.data else 0.0
    
    async def get_monthly_cost(self, year: int, month: int) -> float:
        """Get total cost for a specific month."""
        result = self.supabase.rpc('get_monthly_cost', {
            'target_year': year,
            'target_month': month
        }).execute()
        return result.data[0]['total_cost'] if result.data else 0.0
    
    async def get_cost_breakdown(
        self,
        start_date: date,
        end_date: date,
        group_by: str = "model"
    ) -> Dict[str, float]:
        """
        Get cost breakdown by model or step.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            group_by: "model" or "step"
        
        Returns:
            Dict mapping model/step to total cost
        """
        result = self.supabase.rpc('get_cost_breakdown', {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'group_by': group_by
        }).execute()
        
        return {row['group_key']: row['total_cost'] for row in result.data}
