import math
from typing import Dict, Any, List, Optional


def calculate_home_loan_emi(
    loan_amount_lakhs: float,
    annual_interest_rate: float = 8.5,
    tenure_years: int = 20
) -> Dict[str, Any]:
    """
    Calculates monthly home loan EMI, total interest, and principal vs interest distribution.
    Uses standard reducing balance compound interest formula.
    """
    principal = float(loan_amount_lakhs) * 100000.0
    monthly_rate = (float(annual_interest_rate) / 12.0) / 100.0
    months = int(tenure_years) * 12

    if months <= 0 or principal <= 0:
        return {"error": "Invalid principal or tenure provided."}

    if monthly_rate > 0:
        factor = (1 + monthly_rate) ** months
        emi = (principal * monthly_rate * factor) / (factor - 1)
    else:
        emi = principal / months

    total_payment = emi * months
    total_interest = total_payment - principal

    principal_pct = round((principal / total_payment) * 100, 1)
    interest_pct = round((total_interest / total_payment) * 100, 1)

    # 3-year amortization preview
    amortization_preview: List[Dict[str, Any]] = []
    balance = principal
    for yr in range(1, min(4, tenure_years + 1)):
        interest_yr = 0.0
        principal_yr = 0.0
        for _ in range(12):
            int_month = balance * monthly_rate
            prin_month = emi - int_month
            interest_yr += int_month
            principal_yr += prin_month
            balance = max(0.0, balance - prin_month)
        amortization_preview.append({
            "year": f"Year {yr}",
            "principal_paid": f"Rs {round(principal_yr):,}",
            "interest_paid": f"Rs {round(interest_yr):,}",
            "ending_balance": f"Rs {round(balance):,}"
        })

    return {
        "status": "SUCCESS",
        "loan_amount": f"Rs {loan_amount_lakhs:.2f} Lakhs",
        "interest_rate": f"{annual_interest_rate}% p.a.",
        "tenure_years": tenure_years,
        "total_tenure_months": months,
        "monthly_emi": f"Rs {round(emi):,}",
        "monthly_emi_raw": round(emi),
        "total_interest_payable": f"Rs {round(total_interest / 100000.0, 2)} Lakhs (Rs {round(total_interest):,})",
        "total_amount_payable": f"Rs {round(total_payment / 100000.0, 2)} Lakhs (Rs {round(total_payment):,})",
        "principal_percentage": f"{principal_pct}%",
        "interest_percentage": f"{interest_pct}%",
        "amortization_preview": amortization_preview
    }


def calculate_property_price_breakdown(
    base_price_lakhs: float,
    sqft: Optional[float] = None,
    registration_fee_percent: float = 7.0,
    stamp_duty_percent: float = 2.0,
    gst_percent: float = 0.0
) -> Dict[str, Any]:
    """
    Calculates comprehensive all-inclusive on-road property price breakdown including:
    - Base price
    - Rate per sq.ft
    - Tamil Nadu Stamp Duty (typically 7% registration + 2% stamp duty)
    - GST (0% for ready-to-move, 5% for under-construction)
    - Estimated Total Cost
    """
    base_amount_inr = float(base_price_lakhs) * 100000.0
    stamp_duty_inr = base_amount_inr * (stamp_duty_percent / 100.0)
    reg_fee_inr = base_amount_inr * (registration_fee_percent / 100.0)
    gst_inr = base_amount_inr * (gst_percent / 100.0)
    
    total_on_road_inr = base_amount_inr + stamp_duty_inr + reg_fee_inr + gst_inr
    
    price_per_sqft_str = "N/A"
    if sqft and sqft > 0:
        rate = round(base_amount_inr / sqft)
        price_per_sqft_str = f"Rs {rate:,} / sq.ft"

    return {
        "status": "SUCCESS",
        "base_property_price": f"Rs {base_price_lakhs:.2f} Lakhs",
        "sqft_area": f"{sqft} sq.ft" if sqft else "Not Specified",
        "price_per_sqft": price_per_sqft_str,
        "stamp_duty_cost": f"Rs {round(stamp_duty_inr / 100000.0, 2)} Lakhs ({stamp_duty_percent}%)",
        "registration_fees": f"Rs {round(reg_fee_inr / 100000.0, 2)} Lakhs ({registration_fee_percent}%)",
        "gst_charges": f"Rs {round(gst_inr / 100000.0, 2)} Lakhs ({gst_percent}%)" if gst_percent > 0 else "Rs 0 (Ready-to-Move)",
        "total_estimated_cost": f"Rs {round(total_on_road_inr / 100000.0, 2)} Lakhs (Rs {round(total_on_road_inr):,})",
        "additional_government_charges": f"Rs {round((stamp_duty_inr + reg_fee_inr + gst_inr) / 100000.0, 2)} Lakhs"
    }


def calculate_buyer_loan_eligibility(
    monthly_net_income_inr: float,
    existing_monthly_emis_inr: float = 0.0,
    loan_tenure_years: int = 20,
    interest_rate: float = 8.5
) -> Dict[str, Any]:
    """
    Computes home buyer maximum loan eligibility and budget using banking FOIR guidelines (50% max EMI to Income).
    """
    max_foir_limit = monthly_net_income_inr * 0.50
    available_monthly_emi = max(0.0, max_foir_limit - existing_monthly_emis_inr)

    monthly_rate = (interest_rate / 12.0) / 100.0
    months = loan_tenure_years * 12

    if available_monthly_emi <= 0:
        return {
            "status": "INELIGIBLE",
            "message": "Existing monthly EMIs exceed 50% FOIR limit.",
            "max_eligible_loan": "Rs 0"
        }

    # Reverse calculate principal from available EMI
    if monthly_rate > 0:
        factor = (1 + monthly_rate) ** months
        eligible_principal = (available_monthly_emi * (factor - 1)) / (monthly_rate * factor)
    else:
        eligible_principal = available_monthly_emi * months

    eligible_lakhs = round(eligible_principal / 100000.0, 2)
    # Assuming 80% Loan to Value (20% Down payment from buyer)
    recommended_property_budget_lakhs = round(eligible_lakhs / 0.80, 2)

    return {
        "status": "SUCCESS",
        "monthly_net_income": f"Rs {round(monthly_net_income_inr):,}",
        "max_allowable_emi_capacity": f"Rs {round(available_monthly_emi):,} / month",
        "max_eligible_loan_amount": f"Rs {eligible_lakhs} Lakhs (Rs {round(eligible_principal):,})",
        "recommended_property_budget": f"Rs {recommended_property_budget_lakhs} Lakhs (Assuming 20% down payment)",
        "assumptions": {
            "interest_rate": f"{interest_rate}%",
            "tenure": f"{loan_tenure_years} Years",
            "foir_ratio": "50%"
        }
    }
