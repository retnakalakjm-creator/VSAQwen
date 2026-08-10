from models import BackgroundAssessment, EvidenceCategory


class BackgroundReportBuilder:
    """
    Converts BackgroundAssessment into a
    professional narrative.
    """
    
    def build(
        self,
        background: BackgroundAssessment,
    ) -> str:       
        
        sections: dict[EvidenceCategory, list[str]] = {}
        
        for item in background.evidence:
            sections.setdefault(
                item.category,
                [],
            ).append(
                item.description,
            )
        
        lines: list[str] = []

        lines.append("BACKGROUND")
        lines.append("")

        for category in (
            EvidenceCategory.SUPPLY,
            EvidenceCategory.DEMAND,
            EvidenceCategory.TREND,
        ):

            if category not in sections:
                continue

            lines.append(category.name)

            lines.append("-" * len(category.name))

            for description in sections[category]:

                lines.append(f"• {description}")

            lines.append("")

        lines.append("CONCLUSION")
        lines.append("----------")
        lines.append(
            background.bias.name.replace(
                "_",
                " ",
            )
        )

        return "\n".join(lines)