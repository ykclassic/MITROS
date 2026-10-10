from packages.execution.interface import ExecutionGateway
from packages.execution.paper import PaperExecutionGateway
from packages.execution.xt import XTSpotExecutionGateway
from packages.operations.config import ExecutionMode, ProductionConfig


def build_venue_gateway(config: ProductionConfig | None = None) -> ExecutionGateway:
    """Choose execution implementation without source-code edits between paper and XT."""
    active = config or ProductionConfig.from_env()
    if active.execution_mode is ExecutionMode.PAPER:
        return PaperExecutionGateway()
    return XTSpotExecutionGateway()
