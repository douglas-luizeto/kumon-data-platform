"""
Synthetic Data Generation Script for Transactional Tables (Kumon Unit)
Reads master CSV files (employees, customers, accounts) and generates consistent
transactional records for interactions, monthly_performance, tuition_invoices,
tuition_invoice_items, and financial_transactions respecting PostgreSQL schema constraints.
"""

from pathlib import Path
import random
import uuid
from datetime import date, datetime, time, timedelta
import numpy as np
import pandas as pd

# ==========================================
# CONFIGURATION AND DETERMINISTIC SEEDS
# ==========================================
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

START_DATE = date(2024, 7, 1)
END_DATE = date(2026, 6, 30)

# ==========================================
# DOMAIN CATALOGS & MAPPINGS
# ==========================================
STAGE_MAP = {
    "m": list(range(1, 21)),   # 1..20 (6A..2A, A..O)
    "p": list(range(21, 48)),  # 21..47 (7A..2A, AI..GII, HI, HII, II, III, J..L)
    "i": list(range(48, 69)),  # 48..68 (7A..2A, A..O)
    "j": list(range(69, 84)),  # 69..83 (4A..2A, A..L)
}

SLOT_TIMES = [
    time(9, 0), time(9, 30), time(10, 0), time(10, 30),
    time(14, 0), time(15, 0), time(16, 0), time(17, 0), time(18, 0), time(19, 0)
]

# Map time_slot_id (1..40) -> (isoweekday, time_object)
# PostgreSQL DOW: Mon=1, Tue=2, Thu=4, Fri=5 (matches Python date.isoweekday())
TIME_SLOT_INFO = {}
for idx, dow in enumerate([1, 2, 4, 5]):
    for t_idx, slot_t in enumerate(SLOT_TIMES):
        slot_id = idx * 10 + t_idx + 1
        TIME_SLOT_INFO[slot_id] = (dow, slot_t)

# Payment Methods: id -> {name, settlement_days, fee_fixed, fee_pct}
PAYMENT_METHODS = {
    1: {"name": "Boleto", "settlement_days": 2, "fee_fixed": 2.50, "fee_pct": 0.0},
    2: {"name": "Boleto-Pix", "settlement_days": 1, "fee_fixed": 1.80, "fee_pct": 0.0},
    3: {"name": "Pix", "settlement_days": 0, "fee_fixed": 0.00, "fee_pct": 0.005},
    4: {"name": "Dinheiro", "settlement_days": 0, "fee_fixed": 0.00, "fee_pct": 0.0},
}

# Cost Centers: id -> {name, flow_type}
COST_CENTERS = {
    1: {"name": "Mensalidades", "flow_type": "IN"},
    2: {"name": "Material Didático", "flow_type": "IN"},
    3: {"name": "Royalties", "flow_type": "OUT"},
    4: {"name": "Salários", "flow_type": "OUT"},
    5: {"name": "Aluguel", "flow_type": "OUT"},
    6: {"name": "Utilidades", "flow_type": "OUT"},
    7: {"name": "Impostos", "flow_type": "OUT"},
    8: {"name": "Tarifas Bancárias", "flow_type": "OUT"},
}

BEHAVIOR_TAGS_POOL = ["desmotivado", "pergunta demais", "indisciplinado"]


# ==========================================
# 1. DATA LOADING & PREPROCESSING
# ==========================================
def load_master_data():
    """Loads master CSVs enforcing string types on identifiers and codes."""
    emp_df = pd.read_csv(
        DATA_DIR / "employees.csv",
        dtype={"emp_id": str, "phone1": str, "phone2": str}
    )
    cust_df = pd.read_csv(
        DATA_DIR / "customers.csv",
        dtype={"customer_id": str, "cpf": str, "phone1": str, "phone2": str, "zip_code": str}
    )
    acc_df = pd.read_csv(
        DATA_DIR / "accounts.csv",
        dtype={
            "account_id": str,
            "kumon_id": str,
            "customer_id": str,
            "subject_id": str,
            "emp_1": str,
            "emp_2": str,
        }
    )

    # Parse date columns
    emp_df["contract_start"] = pd.to_datetime(emp_df["contract_start"]).dt.date
    emp_df["contract_end"] = pd.to_datetime(emp_df["contract_end"]).dt.date

    acc_df["birth_date"] = pd.to_datetime(acc_df["birth_date"]).dt.date
    acc_df["enroll_date"] = pd.to_datetime(acc_df["enroll_date"]).dt.date
    acc_df["cancellation_date"] = pd.to_datetime(acc_df["cancellation_date"]).dt.date

    # Family-level billing attributes now reside on master.customers
    cust_df["due_day"] = cust_df["due_day"].astype(int)
    cust_df["default_payment_method_id"] = cust_df["default_payment_method_id"].astype(int)

    acc_df["initial_stage_id"] = acc_df["initial_stage_id"].astype(int)
    acc_df["time_slot_1"] = acc_df["time_slot_1"].astype(int)
    acc_df["time_slot_2"] = acc_df["time_slot_2"].astype(int)
    acc_df["monthly_fee"] = acc_df["monthly_fee"].astype(float)

    print(
        f"[OK] Loaded master tables: {len(emp_df)} employees, "
        f"{len(cust_df)} customers, {len(acc_df)} accounts."
    )
    return emp_df, cust_df, acc_df


