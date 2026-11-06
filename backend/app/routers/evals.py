"""Golden-set regression, contract and groundedness checks over the stored corpus.
Deterministic: no LLM calls, safe to run on every deploy. Dataset: app/evals/golden.json."""
from fastapi import APIRouter, Depends

from ..evals.runner import DATASET, run_golden
from ..security import get_current_user

router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.get("/golden")
async def golden(user: dict = Depends(get_current_user)):
    return await run_golden()


@router.get("/dataset")
async def dataset(user: dict = Depends(get_current_user)):
    """The golden dataset itself - fixtures, frozen expectations and invariants."""
    return {
        "version": DATASET["version"],
        "description": DATASET["description"],
        "fixtures": {key: {"facts": len(value["facts"]),
                           "note": value.get("note", "")}
                     for key, value in DATASET["fixtures"].items()},
        "frozen_expectations": DATASET["expected_scores"],
        "invariants": DATASET["invariants"],
        "persona_modules": DATASET["persona_modules"],
        "block_contract": DATASET["block_contract"],
    }
