"""Query executor operators for tinydb.

Operators compose as an iterator pipeline::

    PlanSelector → SeqScan → Filter → Sort → Aggregate → Limit

Each operator accepts and yields row dicts (`{column: value, ...}`).
"""

from tinydb.executor.scan import SeqScan
from tinydb.executor.filter import Filter
from tinydb.executor.sort import Sort
from tinydb.executor.limit import Limit
from tinydb.executor.aggregate import Aggregate
from tinydb.executor.plan import PlanSelector

__all__ = [
    'SeqScan',
    'Filter',
    'Sort',
    'Limit',
    'Aggregate',
    'PlanSelector',
]
