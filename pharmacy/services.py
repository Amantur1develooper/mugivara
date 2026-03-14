from dataclasses import dataclass
from django.db import transaction

from .models import PharmacyBranch, DrugInCategory, BranchDrug


@dataclass
class SyncResult:
    created: int
    existed: int
    disabled: int = 0


def sync_branch_catalog(
    branch: PharmacyBranch,
    *,
    default_price=0,
    default_available=True,
    disable_removed=False,
) -> SyncResult:
    """
    Создаёт BranchDrug для всех активных лекарств, которые привязаны к активным категориям аптеки.
    Не перезаписывает цену/наличие у уже существующих BranchDrug.

    disable_removed=True -> если лекарство исчезло из каталога/категорий, помечаем is_available=False.
    """
    pharmacy_id = branch.pharmacy_id

    drug_ids_qs = (
        DrugInCategory.objects
        .filter(
            category__pharmacy_id=pharmacy_id,
            category__is_active=True,
            drug__is_active=True,
        )
        .values_list("drug_id", flat=True)
        .distinct()
    )

    drug_ids = list(drug_ids_qs)
    if not drug_ids:
        return SyncResult(created=0, existed=0, disabled=0)

    existing_ids = set(
        BranchDrug.objects.filter(branch=branch, drug_id__in=drug_ids)
        .values_list("drug_id", flat=True)
    )

    to_create = [did for did in drug_ids if did not in existing_ids]

    created = 0
    disabled = 0

    with transaction.atomic():
        if to_create:
            BranchDrug.objects.bulk_create([
                BranchDrug(
                    branch=branch,
                    drug_id=did,
                    price=default_price,
                    is_available=default_available,
                    sort_order=0,
                )
                for did in to_create
            ], ignore_conflicts=True)
            created = len(to_create)

        if disable_removed:
            # те, что есть в филиале, но больше не входят в активный каталог
            disabled = (BranchDrug.objects
                        .filter(branch=branch)
                        .exclude(drug_id__in=drug_ids)
                        .update(is_available=False))

    existed = len(existing_ids)
    return SyncResult(created=created, existed=existed, disabled=disabled)