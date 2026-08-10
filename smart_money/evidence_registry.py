from __future__ import annotations

from smart_money.base_rule import BaseEvidenceRule


class EvidenceRegistry:

    def __init__(self) -> None:

        self._rules: list[BaseEvidenceRule] = []

    def register(
        self,
        rule: BaseEvidenceRule,
    ) -> None:

        self._rules.append(rule)

    @property
    def rules(self) -> tuple[BaseEvidenceRule, ...]:

        return tuple(self._rules)