from models import Swing, SwingHistorySnapshot, SwingProfessionalEvaluation, SwingProfessionalScore


def print_professional_score(
    swing: Swing,
    evaluation: SwingProfessionalEvaluation,
) -> None:

    structure = evaluation.structure.score
    snapshot = evaluation.structure.snapshot
    professional = evaluation.professional
    smart_money = evaluation.smart_money
    
    print("=" * 60)

    print(
        f"Week   : {swing.week_beginning}"
    )

    print(
        f"Swing  : {swing.type.name}"
    )

    print(
        f"Price  : {swing.price:.2f}"
    )

    print()

    print("STRUCTURE")
    print("-" * 20)

    print(
        f"Amplitude        : {structure.price:.2f}"
    )

    print(
        f"Structural Size  : {structure.structural_size:.2f}"
    )

    print()

    print(
        "Current Spread Adjusted Amplitude"
    )

    if snapshot.current_spread_adjusted_amplitude is None:
        print("    None")
    else:
        print(
            f"    {snapshot.current_spread_adjusted_amplitude:.2f}"
        )

    print()

    print(
        "Historical Spread Adjusted Amplitudes"
    )

    for value in snapshot.spread_adjusted_amplitudes:
        print(
            f"    {value:.2f}"
        )

    print(
        f"Duration         : {structure.duration:.2f}"
    )

    print(
        f"Volume           : {structure.volume:.2f}"
    )

    print(
        f"Spread           : {structure.spread:.2f}"
    )

    print(
        f"Overall          : {structure.overall:.2f}"
    )

    print()

    print("SMART MONEY")
    print("-" * 20)

    print(
        f"Stopping Volume  : {smart_money.stopping_volume:.2f}"
    )

    print(
        f"Climactic Volume : {smart_money.climactic_volume:.2f}"
    )

    print(
        f"Overall          : {smart_money.overall:.2f}"
    )

    print()

    print("PROFESSIONAL")
    print("-" * 20)

    print(
        f"Overall          : {professional.overall:.2f}"
    )

    print("=" * 60)
    print()