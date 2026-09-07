"""Foundation validation before market-risk calculations are allowed to run."""

from typing import List

from frtb_engine.config import (
    load_model_conventions,
    load_project_config,
    load_regulatory_manifest,
)


SEVEN_SBM_RISK_CLASSES = {
    "GIRR",
    "CSR_NON_SECURITISATION",
    "CSR_SECURITISATION_NON_CTP",
    "CSR_SECURITISATION_CTP",
    "EQUITY",
    "COMMODITY",
    "FX",
}

THREE_DRC_COMPONENTS = {
    "DRC_NON_SECURITISATION",
    "DRC_SECURITISATION_NON_CTP",
    "DRC_SECURITISATION_CTP",
}


def foundation_errors() -> List[str]:
    """Return readable validation errors; an empty list means success."""
    project = load_project_config()
    conventions = load_model_conventions()
    manifest = load_regulatory_manifest()
    errors: List[str] = []

    if project["project"]["reporting_currency"] != "INR":
        errors.append("Project reporting currency must be INR.")

    if conventions["valuation"]["reporting_currency"] != "INR":
        errors.append("Model-convention reporting currency must be INR.")

    shared_methods = set(project["portfolio"]["shared_across_methods"])
    if shared_methods != {"SA", "IMA"}:
        errors.append("The shared portfolio must be available to SA and IMA.")

    risk_classes = set(project["engines"]["sbm_risk_classes"])
    if risk_classes != SEVEN_SBM_RISK_CLASSES:
        errors.append("The SA configuration must contain exactly seven SBM risk classes.")

    components = set(project["engines"]["regulatory_components"])
    if not THREE_DRC_COMPONENTS.issubset(components):
        errors.append("All three DRC components must remain separate.")

    if "SBM" not in components or "RRAO" not in components:
        errors.append("The SA configuration must include SBM and RRAO.")

    source_sections = set(manifest["required_components"])
    if source_sections != {"MAR20", "MAR21", "MAR22", "MAR23", "MAR30", "MAR31", "MAR32", "MAR33"}:
        errors.append("Regulatory lineage must cover the SA and IMA Basel chapters.")

    if manifest["parameter_set"]["basis"] != "Basel global minimum standard":
        errors.append("The base parameter set must be labelled as the Basel global minimum standard.")

    if set(project["engines"]["methods"]) != {"SA", "IMA"}:
        errors.append("Both SA and IMA must be active on the shared trading book.")

    return errors


def validate_foundation() -> None:
    errors = foundation_errors()
    if errors:
        raise ValueError("Foundation validation failed:\n- " + "\n- ".join(errors))