# ==========================================
# 2. BEHAVIORAL ARCHETYPE ASSIGNMENT
# ==========================================
def assign_behavioral_profiles(acc_df):
    """
    Assigns a behavioral archetype to each account based on gender, age at enrollment,
    and cancellation status.
    Archetypes: 'exemplar', 'mediano', 'esforcado_lento', 'sem_dever', 'faltoso_risco'
    """
    archetypes = ["exemplar", "mediano", "esforcado_lento", "sem_dever", "faltoso_risco"]
    assigned = {}

    for _, row in acc_df.iterrows():
        acc_id = row["account_id"]
        gender = row["gender"]
        age = (row["enroll_date"] - row["birth_date"]).days / 365.25
        is_canceled = pd.notna(row["cancellation_date"])

        # Base weights: exemplar(25%), mediano(35%), esforcado_lento(15%), sem_dever(15%), faltoso_risco(10%)
        weights = np.array([0.25, 0.35, 0.15, 0.15, 0.10], dtype=float)

        # Gender bias: boys have slightly higher probability of low homework / evasion
        if gender == "M":
            weights += np.array([-0.04, -0.02, 0.00, 0.04, 0.02])
        else:
            weights += np.array([0.03, 0.02, 0.01, -0.04, -0.02])

        # Cancellation bias: accounts that eventually cancel lean more toward risk/low homework
        if is_canceled:
            weights += np.array([-0.08, -0.05, 0.00, 0.06, 0.07])

        weights = np.clip(weights, 0.02, None)
        weights /= weights.sum()

        profile = np.random.choice(archetypes, p=weights)
        assigned[acc_id] = {
            "base_profile": profile,
            "is_teenager": 12.0 <= age <= 17.5,
            "age_at_enroll": age,
        }

    return assigned


def get_effective_profile(base_info, current_date, enroll_date, cancel_date):
    """
    Adjusts the student's effective behavioral profile dynamically over time:
    - Last 60 days before cancellation -> shifts to 'faltoso_risco'.
    - Teenagers (12-17) -> start strong/regular for first 4-5 months, then drop to 'sem_dever' or 'mediano'.
    """
    if pd.notna(cancel_date) and (cancel_date - current_date).days <= 60:
        return "faltoso_risco"

    days_enrolled = (current_date - enroll_date).days
    base_prof = base_info["base_profile"]

    if base_info["is_teenager"]:
        if days_enrolled <= 135 and base_prof in ("sem_dever", "mediano"):
            return "exemplar" if random.random() < 0.5 else "mediano"
        elif days_enrolled > 150 and base_prof in ("exemplar", "mediano"):
            return "sem_dever" if random.random() < 0.65 else "mediano"

    return base_prof


# ==========================================
# 3. INTERACTIONS GENERATION
# ==========================================
def format_pg_array(tags_list):
    """Formats a Python list of strings into PostgreSQL array literal '{a,b}' or None."""
    if not tags_list:
        return None
    escaped = [f'"{t}"' if " " in t else t for t in tags_list]
    return "{" + ",".join(escaped) + "}"


def simulate_attendance_attributes(eff_profile, study_medium, max_study_days):
    """Samples attendance, homework days, quality, did_corrections, and behavior tags."""
    profile_params = {
        "exemplar": {
            "att_prob": 0.95,
            "just_prob": 0.80,
            "study_ratio": (0.85, 1.00),
            "qual_weights": [0.80, 0.18, 0.02],  # alta, média, baixa
            "corr_prob": 0.92,
            "tag_probs": {},
        },
        "mediano": {
            "att_prob": 0.85,
            "just_prob": 0.60,
            "study_ratio": (0.45, 0.80),
            "qual_weights": [0.20, 0.65, 0.15],
            "corr_prob": 0.75,
            "tag_probs": {"desmotivado": 0.05},
        },
        "esforcado_lento": {
            "att_prob": 0.92,
            "just_prob": 0.75,
            "study_ratio": (0.75, 1.00),
            "qual_weights": [0.25, 0.55, 0.20],
            "corr_prob": 0.85,
            "tag_probs": {"pergunta demais": 0.28, "desmotivado": 0.05},
        },
        "sem_dever": {
            "att_prob": 0.80,
            "just_prob": 0.45,
            "study_ratio": (0.00, 0.35),
            "qual_weights": [0.05, 0.30, 0.65],
            "corr_prob": 0.45,
            "tag_probs": {"desmotivado": 0.25, "indisciplinado": 0.20},
        },
        "faltoso_risco": {
            "att_prob": 0.50,
            "just_prob": 0.20,
            "study_ratio": (0.00, 0.25),
            "qual_weights": [0.02, 0.23, 0.75],
            "corr_prob": 0.35,
            "tag_probs": {"desmotivado": 0.35, "indisciplinado": 0.15},
        },
    }

    p = profile_params[eff_profile]
    attended = random.random() < p["att_prob"]

    if not attended:
        is_justified = random.random() < p["just_prob"]
        return False, is_justified, None, None, None, None

    # Calculate days_studied_since_last strictly within [0, max_study_days]
    if max_study_days <= 0:
        days_studied = 0
    else:
        ratio = random.uniform(*p["study_ratio"])
        days_studied = int(round(max_study_days * ratio))
        days_studied = max(0, min(days_studied, max_study_days))

    # did_corrections (higher probability on tablet)
    corr_prob = min(0.98, p["corr_prob"] + (0.10 if study_medium == "tablet" else 0.0))
    did_corrections = bool(random.random() < corr_prob)

    study_quality = np.random.choice(["alta", "média", "baixa"], p=p["qual_weights"])

    tags = [tag for tag, prob in p["tag_probs"].items() if random.random() < prob]
    pg_tags = format_pg_array(tags)

    return True, False, days_studied, did_corrections, study_quality, pg_tags


