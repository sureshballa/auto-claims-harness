"""Pure-Python Pydantic v2 domain models for auto-insurance claims.

No LLM calls, no MAF imports. This module is the shared vocabulary for
the harness, tools, and evals layers. All monetary values use Decimal.
Models are frozen; create new instances instead of mutating.
"""

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CoverageType(StrEnum):
    """The type of insurance coverage on a policy line."""

    LIABILITY = "liability"
    COLLISION = "collision"
    COMPREHENSIVE = "comprehensive"


class ClaimStatus(StrEnum):
    """Lifecycle status of a claim from submission through resolution."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    DECIDED = "decided"
    PAID = "paid"
    DENIED = "denied"
    CLOSED = "closed"


class IncidentType(StrEnum):
    """Broad category of the loss event that gave rise to the claim."""

    COLLISION = "collision"
    THEFT = "theft"
    VANDALISM = "vandalism"
    WEATHER = "weather"
    FIRE = "fire"
    OTHER = "other"


class Coverage(BaseModel):
    """A single coverage line on a policy, with its limit and deductible."""

    model_config = ConfigDict(frozen=True)

    coverage_type: CoverageType = Field(
        description=(
            "The type of coverage this line provides (liability, collision, or comprehensive)."
        )
    )
    limit: Decimal = Field(
        description=(
            "Maximum amount the insurer will pay for a covered loss under this coverage line,"
            " in USD."
        )
    )
    deductible: Decimal = Field(
        description=(
            "Amount the policyholder must pay out-of-pocket before the insurer pays, in USD."
        )
    )

    @field_validator("limit", "deductible")
    @classmethod
    def must_be_non_negative(cls, v: Decimal) -> Decimal:
        """Monetary amounts on a coverage line cannot be negative."""
        if v < 0:
            raise ValueError("must be >= 0")
        return v


class Vehicle(BaseModel):
    """A vehicle covered under a policy."""

    model_config = ConfigDict(frozen=True)

    vin: str = Field(
        description=(
            "Vehicle Identification Number — exactly 17 alphanumeric characters"
            " as issued by the manufacturer."
        )
    )
    year: int = Field(
        description=(
            "Model year of the vehicle, between 1900 and one year beyond the current calendar year."
        )
    )
    make: str = Field(description="Vehicle manufacturer name (e.g. 'Toyota', 'Ford').")
    model: str = Field(description="Vehicle model name (e.g. 'Camry', 'F-150').")
    value_estimate: Decimal = Field(
        description=(
            "Rough current market value of the vehicle in USD, used for total-loss calculations."
        )
    )

    @field_validator("vin")
    @classmethod
    def vin_must_be_17_chars(cls, v: str) -> str:
        """NHTSA VINs are exactly 17 characters; checksum validation is deferred."""
        if len(v) != 17:
            raise ValueError("VIN must be exactly 17 characters")
        return v.upper()

    @field_validator("year")
    @classmethod
    def year_must_be_in_range(cls, v: int) -> int:
        """Reject implausible model years without consulting external data."""
        max_year = date.today().year + 1
        if not (1900 <= v <= max_year):
            raise ValueError(f"year must be between 1900 and {max_year}")
        return v

    @field_validator("value_estimate")
    @classmethod
    def value_must_be_non_negative(cls, v: Decimal) -> Decimal:
        """A vehicle with negative market value is not a meaningful concept here."""
        if v < 0:
            raise ValueError("must be >= 0")
        return v


class Policy(BaseModel):
    """An active insurance policy binding a policyholder to one or more vehicles and coverages."""

    model_config = ConfigDict(frozen=True)

    policy_number: str = Field(
        description="Unique insurer-assigned identifier for this policy (e.g. 'POL-000123')."
    )
    policyholder_name: str = Field(description="Full legal name of the primary insured person.")
    policyholder_email: str = Field(
        description="Contact email address for the policyholder; used for claim notifications."
    )
    effective_date: date = Field(
        description="Date on which coverage under this policy begins (inclusive)."
    )
    expiration_date: date = Field(
        description="Date on which coverage under this policy ends (inclusive)."
    )
    vehicles: list[Vehicle] = Field(
        description="One or more vehicles covered by this policy. Must not be empty."
    )
    coverages: list[Coverage] = Field(
        description=(
            "Coverage lines on this policy. Must not be empty and each CoverageType"
            " may appear at most once."
        )
    )

    @field_validator("policyholder_email")
    @classmethod
    def email_basic_format(cls, v: str) -> str:
        """Reject obviously malformed addresses; RFC-5321 validation is outside domain scope."""
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(pattern, v):
            raise ValueError("policyholder_email does not look like a valid email address")
        return v

    @field_validator("vehicles")
    @classmethod
    def vehicles_non_empty(cls, v: list[Vehicle]) -> list[Vehicle]:
        """A policy with no vehicles has no subject of coverage."""
        if not v:
            raise ValueError("policy must list at least one vehicle")
        return v

    @model_validator(mode="after")
    def coverages_non_empty_and_unique(self) -> "Policy":
        """Coverage list must be non-empty and each CoverageType may appear exactly once."""
        if not self.coverages:
            raise ValueError("policy must have at least one coverage line")
        seen: set[CoverageType] = set()
        for c in self.coverages:
            if c.coverage_type in seen:
                raise ValueError(f"duplicate coverage type: {c.coverage_type.value}")
            seen.add(c.coverage_type)
        return self

    def is_active_on(self, when: date) -> bool:
        """Return True if the policy provides coverage on the given date."""
        return self.effective_date <= when <= self.expiration_date

    @property
    def is_active(self) -> bool:
        """Return True if the policy is in force as of today."""
        return self.is_active_on(date.today())


class IncidentDetails(BaseModel):
    """Claimant-reported facts about the loss event at FNOL submission."""

    model_config = ConfigDict(frozen=True)

    incident_type: IncidentType = Field(
        description="Broad category of the loss event (collision, theft, weather damage, etc.)."
    )
    incident_date: date = Field(
        description="Calendar date on which the loss event occurred, as reported by the claimant."
    )
    description: str = Field(
        description="Free-form narrative from the claimant describing how the incident occurred."
    )
    location: str = Field(
        description=(
            "City, area, or address where the incident took place, as provided by the claimant."
        )
    )
    police_report_number: str | None = Field(
        default=None,
        description=(
            "Official police report number if law enforcement was involved;"
            " None if no report was filed."
        ),
    )
    injuries_reported: bool = Field(
        description=(
            "True if the claimant indicated that any person sustained injuries in the incident."
        )
    )
    other_parties_involved: bool = Field(
        description=(
            "True if other vehicles, persons, or property not belonging to the policyholder"
            " were involved."
        )
    )


class DamageAssessment(BaseModel):
    """An estimate of the monetary cost to repair or replace the damaged vehicle."""

    model_config = ConfigDict(frozen=True)

    assessed_amount: Decimal = Field(
        description="Total estimated cost to repair or replace the damaged vehicle, in USD."
    )
    assessment_source: str = Field(
        description=(
            "Origin of this estimate: one of 'claimant_estimate', 'shop_estimate',"
            " 'adjuster_inspection', or 'ml_assessment'."
        )
    )
    confidence: Decimal = Field(
        description=(
            "Confidence score for this estimate, on a scale from 0 (no confidence) to 1 (certain)."
            " Claimant and shop estimates typically carry lower confidence than adjuster"
            " inspections."
        )
    )

    @field_validator("assessed_amount")
    @classmethod
    def amount_non_negative(cls, v: Decimal) -> Decimal:
        """Damage costs cannot be negative."""
        if v < 0:
            raise ValueError("assessed_amount must be >= 0")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_in_unit_interval(cls, v: Decimal) -> Decimal:
        """Confidence is a probability; values outside [0, 1] are nonsensical."""
        if not (Decimal("0") <= v <= Decimal("1")):
            raise ValueError("confidence must be between 0 and 1 inclusive")
        return v


class Claim(BaseModel):
    """A single insurance claim from FNOL through final disposition."""

    model_config = ConfigDict(frozen=True)

    claim_number: str = Field(
        description="Unique insurer-assigned identifier for this claim (e.g. 'CLM-000456')."
    )
    policy_number: str = Field(
        description="Identifier of the policy under which this claim is filed."
    )
    vehicle_vin: str = Field(
        description="VIN of the specific policy vehicle involved in the incident."
    )
    incident: IncidentDetails = Field(description="Claimant-reported facts about the loss event.")
    damage: DamageAssessment | None = Field(
        default=None,
        description=(
            "Damage cost estimate; None until an assessment has been completed."
            " Populated after inspection or ML scoring."
        ),
    )
    status: ClaimStatus = Field(description="Current lifecycle status of the claim.")
    created_at: date = Field(
        description=(
            "Calendar date on which the FNOL was received and the claim record was created."
        )
    )
    decided_at: date | None = Field(
        default=None,
        description=(
            "Calendar date on which a pay/deny decision was reached;"
            " None until the claim reaches DECIDED, PAID, or DENIED status."
        ),
    )
