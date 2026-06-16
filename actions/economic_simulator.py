import pandas as pd
import numpy as np

class EconomicBacktester:
    def backtest_discovery(self, discovery_summary):
        """Simulates the economic impact of a discovery."""
        print("📈 ECONOMIC BACKTESTER: Running simulation...")
        
        # Simple synthetic backtest: generate a 30-day efficiency curve
        days = 30
        baseline = np.random.normal(100, 5, days)
        # discovery_impact is derived from the 'confidence' of the synthesis (mocked here)
        discovery_impact = np.random.normal(1.05, 0.02, days) 
        
        optimized = baseline * discovery_impact
        
        total_gain = (optimized.sum() - baseline.sum()) / baseline.sum() * 100
        
        return {
            "total_gain_percent": total_gain,
            "max_drawdown": (baseline - optimized).max(),
            "viability_score": 1.0 if total_gain > 2.0 else 0.0
        }