def generate_interactions(acc_df, profiles):
    """
    Simulates chronological class interactions per student account, including
    regular classes and makeup classes (rescheduled_from_id).
    """
    interactions = []

    for _, acc in acc_df.iterrows():
        acc_id = acc["account_id"]
        enroll_d = acc["enroll_date"]
        cancel_d = acc["cancellation_date"]
        active_end = min(cancel_d, END_DATE) if pd.notna(cancel_d) else END_DATE

        slot_1 = int(acc["time_slot_1"])
        slot_2 = int(acc["time_slot_2"])
        dow_1, _ = TIME_SLOT_INFO[slot_1]
        dow_2, _ = TIME_SLOT_INFO[slot_2]
        dow_to_slot = {dow_1: slot_1, dow_2: slot_2}

        study_medium = acc["study_medium"]
        base_info = profiles[acc_id]

        # Build initial regular schedule
        scheduled_events = []
        curr_d = enroll_d
        while curr_d <= active_end:
            dow = curr_d.isoweekday()
            if dow in dow_to_slot:
                scheduled_events.append({
                    "expected_date": curr_d,
                    "expected_time_slot_id": dow_to_slot[dow],
                    "rescheduled_from_id": None,
                    "is_makeup": False,
                })
            curr_d += timedelta(days=1)

        # Process events chronologically (allowing dynamic insertion of makeup classes)
        idx = 0
        last_attended_date = None
        scheduled_dates_set = {e["expected_date"] for e in scheduled_events}

        while idx < len(scheduled_events):
            ev = scheduled_events[idx]
            exp_date = ev["expected_date"]
            slot_id = ev["expected_time_slot_id"]
            _, slot_time_obj = TIME_SLOT_INFO[slot_id]

            eff_prof = get_effective_profile(base_info, exp_date, enroll_d, cancel_d)

            # Determine maximum possible homework days since last attended class
            if last_attended_date is None:
                max_study_days = 0
            else:
                gap_days = (exp_date - last_attended_date).days - 1
                max_study_days = max(0, min(gap_days, 7))

            # Makeup classes have higher attendance probability (~90%)
            if ev["is_makeup"]:
                attended, is_just, days_studied, corr, qual, pg_tags = simulate_attendance_attributes(
                    eff_prof, study_medium, max_study_days
                )
                if not attended and random.random() < 0.80:
                    attended = True
                    is_just = False
                    days_studied = max(0, min(max_study_days, random.randint(1, 3)))
                    corr = True
                    qual = "média"
                    pg_tags = None
            else:
                attended, is_just, days_studied, corr, qual, pg_tags = simulate_attendance_attributes(
                    eff_prof, study_medium, max_study_days
                )

            inter_id = str(uuid.uuid4())

            if attended:
                base_dt = datetime.combine(exp_date, slot_time_obj)
                start_dt = base_dt + timedelta(minutes=random.randint(-10, 15))
                duration_min = random.randint(30, 50)
                end_dt = start_dt + timedelta(minutes=duration_min)

                start_ts_str = start_dt.strftime("%Y-%m-%d %H:%M:%S-03:00")
                end_ts_str = end_dt.strftime("%Y-%m-%d %H:%M:%S-03:00")
                last_attended_date = exp_date
            else:
                start_ts_str = None
                end_ts_str = None

                # Reschedule ~40% of justified absences (only from regular classes)
                if is_just and not ev["is_makeup"] and random.random() < 0.40:
                    for offset in range(1, 15):
                        cand_date = exp_date + timedelta(days=offset)
                        if cand_date > active_end:
                            break
                        cand_dow = cand_date.isoweekday()
                        if cand_dow in (1, 2, 4, 5) and cand_date not in scheduled_dates_set:
                            # Pick a valid slot on that weekday
                            dow_block_idx = [1, 2, 4, 5].index(cand_dow)
                            makeup_slot = dow_block_idx * 10 + random.randint(1, 10)
                            makeup_ev = {
                                "expected_date": cand_date,
                                "expected_time_slot_id": makeup_slot,
                                "rescheduled_from_id": inter_id,
                                "is_makeup": True,
                            }
                            scheduled_dates_set.add(cand_date)
                            # Insert maintaining chronological order
                            insert_pos = idx + 1
                            while (
                                insert_pos < len(scheduled_events)
                                and scheduled_events[insert_pos]["expected_date"] < cand_date
                            ):
                                insert_pos += 1
                            scheduled_events.insert(insert_pos, makeup_ev)
                            break

            interactions.append({
                "interaction_id": inter_id,
                "account_id": acc_id,
                "expected_date": exp_date,
                "expected_time_slot_id": slot_id,
                "rescheduled_from_id": ev["rescheduled_from_id"],
                "is_justified_absence": is_just,
                "start_ts": start_ts_str,
                "end_ts": end_ts_str,
                "days_studied_since_last": days_studied,
                "did_corrections": corr,
                "study_quality": qual,
                "behavior_tags": pg_tags,
            })

            idx += 1

    inter_df = pd.DataFrame(interactions)
    # Format nullable integer columns cleanly for CSV export
    inter_df["days_studied_since_last"] = inter_df["days_studied_since_last"].astype("Int64")
    inter_df.to_csv(DATA_DIR / "interactions.csv", index=False)
    print(f"[OK] interactions.csv generated with {len(inter_df)} records.")
    return inter_df


