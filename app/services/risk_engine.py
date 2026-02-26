class RiskEngine:
    """
    Context-Aware Risk Engine that calculates risk score and levels
    based on real-time aggregated metrics and session configuration.
    """
    
    EXPECTED_MAX_SPEED = {
        "STATIC": 5.0,
        "SLOW": 15.0,
        "NORMAL": 40.0,
        "FAST_FLOW": 80.0,
        "TRANSIT_RUSH": 160.0,
    }

    SENSITIVITY_MULTIPLIERS = {
        "LOW": 0.8,
        "MEDIUM": 1.0,
        "HIGH": 1.2,
        "PARANOID": 1.4,
    }

    CLUSTERING_ADJUSTMENTS = {
        "ALLOWED": 0.6,
        "LIMITED": 0.8,
        "DISCOURAGED": 1.0,
        "NOT_ALLOWED": 1.2,
    }

    GOAL_WEIGHTS = {
        "FLOW": {"motion": 0.4, "density": 0.4, "surge": 0.2},
        "STAY": {"density": 0.5, "motion": 0.2, "surge": 0.3},
        "QUEUE": {"density": 0.5, "surge": 0.4, "motion": 0.1},
        "SECURITY": {"motion": 0.6, "density": 0.2, "surge": 0.2},
        "RESTRICTED": {"motion": 0.7, "surge": 0.3, "density": 0.0},
        "MONITORING": {"motion": 0.3, "density": 0.5, "surge": 0.2},
    }

    @staticmethod
    def _clamp(val, min_val, max_val):
        return max(min_val, min(val, max_val))

    @classmethod
    def calculate_risk(cls, context, metrics):
        """
        Calculate the risk profile given the session config context and aggregated metrics.
        Returns a dictionary with density, motion_score, surge_score, risk_score, risk_level, and risk_flags.
        """
        capacity = max(context.get('capacity', 100), 1)
        flow_type = context.get('flow_type', 'NORMAL')
        sensitivity = context.get('sensitivity', 'MEDIUM')
        clustering = context.get('clustering', 'ALLOWED')
        goal = context.get('goal', 'MONITORING')

        avg_human_count = metrics.get('avg_human_count', 0.0)
        avg_motion_speed = metrics.get('avg_motion_speed', 0.0)
        crowd_growth_rate = metrics.get('crowd_growth_rate', 0.0)

        # 1. Density Score
        density = cls._clamp(avg_human_count / capacity, 0.0, 1.5)

        # 2. Motion Score
        expected_speed = cls.EXPECTED_MAX_SPEED.get(flow_type, 40.0)
        motion_score = cls._clamp(avg_motion_speed / expected_speed, 0.0, 2.0)

        # 3. Surge Score
        surge_score = cls._clamp(abs(crowd_growth_rate) / capacity, 0.0, 1.0)

        # Multipliers
        sens_mult = cls.SENSITIVITY_MULTIPLIERS.get(sensitivity, 1.0)
        clus_adj = cls.CLUSTERING_ADJUSTMENTS.get(clustering, 1.0)

        # Adjusted Density
        density_adjusted = density * clus_adj

        # Goal Weights
        weights = cls.GOAL_WEIGHTS.get(goal, cls.GOAL_WEIGHTS["MONITORING"])
        density_weight = weights.get('density', 0.5)
        motion_weight = weights.get('motion', 0.3)
        surge_weight = weights.get('surge', 0.2)
        
        # Risk Score Calculation
        raw_risk = (
            density_weight * density_adjusted +
            motion_weight * motion_score +
            surge_weight * surge_score
        )
        risk_score = round(cls._clamp(raw_risk * sens_mult, 0.0, 1.0), 4)

        # Risk Levels Maps
        if risk_score <= 0.30:
            risk_level = "NORMAL"
        elif risk_score <= 0.55:
            risk_level = "BUSY"
        elif risk_score <= 0.75:
            risk_level = "WARNING"
        else:
            risk_level = "CRITICAL"

        # Risk Flags
        flags = []
        if density > 0.9:
            flags.append("overcrowding")
        if motion_score > 1.2:
            flags.append("panic_movement")
        if surge_score > 0.5:
            flags.append("sudden_surge")

        return {
            "density": round(density, 4),
            "motion_score": round(motion_score, 4),
            "surge_score": round(surge_score, 4),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_flags": flags
        }
