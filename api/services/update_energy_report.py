from api.constants import (
    CACHE_ENERGY_APPEALS_FILE,
    CACHE_ENERGY_CLAIMS_FILE,
    CACHE_ENERGY_TTL,
)
from api.utils import is_file_fresh
from api.views.energy import AppealViewSet, ClaimViewSet


class EnergyCSVBuilder:
    def __init__(self):
        self.claim_view = ClaimViewSet()
        self.appeal_view = AppealViewSet()

    def update_claims_file(self):
        fresh, _ = is_file_fresh(CACHE_ENERGY_CLAIMS_FILE, CACHE_ENERGY_TTL)
        if fresh:
            return

        qs = self.claim_view.get_queryset()
        self.claim_view._generate_csv_file(qs, CACHE_ENERGY_CLAIMS_FILE)

    def update_appeals_file(self):
        fresh, _ = is_file_fresh(CACHE_ENERGY_APPEALS_FILE, CACHE_ENERGY_TTL)
        if fresh:
            return

        qs = self.appeal_view.get_queryset()
        self.appeal_view._generate_csv_file(qs, CACHE_ENERGY_APPEALS_FILE)