# ==========================================
# 4. MONTHLY PERFORMANCE GENERATION
# ==========================================
def get_stage_daily_sheet_rate(subject_id, current_stage_id, eff_profile):
    """
    Returns net non-repeated sheets progressed per effective study day,
    faster in introductory stages (7A..A) and slower in advanced stages.
    """
    stages = STAGE_MAP[subject_id]
    rel_pos = stages.index(current_stage_id) / max(1, len(stages) - 1)

    if rel_pos <= 0.30:       # Introductory (7A..A)
        base_rate = random.uniform(9.0, 14.0)
    elif rel_pos <= 0.65:     # Intermediate (B..G)
        base_rate = random.uniform(5.0, 8.5)
    else:                     # Advanced (H+)
        base_rate = random.uniform(2.5, 4.5)

    # Profile repetition / efficiency multiplier
    mult_map = {
        "exemplar": 1.15,
        "mediano": 0.85,
        "esforcado_lento": 0.50,  # High block repetition -> slow stage advancement
        "sem_dever": 0.60,
        "faltoso_risco": 0.45,
    }
    return base_rate * mult_map.get(eff_profile, 0.80)


def generate_monthly_performance(acc_df, inter_df, profiles):
    """
    Generates monthly_performance records per student account from enrollment month
    through cancellation month (or end of window), synced with interactions.
    """
    # Pre-track earliest enrollment date per kumon_id to identify 'EO' (multi-subject)
    earliest_enroll_by_student = acc_df.groupby("kumon_id")["enroll_date"].min().to_dict()

    # Pre-group interactions by account_id and month
    inter_attended = inter_df[inter_df["start_ts"].notna()].copy()
    inter_attended["ref_month"] = inter_attended["expected_date"].apply(
        lambda d: date(d.year, d.month, 1)
    )
    monthly_inter_stats = (
        inter_attended.groupby(["account_id", "ref_month"])
        .agg(
            attended_classes=("interaction_id", "count"),
            homework_days=("days_studied_since_last", "sum"),
        )
        .to_dict(orient="index")
    )

    records = []
    perf_id_counter = 1

    for _, acc in acc_df.iterrows():
        acc_id = acc["account_id"]
        kumon_id = acc["kumon_id"]
        subj = acc["subject_id"]
        enroll_d = acc["enroll_date"]
        cancel_d = acc["cancellation_date"]

        enroll_month = date(enroll_d.year, enroll_d.month, 1)
        end_bound = min(cancel_d, END_DATE) if pd.notna(cancel_d) else END_DATE
        last_month = date(end_bound.year, end_bound.month, 1)
        cancel_month = date(cancel_d.year, cancel_d.month, 1) if pd.notna(cancel_d) else None

        subj_stages = STAGE_MAP[subj]
        curr_stage_idx = subj_stages.index(int(acc["initial_stage_id"]))
        curr_lesson = 10  # Starting lesson block

        curr_m = enroll_month
        while curr_m <= last_month:
            # Determine status_id
            if cancel_month is not None and curr_m == cancel_month:
                status_id = np.random.choice(["A", "OT"], p=[0.90, 0.10])
            elif curr_m == enroll_month:
                if enroll_d > earliest_enroll_by_student[kumon_id]:
                    status_id = "EO"
                else:
                    status_id = np.random.choice(["N", "IT"], p=[0.95, 0.05])
            else:
                status_id = "C"

            if status_id in ("A", "OT"):
                sheets_completed = 0
                final_stage_id = subj_stages[curr_stage_idx]
                final_lesson_number = curr_lesson
            else:
                stats = monthly_inter_stats.get((acc_id, curr_m), {"attended_classes": 0, "homework_days": 0})
                effective_days = int(stats["attended_classes"]) + int(stats["homework_days"])

                if effective_days <= 0:
                    sheets_completed = 10 if curr_m == enroll_month else 0
                else:
                    eff_prof = get_effective_profile(profiles[acc_id], curr_m, enroll_d, cancel_d)
                    daily_rate = get_stage_daily_sheet_rate(subj, subj_stages[curr_stage_idx], eff_prof)
                    raw_sheets = effective_days * daily_rate
                    sheets_completed = max(10, int(round(raw_sheets / 10.0)) * 10)

                # Advance stage and lesson number (200 sheets per stage)
                total_progress = curr_lesson + sheets_completed
                stages_gained = (total_progress - 10) // 200
                new_lesson = ((total_progress - 10) % 200) + 10
                # Ensure strict multiple of 10 in [10..200]
                new_lesson = max(10, min(200, int(round(new_lesson / 10.0)) * 10))

                curr_stage_idx = min(curr_stage_idx + stages_gained, len(subj_stages) - 1)
                curr_lesson = new_lesson

                final_stage_id = subj_stages[curr_stage_idx]
                final_lesson_number = curr_lesson

            records.append({
                "performance_id": perf_id_counter,
                "account_id": acc_id,
                "reference_month": curr_m,
                "status_id": status_id,
                "final_stage_id": final_stage_id,
                "final_lesson_number": final_lesson_number,
                "sheets_completed": sheets_completed,
            })
            perf_id_counter += 1

            # Advance to 1st day of next month
            if curr_m.month == 12:
                curr_m = date(curr_m.year + 1, 1, 1)
            else:
                curr_m = date(curr_m.year, curr_m.month + 1, 1)

    perf_df = pd.DataFrame(records)
    perf_df.to_csv(DATA_DIR / "monthly_performance.csv", index=False)
    print(f"[OK] monthly_performance.csv generated with {len(perf_df)} records.")
    return perf_df


