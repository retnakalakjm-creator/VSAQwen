from evidence.profiles import EVIDENCE_REGISTRY
from models import BackgroundContext, EvidenceCode, StructuralPattern, TrendDirection, TrendState


class WeightCalculator:

    @staticmethod
    def calculate(
        code: EvidenceCode,
        ctx: BackgroundContext,
        quality: float = 1.0,
    ) -> float:
        match code:
            case EvidenceCode.EFFORT_RESULT:
                return 0.0
            case EvidenceCode.EFFORT_GT_RESULT:
                return 0.0
            case EvidenceCode.RESULT_GT_EFFORT:
                return 0.0
            case EvidenceCode.ABSORPTION:
                return 0.0
            case EvidenceCode.DEMAND_DRYING_UP:
                return 0.0
            case EvidenceCode.NO_DEMAND:
                return WeightCalculator._no_demand_weight(ctx)
            case EvidenceCode.NO_SUPPLY:
                return WeightCalculator._no_supply_weight(ctx)
            case EvidenceCode.TEST:
                return WeightCalculator._test_weight(ctx)
            case EvidenceCode.UPTHRUST:
                return WeightCalculator._upthrust_weight(ctx)
            case EvidenceCode.SHAKEOUT:
                return WeightCalculator._shakeout_weight(ctx, quality=quality)
            case EvidenceCode.BUYING_CLIMAX:
                return WeightCalculator._buying_climax_weight(ctx)
            case EvidenceCode.SELLING_CLIMAX:
                return WeightCalculator._selling_climax_weight(ctx)
            case EvidenceCode.SUPPLY_COMING_IN:
                return WeightCalculator._supply_coming_in_weight(ctx)
            case _:
                return 1.00

    @staticmethod
    def _environment_adjustment(expected_bullish: bool, ctx: BackgroundContext) -> float:
        if expected_bullish:
            return 0.30 if ctx.is_bullish_environment() else -0.30
        return 0.30 if ctx.is_bearish_environment() else -0.30

    @staticmethod
    def _clamp(weight: float) -> float:
        return max(0.30, min(2.00, weight))

    @staticmethod
    def _structure_adjustment(progression: StructuralPattern) -> float:
        match progression:
            case StructuralPattern.IMPROVING:
                return 0.30
            case StructuralPattern.STABLE:
                return 0.00
            case StructuralPattern.WEAKENING:
                return -0.20
            case StructuralPattern.BREAKING:
                return -0.40
            case _:
                return 0.00

    @staticmethod
    def _directional_structure_adjustment(expected_bullish: bool, progression: StructuralPattern) -> float:
        match progression:
            case StructuralPattern.IMPROVING:
                return 0.30 if expected_bullish else -0.30
            case StructuralPattern.STABLE:
                return 0.00
            case StructuralPattern.WEAKENING:
                return -0.20 if expected_bullish else 0.20
            case StructuralPattern.BREAKING:
                return -0.40 if expected_bullish else 0.40
            case _:
                return 0.00

    @staticmethod
    def _stopping_adjustment(score: float) -> float:
        if score >= 0.80:
            return 0.40
        if score >= 0.60:
            return 0.20
        if score >= 0.40:
            return 0.10
        return 0.00

    @staticmethod
    def _climactic_adjustment(score: float) -> float:
        if score >= 0.80:
            return 0.40
        if score >= 0.60:
            return 0.20
        if score >= 0.40:
            return 0.10
        return 0.00

    @staticmethod
    def _no_supply_trend_adjustment(state: TrendState) -> float:
        match state:
            case TrendState.HEALTHY | TrendState.CORRECTING | TrendState.EXHAUSTED:
                return 0.20
            case TrendState.DEVELOPING:
                return 0.10
            case TrendState.REVERSING:
                return -0.30
            case _:
                return 0.00

    @staticmethod
    def _no_demand_trend_adjustment(direction: TrendDirection, state: TrendState) -> float:
        if direction == TrendDirection.UP:
            match state:
                case TrendState.HEALTHY:
                    return -0.20
                case TrendState.DEVELOPING:
                    return -0.10
                case TrendState.CORRECTING:
                    return 0.10
                case TrendState.EXHAUSTED:
                    return 0.20
                case TrendState.REVERSING:
                    return 0.30
                case _:
                    return 0.00
        if direction == TrendDirection.DOWN:
            match state:
                case TrendState.HEALTHY | TrendState.CORRECTING | TrendState.EXHAUSTED:
                    return 0.20
                case TrendState.DEVELOPING:
                    return 0.10
                case TrendState.REVERSING:
                    return -0.10
                case _:
                    return 0.00
        return 0.00

    @staticmethod
    def _test_trend_adjustment(direction: TrendDirection, state: TrendState) -> float:
        if direction == TrendDirection.UP:
            match state:
                case TrendState.DEVELOPING:
                    return 0.10
                case TrendState.HEALTHY:
                    return 0.20
                case TrendState.CORRECTING:
                    return 0.30
                case TrendState.EXHAUSTED:
                    return -0.20
                case TrendState.REVERSING:
                    return -0.30
                case _:
                    return 0.00
        if direction == TrendDirection.DOWN:
            match state:
                case TrendState.DEVELOPING:
                    return -0.10
                case TrendState.HEALTHY:
                    return -0.20
                case TrendState.CORRECTING:
                    return -0.30
                case TrendState.EXHAUSTED:
                    return 0.20
                case TrendState.REVERSING:
                    return 0.30
                case _:
                    return 0.00
        return 0.00

    @staticmethod
    def _shakeout_trend_adjustment(direction: TrendDirection, state: TrendState) -> float:
        if direction == TrendDirection.UP:
            match state:
                case TrendState.DEVELOPING:
                    return 0.00
                case TrendState.HEALTHY:
                    return 0.10
                case TrendState.CORRECTING:
                    return 0.30
                case TrendState.EXHAUSTED:
                    return 0.20
                case TrendState.REVERSING:
                    return -0.30
                case _:
                    return 0.00
        if direction == TrendDirection.DOWN:
            match state:
                case TrendState.DEVELOPING:
                    return 0.00
                case TrendState.HEALTHY:
                    return -0.10
                case TrendState.CORRECTING:
                    return 0.30
                case TrendState.EXHAUSTED:
                    return 0.20
                case TrendState.REVERSING:
                    return 0.30
                case _:
                    return 0.00
        return 0.00

    @staticmethod
    def _upthrust_trend_adjustment(direction: TrendDirection, state: TrendState) -> float:
        if direction == TrendDirection.UP:
            match state:
                case TrendState.DEVELOPING:
                    return 0.00
                case TrendState.HEALTHY:
                    return -0.20
                case TrendState.CORRECTING:
                    return 0.10
                case TrendState.EXHAUSTED | TrendState.REVERSING:
                    return 0.30
                case _:
                    return 0.00
        if direction == TrendDirection.DOWN:
            match state:
                case TrendState.DEVELOPING:
                    return 0.00
                case TrendState.HEALTHY:
                    return 0.10
                case TrendState.CORRECTING:
                    return 0.30
                case TrendState.EXHAUSTED:
                    return 0.20
                case TrendState.REVERSING:
                    return -0.30
                case _:
                    return 0.00
        return 0.00

    @staticmethod
    def _buying_climax_trend_adjustment(state: TrendState) -> float:
        match state:
            case TrendState.EXHAUSTED | TrendState.REVERSING:
                return 0.30
            case TrendState.CORRECTING:
                return 0.10
            case TrendState.HEALTHY | TrendState.DEVELOPING:
                return 0.00
            case _:
                return 0.00

    @staticmethod
    def _selling_climax_trend_adjustment(state: TrendState) -> float:
        return WeightCalculator._buying_climax_trend_adjustment(state)

    @staticmethod
    def _supply_coming_in_trend_adjustment(direction: TrendDirection, state: TrendState) -> float:
        if direction == TrendDirection.UP:
            match state:
                case TrendState.DEVELOPING | TrendState.HEALTHY:
                    return 0.00
                case TrendState.CORRECTING:
                    return 0.20
                case TrendState.EXHAUSTED | TrendState.REVERSING:
                    return 0.30
                case _:
                    return 0.00
        if direction == TrendDirection.DOWN:
            match state:
                case TrendState.DEVELOPING:
                    return 0.00
                case TrendState.HEALTHY:
                    return 0.10
                case TrendState.CORRECTING | TrendState.EXHAUSTED:
                    return 0.30
                case TrendState.REVERSING:
                    return 0.00
                case _:
                    return 0.00
        return 0.00

    @staticmethod
    def _buying_climax_weight(ctx: BackgroundContext) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bullish_environment() else -0.30
        weight += WeightCalculator._buying_climax_trend_adjustment(ctx.trend.state)
        weight += WeightCalculator._structure_adjustment(ctx.structural_pattern)
        evaluation = ctx.structural_swings[-1].evaluation
        weight += WeightCalculator._climactic_adjustment(evaluation.smart_money.climactic_volume)
        return max(0.50, min(weight, 2.00))

    @staticmethod
    def _selling_climax_weight(ctx: BackgroundContext) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bearish_environment() else -0.30
        weight += WeightCalculator._selling_climax_trend_adjustment(ctx.trend.state)
        weight += WeightCalculator._structure_adjustment(ctx.structural_pattern)
        evaluation = ctx.structural_swings[-1].evaluation
        weight += WeightCalculator._climactic_adjustment(evaluation.smart_money.climactic_volume)
        return max(0.50, min(weight, 2.00))

    @staticmethod
    def _no_supply_weight(ctx: BackgroundContext) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bearish_environment() else -0.30
        weight += WeightCalculator._no_supply_trend_adjustment(ctx.trend.state)
        weight += WeightCalculator._structure_adjustment(ctx.structural_pattern)
        evaluation = ctx.latest_professional_evaluation
        if evaluation is not None:
            weight += WeightCalculator._stopping_adjustment(evaluation.smart_money.stopping_volume)
        return max(0.50, min(weight, 2.00))

    @staticmethod
    def _test_weight(ctx: BackgroundContext) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bearish_environment() else -0.30
        weight += WeightCalculator._test_trend_adjustment(ctx.trend.direction, ctx.trend.state)
        weight += WeightCalculator._structure_adjustment(ctx.structural_pattern)
        evaluation = ctx.latest_professional_evaluation
        if evaluation is not None:
            weight += WeightCalculator._stopping_adjustment(evaluation.smart_money.stopping_volume)
        return max(0.50, min(weight, 2.00))

    @staticmethod
    def _shakeout_weight(ctx: BackgroundContext, quality: float = 1.0) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bearish_environment() else 0.00
        weight += WeightCalculator._shakeout_trend_adjustment(ctx.trend.direction, ctx.trend.state)
        weight += WeightCalculator._directional_structure_adjustment(True, ctx.structural_pattern)
        evaluation = ctx.latest_professional_evaluation
        if evaluation is not None:
            weight += WeightCalculator._stopping_adjustment(evaluation.smart_money.stopping_volume)
        weight = max(0.50, min(weight, 2.00)) * quality
        return max(0.00, min(weight, 2.00))

    @staticmethod
    def _upthrust_weight(ctx: BackgroundContext) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bullish_environment() else 0.00
        weight += WeightCalculator._upthrust_trend_adjustment(ctx.trend.direction, ctx.trend.state)
        weight += WeightCalculator._directional_structure_adjustment(False, ctx.structural_pattern)
        evaluation = ctx.latest_professional_evaluation
        if evaluation is not None:
            weight += WeightCalculator._climactic_adjustment(evaluation.smart_money.climactic_volume)
        return max(0.50, min(weight, 2.00))

    @staticmethod
    def _supply_coming_in_weight(ctx: BackgroundContext) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bearish_environment() else -0.30
        weight += WeightCalculator._supply_coming_in_trend_adjustment(ctx.trend.direction, ctx.trend.state)
        weight += WeightCalculator._structure_adjustment(ctx.structural_pattern)
        evaluation = ctx.latest_professional_evaluation
        if evaluation is not None:
            weight += WeightCalculator._climactic_adjustment(evaluation.smart_money.climactic_volume)
        return max(0.50, min(weight, 2.00))

    @staticmethod
    def _no_demand_weight(ctx: BackgroundContext) -> float:
        weight = 1.0
        weight += 0.30 if ctx.is_bullish_environment() else -0.30
        weight += WeightCalculator._no_demand_trend_adjustment(ctx.trend.direction, ctx.trend.state)
        weight += WeightCalculator._structure_adjustment(ctx.structural_pattern)
        evaluation = ctx.latest_professional_evaluation
        if evaluation is not None:
            weight += WeightCalculator._stopping_adjustment(evaluation.smart_money.stopping_volume)
        return max(0.50, min(weight, 2.00))
