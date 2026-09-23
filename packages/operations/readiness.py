from collections.abc import Callable, Sequence

from contracts.operations import CheckStatus, ReadinessCheck, ReadinessReport, ReadinessStatus


class ReadinessProbe:
    def __init__(self, name: str, check: Callable[[], str | None]) -> None:
        if not name.strip():
            raise ValueError("probe name is required")
        self._name = name
        self._check = check

    def run(self) -> ReadinessCheck:
        try:
            detail = self._check()
        except Exception as exc:
            return ReadinessCheck(
                name=self._name,
                status=CheckStatus.FAIL,
                detail=f"probe failed: {type(exc).__name__}",
            )
        if detail is None:
            return ReadinessCheck(name=self._name, status=CheckStatus.PASS, detail="ok")
        return ReadinessCheck(name=self._name, status=CheckStatus.FAIL, detail=detail)


class ReadinessService:
    def __init__(self, probes: Sequence[ReadinessProbe]) -> None:
        self._probes = tuple(probes)

    def check(self) -> ReadinessReport:
        checks = tuple(probe.run() for probe in self._probes)
        status = ReadinessStatus.READY if all(
            check.status is CheckStatus.PASS for check in checks
        ) else ReadinessStatus.NOT_READY
        return ReadinessReport(status=status, checks=checks)