# ===================================================
# 5. TUITION INVOICES, ITEMS & FINANCIAL TRANSACTIONS
# ===================================================
def generate_financials(acc_df, cust_df, emp_df):
    """
    Generates consolidated family tuition_invoices, account-level tuition_invoice_items,
    and granular financial_transactions across the 24-month simulation window.

    Enforces the PostgreSQL XOR constraint on financial_transactions:
    - Tuition inflows link to tuition_invoices via invoice_id (competence_date = None).
    - Operating expenses set competence_date (1st of month) and invoice_id = None.
    """
    invoice_records = []
    item_records = []
    fin_records = []

    # Fast lookup for family-level billing settings
    cust_billing = cust_df.set_index("customer_id")[
        ["due_day", "default_payment_method_id"]
    ].to_dict(orient="index")

    # Identify 15% of canceled accounts exhibiting silent churn (delinquent in last 1-2 months)
    canceled_acc_ids = acc_df[acc_df["cancellation_date"].notna()]["account_id"].tolist()
    silent_churn_ids = set(
        random.sample(canceled_acc_ids, k=max(1, int(round(len(canceled_acc_ids) * 0.15))))
    )

    # Build list of all 24 competence months (always 1st day of the month)
    months = []
    curr = date(START_DATE.year, START_DATE.month, 1)
    end_month = date(END_DATE.year, END_DATE.month, 1)
    while curr <= end_month:
        months.append(curr)
        curr = date(curr.year + 1, 1, 1) if curr.month == 12 else date(curr.year, curr.month + 1, 1)

    for ref_month in months:
        monthly_revenue_by_subj = {"m": 0.0, "p": 0.0, "i": 0.0, "j": 0.0}
        monthly_fees_by_pm = {1: [], 2: [], 3: [], 4: []}

        # ------------------------------------------
        # A. CONSOLIDATED FAMILY TUITION INVOICES & ITEMS
        # ------------------------------------------
        # Collect billable accounts per customer_id for this competence month
        customer_billable_accounts = {}

        for _, acc in acc_df.iterrows():
            cust_id = acc["customer_id"]
            enroll_d = acc["enroll_date"]
            cancel_d = acc["cancellation_date"]
            due_day = cust_billing[cust_id]["due_day"]

            enroll_m = date(enroll_d.year, enroll_d.month, 1)
            if ref_month < enroll_m:
                continue

            due_date = date(ref_month.year, ref_month.month, due_day)

            # Skip if account was canceled before this month or before due_date
            if pd.notna(cancel_d):
                cancel_m = date(cancel_d.year, cancel_d.month, 1)
                if ref_month > cancel_m:
                    continue
                if ref_month == cancel_m and cancel_d < due_date:
                    continue

            customer_billable_accounts.setdefault(cust_id, []).append(acc)

        # Create 1 invoice per (customer_id, ref_month) and N invoice items
        for cust_id, billable_accs in customer_billable_accounts.items():
            invoice_id = str(uuid.uuid4())
            due_day = cust_billing[cust_id]["due_day"]
            default_pm_id = cust_billing[cust_id]["default_payment_method_id"]
            due_date = date(ref_month.year, ref_month.month, due_day)

            total_amount = round(sum(float(a["monthly_fee"]) for a in billable_accs), 2)

            invoice_records.append({
                "invoice_id": invoice_id,
                "customer_id": cust_id,
                "competence_date": ref_month,
                "due_date": due_date,
                "total_amount": total_amount,
            })

            has_silent_churn_account = False
            latest_enroll_in_family = max(a["enroll_date"] for a in billable_accs)

            for acc in billable_accs:
                item_records.append({
                    "invoice_item_id": str(uuid.uuid4()),
                    "invoice_id": invoice_id,
                    "account_id": acc["account_id"],
                    "amount": round(float(acc["monthly_fee"]), 2),
                })

                # Check if any account in this family is in silent churn window
                if acc["account_id"] in silent_churn_ids and pd.notna(acc["cancellation_date"]):
                    cancel_m = date(acc["cancellation_date"].year, acc["cancellation_date"].month, 1)
                    months_to_cancel = (
                        (cancel_m.year - ref_month.year) * 12
                        + (cancel_m.month - ref_month.month)
                    )
                    if months_to_cancel <= 1:
                        has_silent_churn_account = True

            # ------------------------------------------
            # B. TUITION PAYMENT INFLOW (financial_transactions)
            # ------------------------------------------
            # Silent churn families leave the invoice unpaid (open delinquency)
            if has_silent_churn_account:
                continue

            # Realistic delinquency: ~4% sporadic unpaid in past months, ~18% still open in final month
            unpaid_prob = 0.18 if ref_month == end_month else 0.04
            if random.random() < unpaid_prob:
                continue

            # Simulate payment timing around due_date (85% on-time/early, 15% overdue by 3-35 days)
            if random.random() < 0.85:
                pay_offset = random.randint(-2, 0) if due_date > latest_enroll_in_family else 0
                payment_date = max(latest_enroll_in_family, due_date + timedelta(days=pay_offset))
            else:
                delay_days = random.randint(3, 35)
                payment_date = due_date + timedelta(days=delay_days)

            # Payment method correlated with customer default (85% default, 15% alternative)
            pm_id = default_pm_id if random.random() < 0.85 else int(np.random.choice([1, 2, 3, 4]))
            settlement_days = PAYMENT_METHODS[pm_id]["settlement_days"]
            transaction_date = payment_date + timedelta(days=settlement_days)

            # If settlement occurs after simulation cutoff, keep invoice open/unpaid
            if transaction_date > END_DATE:
                continue

            fin_records.append({
                "transaction_id": str(uuid.uuid4()),
                "cost_center_id": 1,
                "payment_method_id": pm_id,
                "competence_date": None,        # XOR rule: inherited from tuition_invoices
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": total_amount,
                "description": (
                    f"Mensalidade Consolidada - Fatura {invoice_id[:8]} "
                    f"({ref_month.strftime('%Y-%m')}, {len(billable_accs)} matr.)"
                ),
            })

            # Accumulate realized revenue per subject for royalty calculation
            for acc in billable_accs:
                monthly_revenue_by_subj[acc["subject_id"]] += float(acc["monthly_fee"])

            # Track settled invoice for consolidated banking fee calculation
            monthly_fees_by_pm[pm_id].append((transaction_date, total_amount))

        total_month_revenue = sum(monthly_revenue_by_subj.values())

        # ------------------------------------------
        # C. GRANULAR OPERATING EXPENSES (OUT)
        #    XOR rule: invoice_id = None, competence_date = ref_month (1st of month)
        # ------------------------------------------
        # 1. Salaries (cost_center_id = 4) -> 1 transaction per active employee
        sal_tx_date = date(ref_month.year, ref_month.month, 5)
        for _, emp in emp_df.iterrows():
            if emp["contract_start"] <= sal_tx_date and (
                pd.isna(emp["contract_end"]) or emp["contract_end"] >= ref_month
            ):
                fin_records.append({
                    "transaction_id": str(uuid.uuid4()),
                    "cost_center_id": 4,
                    "payment_method_id": 3,  # Pix
                    "competence_date": ref_month,
                    "invoice_id": None,
                    "transaction_date": sal_tx_date,
                    "amount": round(float(emp["salary"]), 2),
                    "description": f"Salário - {emp['employee_type']} ({emp['emp_name']})",
                })

        # 2. Royalties (cost_center_id = 3) -> 1 transaction per subject (14% of realized revenue)
        royalty_tx_date = date(ref_month.year, ref_month.month, 15)
        for subj_code, subj_rev in monthly_revenue_by_subj.items():
            if subj_rev > 0:
                fin_records.append({
                    "transaction_id": str(uuid.uuid4()),
                    "cost_center_id": 3,
                    "payment_method_id": 1,  # Boleto
                    "competence_date": ref_month,
                    "invoice_id": None,
                    "transaction_date": royalty_tx_date,
                    "amount": round(subj_rev * 0.14, 2),
                    "description": f"Royalties Franquia - Disciplina {subj_code.upper()}",
                })

        # 3. Rent (cost_center_id = 5) -> Fixed R$ 2,800.00
        fin_records.append({
            "transaction_id": str(uuid.uuid4()),
            "cost_center_id": 5,
            "payment_method_id": 1,
            "competence_date": ref_month,
            "invoice_id": None,
            "transaction_date": date(ref_month.year, ref_month.month, 10),
            "amount": 2800.00,
            "description": "Aluguel do Imóvel Comercial",
        })

        # 4. Utilities (cost_center_id = 6) -> 4 granular items per month
        utilities_items = [
            ("Energia Elétrica", round(random.uniform(450.0, 650.0), 2), 12),
            ("Água e Esgoto", round(random.uniform(120.0, 180.0), 2), 14),
            ("Internet e Telefonia", 160.00, 18),
            ("Material de Limpeza e Escritório", round(random.uniform(150.0, 250.0), 2), 22),
        ]
        for desc, val, day_num in utilities_items:
            fin_records.append({
                "transaction_id": str(uuid.uuid4()),
                "cost_center_id": 6,
                "payment_method_id": 2,
                "competence_date": ref_month,
                "invoice_id": None,
                "transaction_date": date(ref_month.year, ref_month.month, day_num),
                "amount": val,
                "description": desc,
            })

        # 5. Taxes (cost_center_id = 7) -> Simples Nacional (6% of realized gross revenue)
        if total_month_revenue > 0:
            fin_records.append({
                "transaction_id": str(uuid.uuid4()),
                "cost_center_id": 7,
                "payment_method_id": 1,
                "competence_date": ref_month,
                "invoice_id": None,
                "transaction_date": date(ref_month.year, ref_month.month, 20),
                "amount": round(total_month_revenue * 0.06, 2),
                "description": "Imposto Simples Nacional (DAS)",
            })

        # 6. Banking Fees (cost_center_id = 8) -> Granular settlements per payment method
        for pm_id, settled_list in monthly_fees_by_pm.items():
            if not settled_list:
                continue
            pm_cfg = PAYMENT_METHODS[pm_id]
            if pm_cfg["fee_fixed"] == 0 and pm_cfg["fee_pct"] == 0:
                continue

            total_pm_fee = sum(
                pm_cfg["fee_fixed"] + (amt * pm_cfg["fee_pct"]) for _, amt in settled_list
            )
            if total_pm_fee > 0:
                fin_records.append({
                    "transaction_id": str(uuid.uuid4()),
                    "cost_center_id": 8,
                    "payment_method_id": pm_id,
                    "competence_date": ref_month,
                    "invoice_id": None,
                    "transaction_date": date(ref_month.year, ref_month.month, 28),
                    "amount": round(total_pm_fee, 2),
                    "description": (
                        f"Tarifas de Liquidação - {pm_cfg['name']} ({len(settled_list)} faturas)"
                    ),
                })

    inv_df = pd.DataFrame(invoice_records)
    items_df = pd.DataFrame(item_records)
    fin_df = pd.DataFrame(fin_records)

    inv_df.to_csv(DATA_DIR / "tuition_invoices.csv", index=False)
    items_df.to_csv(DATA_DIR / "tuition_invoice_items.csv", index=False)
    fin_df.to_csv(DATA_DIR / "financial_transactions.csv", index=False)

    print(f"[OK] tuition_invoices.csv generated with {len(inv_df)} records.")
    print(f"[OK] tuition_invoice_items.csv generated with {len(items_df)} records.")
    print(f"[OK] financial_transactions.csv generated with {len(fin_df)} records.")
    return inv_df, items_df, fin_df


