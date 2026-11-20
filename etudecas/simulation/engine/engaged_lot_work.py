"""An explicit work duration for one frozen, integer physical batch."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EngagedLotWork:
    order_id: str
    work_days: int

    @classmethod
    def parse(cls, value: str) -> "EngagedLotWork":
        order_id, separator, raw_days = value.rpartition(",")
        if not separator or not order_id.strip() or not raw_days.strip().isdigit():
            raise ValueError("Expected ORDER_ID,DAYS for the engaged lot")
        work_days = int(raw_days)
        if not 1 <= work_days <= 365:
            raise ValueError("Engaged lot duration must be between 1 and 365 work days")
        return cls(order_id.strip(), work_days)

    def _next_slot(self, *, target: float, executed: float) -> int:
        if not (float(target).is_integer() and float(executed).is_integer()
                and self.work_days <= target and 0 <= executed < target):
            raise ValueError("Engaged lot work needs positive integer daily tranches within one UN batch")
        target, executed = int(target), int(executed)
        # Find the first cumulative boundary strictly above actual work.
        return ((executed + 1) * self.work_days + target - 1) // target

    def daily_work(self, *, target: float, executed: float) -> int:
        slot = self._next_slot(target=target, executed=executed)
        return int(target) * slot // self.work_days - int(executed)

    def remaining_days(self, *, target: float, executed: float) -> int:
        return self.work_days - self._next_slot(target=target, executed=executed) + 1

    def check_overlap(self, *, orders, pair, day, current_order_id):
        for order in orders:
            if ((order["node_id"], order["item_id"]) == pair
                    and order["state"] == "frozen" and order["planned_release_day"] <= day
                    and order["order_id"] != current_order_id
                    and self.order_id in (order["order_id"], current_order_id)):
                raise ValueError(
                    f"Overlapping engaged lot work at {pair} on day {day}: "
                    f"{current_order_id or 'native WIP'} and {order['order_id']}"
                )