# ==========================================
# 6. AUDIT AND SANITY CHECK
# ==========================================
def audit_transactional_data(acc_df, cust_df, inter_df, perf_df, inv_df, items_df, fin_df):
    """Validates relational integrity, XOR constraints, invoice totals, and prints 24-month P&L summary."""
    print("\n" + "=" * 60)
    print("TRANSACTIONAL DATA AUDIT & SANITY REPORT (24 MONTHS)")
    print("=" * 60)

    # 1. Foreign Key & Constraint Checks
    valid_acc_ids = set(acc_df["account_id"])
    valid_cust_ids = set(cust_df["customer_id"])
    valid_inv_ids = set(inv_df["invoice_id"])

    assert set(inter_df["account_id"]).issubset(valid_acc_ids), "FK violation: interactions -> accounts"
    assert set(perf_df["account_id"]).issubset(valid_acc_ids), "FK violation: monthly_performance -> accounts"
    assert set(inv_df["customer_id"]).issubset(valid_cust_ids), "FK violation: tuition_invoices -> customers"
    assert set(items_df["invoice_id"]).issubset(valid_inv_ids), "FK violation: tuition_invoice_items -> tuition_invoices"
    assert set(items_df["account_id"]).issubset(valid_acc_ids), "FK violation: tuition_invoice_items -> accounts"
    assert set(fin_df["invoice_id"].dropna()).issubset(valid_inv_ids), (
        "FK violation: financial_transactions -> tuition_invoices"
    )

    # Composite uniqueness checks
    assert not inv_df.duplicated(subset=["customer_id", "competence_date"]).any(), (
        "UNIQUE violation on tuition_invoices(customer_id, competence_date)"
    )
    assert not items_df.duplicated(subset=["invoice_id", "account_id"]).any(), (
        "UNIQUE violation on tuition_invoice_items(invoice_id, account_id)"
    )

    # Strict XOR constraint check on financial_transactions
    xor_valid = (fin_df["invoice_id"].isna() != fin_df["competence_date"].isna()).all()
    assert xor_valid, "XOR violation: (invoice_id IS NULL) != (competence_date IS NULL) failed!"

    # Day=1 competence_date check
    assert (pd.to_datetime(inv_df["competence_date"]).dt.day == 1).all(), (
        "CHECK violation: tuition_invoices.competence_date must be day 1"
    )
    non_null_comp = fin_df["competence_date"].dropna()
    assert (pd.to_datetime(non_null_comp).dt.day == 1).all(), (
        "CHECK violation: financial_transactions.competence_date must be day 1"
    )

    # Header total_amount == sum(line items amount)
    items_sum = items_df.groupby("invoice_id")["amount"].sum().round(2)
    inv_totals = inv_df.set_index("invoice_id")["total_amount"].round(2)
    assert (items_sum.reindex(inv_totals.index) == inv_totals).all(), (
        "Reconciliation error: tuition_invoices.total_amount != sum(tuition_invoice_items.amount)"
    )

    # Stage consistency check
    acc_subj_map = acc_df.set_index("account_id")["subject_id"].to_dict()
    for _, row in perf_df.iterrows():
        subj = acc_subj_map[row["account_id"]]
        assert row["final_stage_id"] in STAGE_MAP[subj], "Invalid stage_id for subject!"
        assert 10 <= row["final_lesson_number"] <= 200 and row["final_lesson_number"] % 10 == 0

    print("\n1. Relational & Domain Integrity Checks:")
    print("   - [PASS] All foreign keys (account_id, customer_id, invoice_id) verified.")
    print("   - [PASS] Composite UNIQUE constraints and invoice total reconciliation verified.")
    print("   - [PASS] Strict XOR constraint on financial_transactions verified.")
    print("   - [PASS] All stage progressions match subject catalogs and lesson bounds [10..200].")

    # 2. Interactions Summary
    total_inter = len(inter_df)
    attended_cnt = inter_df["start_ts"].notna().sum()
    makeup_cnt = inter_df["rescheduled_from_id"].notna().sum()
    print(f"\n2. Class Interactions Summary:")
    print(f"   - Total scheduled interactions: {total_inter:,}")
    print(f"   - Attended classes: {attended_cnt:,} ({attended_cnt / total_inter * 100:.1f}%)")
    print(f"   - Rescheduled makeup classes: {makeup_cnt:,}")
    print(f"   - Max homework days between classes: {inter_df['days_studied_since_last'].max()}")

    # 3. Monthly Performance Summary
    print(f"\n3. Monthly Performance Breakdown by Status:")
    for st, cnt in perf_df["status_id"].value_counts().items():
        print(f"   - Status '{st}': {cnt:,} records ({cnt / len(perf_df) * 100:.1f}%)")

    # 4. Billing & Delinquency Summary
    paid_inv_ids = set(fin_df["invoice_id"].dropna())
    total_billed = inv_df["total_amount"].sum()
    paid_cnt = len(paid_inv_ids)
    unpaid_cnt = len(inv_df) - paid_cnt
    delinquency_rate = (unpaid_cnt / len(inv_df) * 100) if len(inv_df) > 0 else 0.0
    print(f"\n4. Tuition Billing & Delinquency Summary:")
    print(f"   - Total family invoices issued: {len(inv_df):,} ({len(items_df):,} account line items)")
    print(f"   - Paid invoices: {paid_cnt:,} | Open/Delinquent: {unpaid_cnt:,} ({delinquency_rate:.1f}%)")
    print(f"   - Total Billed Amount: R$ {total_billed:,.2f}")

    # 5. Simplified 24-Month P&L Statement
    fin_df = fin_df.copy()
    fin_df["flow_type"] = fin_df["cost_center_id"].map(lambda c: COST_CENTERS[c]["flow_type"])
    fin_df["cost_center_name"] = fin_df["cost_center_id"].map(lambda c: COST_CENTERS[c]["name"])

    total_rev = fin_df[fin_df["flow_type"] == "IN"]["amount"].sum()
    total_exp = fin_df[fin_df["flow_type"] == "OUT"]["amount"].sum()
    net_income = total_rev - total_exp
    margin_pct = (net_income / total_rev * 100) if total_rev > 0 else 0.0

    print("\n5. Simplified 24-Month P&L Statement (DRE Consolidada):")
    print(f"   - Gross Revenue (Mensalidades Recebidas): R$ {total_rev:,.2f}")
    print(f"   - Total Operating Expenses:               R$ {total_exp:,.2f}")
    for cc_id in sorted(COST_CENTERS.keys()):
        if COST_CENTERS[cc_id]["flow_type"] == "OUT":
            cc_sum = fin_df[fin_df["cost_center_id"] == cc_id]["amount"].sum()
            print(f"       * {COST_CENTERS[cc_id]['name']:<20}: R$ {cc_sum:,.2f}")
    print(f"   ------------------------------------------------------------")
    print(f"   - Net Operating Profit (Lucro Líquido):   R$ {net_income:,.2f} ({margin_pct:.1f}% margin)")
    print("=" * 60 + "\n")


# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("Starting transactional synthetic data generation...")
    emp_df, cust_df, acc_df = load_master_data()
    profiles = assign_behavioral_profiles(acc_df)
    inter_df = generate_interactions(acc_df, profiles)
    perf_df = generate_monthly_performance(acc_df, inter_df, profiles)
    inv_df, items_df, fin_df = generate_financials(acc_df, cust_df, emp_df)
    audit_transactional_data(acc_df, cust_df, inter_df, perf_df, inv_df, items_df, fin_df)
    print("Transactional data generation completed successfully! Files saved in data/")