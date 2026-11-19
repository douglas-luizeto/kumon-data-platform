"""
Synthetic Data Generation Script for Master Tables (Kumon Unit)
Generates consistent data for employees, customers, and accounts respecting init.sql.
"""

import os
from pathlib import Path
import random
import uuid
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from faker import Faker

# ==========================================
# CONFIGURATION AND DETERMINISTIC SEEDS
# ==========================================
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
fake = Faker("pt_BR")
Faker.seed(RANDOM_SEED)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Historical Window
START_DATE = datetime.strptime("2024-07-01", "%Y-%m-%d").date()
END_DATE = datetime.strptime("2026-06-30", "%Y-%m-%d").date()

MAX_CAPACITY_PER_EMP_SLOT = 5

# ==========================================
# STAGE MAPS (BASED ON init.sql)
# Exact IDs corresponding to the master.stages catalog
# ==========================================
STAGE_MAP = {
    'm': list(range(1, 21)),   # 1 to 20 (6A..2A, A..O)
    'p': list(range(21, 48)),  # 21 to 47 (7A..2A, AI..GII, HI, HII, II, III, J..L)
    'i': list(range(48, 69)),  # 48 to 68 (7A..2A, A..O)
    'j': list(range(69, 84))   # 69 to 83 (4A..2A, A..L)
}

# Stage weights per subject according to specification
STAGE_WEIGHTS = {
    # 20 stages: 6A..2A (5), A..O (15)
    'm': [0.05/3]*3 + [0.45] + [0.30/2]*2 + [0.10/2]*2 + [0.07/2]*2 + [0.03/5]*5 + [0.0]*5,
    
    # 27 stages: 7A..2A (6), AI..GII (14), HI (1), HII..L (6) -> 16 weighted + 11 zeroed
    'p': [0.15/3]*3 + [0.15] + [0.30/3]*3 + [0.30/3]*3 + [0.10/6]*6 + [0.0]*11,
    
    # 21 stages: 7A(0), 6A(1), 5A(2), 4A(3), 3A(4), 2A(5), A(6), B(7), C(8), D(9), E(10), F(11), G(12), H(13), I(14), J(15), K..O(16..20)
    'i': [0.15, 0.0, 0.0, 0.15, 0.0, 0.0, 0.30, 0.0, 0.0, 0.30, 0.0, 0.0, 0.05, 0.0, 0.0, 0.05] + [0.0]*5,
    
    # 15 stages: 4A, 3A, 2A (3) + A..L (12)
    'j': [0.88, 0.09, 0.03] + [0.0]*12
}

# ==========================================
# 1. EMPLOYEES GENERATION
# ==========================================
def generate_employees():
    employees = []
    
    # 1 Orientador (teaches all subjects)
    employees.append({
        "emp_id": str(uuid.uuid4()),
        "emp_name": fake.name(),
        "employee_type": "Orientador",
        "teaches_m": True,
        "teaches_p": True,
        "teaches_i": True,
        "teaches_j": True,
        "phone1": f"24{random.randint(900000000, 999999999)}",
        "phone2": None,
        "email": fake.email(),
        "salary": 4500.00,
        "contract_start": "2024-01-01",
        "contract_end": None
    })
    
    # 4 Auxiliares (distributing qualifications to ensure coverage)
    aux_configs = [
        (True, True, False, False),
        (True, True, True, False),
        (True, False, False, True),
        (True, False, True, True)
    ]
    
    for config in aux_configs:
        employees.append({
            "emp_id": str(uuid.uuid4()),
            "emp_name": fake.name(),
            "employee_type": "Auxiliar",
            "teaches_m": config[0],
            "teaches_p": config[1],
            "teaches_i": config[2],
            "teaches_j": config[3],
            "phone1": f"24{random.randint(900000000, 999999999)}",
            "phone2": f"24{random.randint(900000000, 999999999)}" if random.random() < 0.3 else None,
            "email": fake.email(),
            "salary": round(random.uniform(1600.00, 2400.00), 2),
            "contract_start": "2024-01-01",
            "contract_end": None
        })
        
    df = pd.DataFrame(employees)
    df.to_csv(os.path.join(OUTPUT_DIR, "employees.csv"), index=False)
    print(f"[OK] employees.csv generated with {len(df)} records.")
    return df

# ==========================================
# 2. CUSTOMERS GENERATION
# ==========================================
def generate_customers(n_customers=100):
    customers = []
    generated_cpfs = set()
    
    while len(customers) < n_customers:
        cpf = "".join([str(random.randint(0, 9)) for _ in range(11)])
        if cpf in generated_cpfs:
            continue
        generated_cpfs.add(cpf)
        
        customers.append({
            "customer_id": str(uuid.uuid4()),
            "cpf": cpf,
            "customer_name": fake.name(),
            "email": fake.email(),
            "phone1": f"24{random.randint(900000000, 999999999)}",
            "phone2": f"24{random.randint(900000000, 999999999)}" if random.random() < 0.3 else None,
            "street": fake.street_name(),
            "address_number": str(random.randint(1, 1500)),
            "complement": random.choice([
                f"Apto {random.randint(101, 804)}",
                f"Bloco {random.choice(['A', 'B', 'C'])} - Apto {random.randint(10, 40)}",
                "Casa 2",
                "Fundos"
            ]) if random.random() < 0.4 else None,
            "district": fake.bairro(),
            "zip_code": f"25{random.randint(100000, 999999)}",
            "city": "Petrópolis",
            "state": "RJ",
            "country": "Brasil"
        })
        
    df = pd.DataFrame(customers)
    # Strictly enforce string type to preserve leading zeros
    df["cpf"] = df["cpf"].astype(str)
    df["zip_code"] = df["zip_code"].astype(str)
    df["phone1"] = df["phone1"].astype(str)
    df["phone2"] = df["phone2"].astype(str)
    
    df.to_csv(os.path.join(OUTPUT_DIR, "customers.csv"), index=False)
    print(f"[OK] customers.csv generated with {len(df)} records.")
    return df

# ==========================================
# 3. ACCOUNTS GENERATION & SLOT ALLOCATION
# ==========================================
def allocate_slot_and_emp(candidate_slots, eligible_emps, modality, enroll_date, cancel_date, schedule_tracker):
    """
    Finds a valid (slot_id, emp_id) pair respecting:
    1. Exclusivity of modality per (emp_id, slot_id) across the entire schedule (or active window).
    2. Max simultaneous capacity of 5 active students per (emp_id, slot_id).
    """
    eff_end = cancel_date if cancel_date is not None else END_DATE
    slots = list(candidate_slots)
    emps = list(eligible_emps)
    random.shuffle(slots)
    random.shuffle(emps)

    for slot_id in slots:
        for emp_id in emps:
            allocations = schedule_tracker.get((emp_id, slot_id), [])
            
            # Rule 1: Do not mix 'presencial' and 'online' in the same (emp, slot)
            if allocations and any(a["modality"] != modality for a in allocations):
                continue
                
            # Filter allocations whose active window overlaps with [enroll_date, eff_end]
            overlapping = [
                a for a in allocations
                if a["start"] <= eff_end and a["end"] >= enroll_date
            ]
            
            # Rule 2: Max 5 simultaneous students for this employee in this slot
            if len(overlapping) >= MAX_CAPACITY_PER_EMP_SLOT:
                continue
                
            # Valid allocation found -> register in tracker
            schedule_tracker.setdefault((emp_id, slot_id), []).append({
                "start": enroll_date,
                "end": eff_end,
                "modality": modality
            })
            return slot_id, emp_id

    raise RuntimeError(f"Capacity exhausted for modality='{modality}' in slots {list(candidate_slots)}")


# Dynamic reference for the index of stage A/AI (1st grade of elementary school, ~6 years old)
# and how many stages correspond to 1 school grade in STAGE_MAP[subject_id].
# Adjust the indices if your STAGE_MAP starts at 7A instead of 6A.
STAGE_A_INDEX_BY_SUBJECT = {
    'm': 5,     # e.g., [6A, 5A, 4A, 3A, 2A, A, B, C, ...] -> index 5 = A
    'p': 5,     # e.g., [6A, 5A, 4A, 3A, 2A, AI, AII, ...] -> index 5 = AI
    'i': 5,     # e.g., [6A, 5A, 4A, 3A, 2A, A, B, C, ...] -> index 5 = A
    'j': None,  # Japanese has no direct equivalence to Brazilian school grades
}

STAGES_PER_GRADE_BY_SUBJECT = {
    'm': 1,     # A, B, C... (1 stage per school grade)
    'p': 2,     # AI/AII, BI/BII... (2 stages per school grade)
    'i': 1,     # A, B, C... (1 stage per school grade)
    'j': None,
}


def determine_declared_churn_reason(
    subject_id, initial_stage_id, birth_date, enroll_date, cancellation_date
):
    """
    Infers the declared churn reason correlated with tenure, estimated stage
    progression, and school-grade equivalence (Stage A/AI = 1st grade / ~6 years old).
    """
    if cancellation_date is None:
        return None

    tenure_months = (cancellation_date - enroll_date).days / 30.44
    age_at_cancel = (cancellation_date - birth_date).days / 365.25

    stages_list = list(STAGE_MAP[subject_id])
    max_idx = len(stages_list) - 1
    initial_idx = stages_list.index(initial_stage_id)

    # Simulate stage progression month by month: faster in early stages
    # (3-4 months/stage) and slower in intermediate/advanced stages (5-7 months/stage)
    current_idx = initial_idx
    remaining_months = tenure_months
    stage_a_idx = STAGE_A_INDEX_BY_SUBJECT.get(subject_id)
    early_cutoff_idx = stage_a_idx if stage_a_idx is not None else min(4, max_idx)

    while remaining_months > 0 and current_idx < max_idx:
        months_needed = (
            random.uniform(3.0, 4.0)
            if current_idx <= early_cutoff_idx
            else random.uniform(5.0, 7.0)
        )
        if remaining_months >= months_needed:
            remaining_months -= months_needed
            current_idx += 1
        else:
            break

    stages_advanced = current_idx - initial_idx
    is_completer = current_idx >= max_idx

    # Check whether the student is ahead of the expected school grade for their age
    is_advanced_for_age = False
    if subject_id in ('m', 'p', 'i') and stage_a_idx is not None:
        stages_per_grade = STAGES_PER_GRADE_BY_SUBJECT[subject_id]
        # Age ~6 = 1st grade (A/AI); each additional year adds stages_per_grade
        expected_grade_offset = max(0, int(age_at_cancel) - 6)
        benchmark_idx = min(
            max_idx, stage_a_idx + (expected_grade_offset * stages_per_grade)
        )

        # Considered advanced if exceeding the age benchmark, or if enrolled in
        # pre-literacy stages and reached stage A/AI between ages 6 and 7.5
        completed_early_literacy = (
            initial_idx < stage_a_idx
            and current_idx >= stage_a_idx
            and 6.0 <= age_at_cancel <= 7.5
        )
        is_advanced_for_age = (current_idx > benchmark_idx) or completed_early_literacy
    elif subject_id == 'j':
        # For Japanese, consider goal achieved if the student advanced >= 3 stages
        is_advanced_for_age = stages_advanced >= 3

    # Case 1: Formal completer or advanced student with tenure >= 8 months
    if is_completer or (is_advanced_for_age and tenure_months >= 8.0):
        return str(
            np.random.choice(
                ['Objetivo atingido', 'Falta de tempo', 'Outros'],
                p=[0.65, 0.20, 0.15],
            )
        )

    # Case 2: Early churn (< 4 months)
    if tenure_months < 4.0:
        return str(
            np.random.choice(
                ['Desmotivação/Dificuldade', 'Falta de tempo', 'Financeiro', 'Outros'],
                p=[0.40, 0.30, 0.20, 0.10],
            )
        )

    # Case 3: Mid-cycle churn (>= 4 months, not advanced for age)
    return str(
        np.random.choice(
            [
                'Falta de tempo',
                'Financeiro',
                'Desmotivação/Dificuldade',
                'Mudança de cidade/escola',
                'Outros',
            ],
            p=[0.35, 0.30, 0.15, 0.10, 0.10],
        )
    )


def generate_accounts(customers_df, employees_df):
    accounts = []
    next_kumon_id = 1001
    schedule_tracker = {}  # Tracks (emp_id, slot_id) -> list of active allocations

    # Distribution of accounts per customer (1 to 4)
    customer_counts = np.random.choice(
        [1, 2, 3, 4], size=len(customers_df), p=[0.65, 0.25, 0.07, 0.03]
    )

    for idx, customer_id in enumerate(customers_df["customer_id"]):
        n_accounts_for_cust = customer_counts[idx]

        # List of individuals (students) under this guardian
        family_students = []

        for _ in range(n_accounts_for_cust):
            # Siblings vs. Multi-subject rule (~50% chance if a student already exists in the family)
            if family_students and random.random() < 0.50:
                # Same student (same kumon_id, name, gender, birth_date, modality)
                student = random.choice(family_students)
                kumon_id = student["kumon_id"]
                account_name = student["account_name"]
                gender = student["gender"]
                birth_date = student["birth_date"]
                modality = student["modality"]
            else:
                # New student (different individual)
                kumon_id = next_kumon_id
                next_kumon_id += 1
                gender = np.random.choice(['M', 'F'], p=[0.43, 0.57])
                account_name = fake.name_male() if gender == 'M' else fake.name_female()

                # Target age bracket sampling
                age_bracket = np.random.choice(
                    ['le_5', '6_10', '11_15', '16_18', '19_30', '31_70'],
                    p=[0.06, 0.26, 0.39, 0.17, 0.09, 0.03],
                )

                # Base enrollment date for age calculation
                enroll_date_tmp = START_DATE + timedelta(
                    days=random.randint(0, (END_DATE - START_DATE).days)
                )

                if age_bracket == 'le_5':
                    age = random.randint(3, 5)
                elif age_bracket == '6_10':
                    age = random.randint(6, 10)
                elif age_bracket == '11_15':
                    age = random.randint(11, 15)
                elif age_bracket == '16_18':
                    age = random.randint(16, 18)
                elif age_bracket == '19_30':
                    age = random.randint(19, 30)
                else:
                    age = random.randint(31, 55)

                birth_date = enroll_date_tmp - timedelta(days=int(age * 365.25))
                if birth_date < datetime.strptime("1900-01-01", "%Y-%m-%d").date():
                    birth_date = datetime.strptime("1970-01-01", "%Y-%m-%d").date()

                # Modality correlated with age (younger kids strongly 'presencial')
                if age <= 6:
                    modality = np.random.choice(["presencial", "online"], p=[0.95, 0.05])
                elif age <= 12:
                    modality = np.random.choice(["presencial", "online"], p=[0.85, 0.15])
                else:
                    modality = np.random.choice(["presencial", "online"], p=[0.70, 0.30])

                student = {
                    "kumon_id": kumon_id,
                    "account_name": account_name,
                    "gender": gender,
                    "birth_date": birth_date,
                    "modality": modality,
                }
                family_students.append(student)

            # Subject (`subject_id`)
            subject_id = np.random.choice(['m', 'p', 'i', 'j'], p=[0.50, 0.20, 0.13, 0.17])

            # Ensure the same student does not have two accounts in the same subject
            existing_subjects = [
                acc["subject_id"] for acc in accounts if acc["kumon_id"] == kumon_id
            ]
            if subject_id in existing_subjects:
                available_subs = [
                    s for s in ['m', 'p', 'i', 'j'] if s not in existing_subjects
                ]
                if not available_subs:
                    continue
                subject_id = random.choice(available_subs)

            # Correlated initial stage
            stage_id = int(
                np.random.choice(STAGE_MAP[subject_id], p=STAGE_WEIGHTS[subject_id])
            )

            # Enrollment date (40% in the initial batch on 2024-07-01, remainder distributed)
            if random.random() < 0.40:
                enroll_date = START_DATE
            else:
                days_offset = random.randint(0, (END_DATE - START_DATE).days)
                enroll_date = START_DATE + timedelta(days=days_offset)

            # Consistency fix: birth_date must precede enroll_date
            if student["birth_date"] >= enroll_date:
                student["birth_date"] = enroll_date - timedelta(days=365 * 6)

            # Cancellation (30% to 35% of accounts)
            cancellation_date = None
            if random.random() < 0.32:
                min_cancel_date = enroll_date + timedelta(days=30)
                if min_cancel_date <= END_DATE:
                    max_days = (END_DATE - min_cancel_date).days
                    cancellation_date = min_cancel_date + timedelta(
                        days=random.randint(0, max_days)
                    )

            # Declared churn reason (NULL when active; correlated with stage/tenure when canceled)
            declared_churn_reason = determine_declared_churn_reason(
                subject_id=subject_id,
                initial_stage_id=stage_id,
                birth_date=student["birth_date"],
                enroll_date=enroll_date,
                cancellation_date=cancellation_date,
            )

            # Study medium ('papel' vs 'tablet'): Japanese is 100% 'papel'
            student_age_approx = (enroll_date - student["birth_date"]).days / 365.25
            if subject_id == 'j':
                study_medium = "papel"
            elif student_age_approx <= 6:
                study_medium = np.random.choice(["papel", "tablet"], p=[0.90, 0.10])
            else:
                study_medium = np.random.choice(["papel", "tablet"], p=[0.65, 0.35])

            # Selection of employees qualified for the subject
            eligible_emps = employees_df[
                employees_df[f"teaches_{subject_id}"] == True
            ]["emp_id"].tolist()

            # Time Slots & Employee allocation (5 students per employee per slot, no modality mixing)
            # Pick a valid pair: (Mon, Thu) -> Blocks [1..10] and [21..30], or (Tue, Fri) -> Blocks [11..20] and [31..40]
            pair_choice = random.choice(['seg_qui', 'ter_sex'])
            if pair_choice == 'seg_qui':
                block_1, block_2 = range(1, 11), range(21, 31)
            else:
                block_1, block_2 = range(11, 21), range(31, 41)

            slot_1, emp_1 = allocate_slot_and_emp(
                block_1,
                eligible_emps,
                student["modality"],
                enroll_date,
                cancellation_date,
                schedule_tracker,
            )
            slot_2, emp_2 = allocate_slot_and_emp(
                block_2,
                eligible_emps,
                student["modality"],
                enroll_date,
                cancellation_date,
                schedule_tracker,
            )

            accounts.append({
                "account_id": str(uuid.uuid4()),
                "kumon_id": kumon_id,
                "account_name": student["account_name"],
                "gender": student["gender"],
                "birth_date": student["birth_date"],
                "customer_id": customer_id,
                "subject_id": subject_id,
                "modality": student["modality"],
                "study_medium": study_medium,
                "initial_stage_id": stage_id,
                "enroll_date": enroll_date,
                "cancellation_date": cancellation_date,
                "declared_churn_reason": declared_churn_reason,
                "time_slot_1": slot_1,
                "emp_1": emp_1,
                "time_slot_2": slot_2,
                "emp_2": emp_2,
                "monthly_fee": 300.00,
                "due_day": np.random.choice([5, 10], p=[0.70, 0.30]),
                "default_payment_method_id": int(
                    np.random.choice([1, 2, 3, 4], p=[0.20, 0.40, 0.35, 0.05])
                ),
            })

    df = pd.DataFrame(accounts)
    df.to_csv(os.path.join(OUTPUT_DIR, "accounts.csv"), index=False)
    print(f"[OK] accounts.csv generated with {len(df)} records.")

    # Audit declared_churn_reason distribution among canceled accounts
    canceled_df = df[df["cancellation_date"].notna()]
    print(f"\n[AUDIT] Declared Churn Reason Distribution ({len(canceled_df)} canceled accounts):")
    if not canceled_df.empty:
        counts = canceled_df["declared_churn_reason"].value_counts(dropna=False)
        pcts = canceled_df["declared_churn_reason"].value_counts(normalize=True, dropna=False) * 100
        for reason, count in counts.items():
            print(f"  - {reason}: {count} ({pcts[reason]:.1f}%)")

    return df
# ==========================================
# 4. GENERATED DATA AUDIT AND SANITY CHECK
# ==========================================
def audit_data(accounts_df):
    print("\n" + "="*50)
    print("MASTER DATA AUDIT AND SANITY REPORT")
    print("="*50)
    
    print("\n1. Total Volumetry:")
    print(f"   - Accounts: {len(accounts_df)}")
    print(f"   - Unique Students (Kumon IDs): {accounts_df['kumon_id'].nunique()}")
    
    print("\n2. Subject Breakdown (subject_id):")
    sub_pct = accounts_df['subject_id'].value_counts(normalize=True) * 100
    for sub, pct in sub_pct.items():
        print(f"   - Subject '{sub}': {pct:.1f}%")
        
    print("\n3. Gender Breakdown (gender):")
    gen_pct = accounts_df['gender'].value_counts(normalize=True) * 100
    for gen, pct in gen_pct.items():
        print(f"   - Gender '{gen}': {pct:.1f}%")
        
    print("\n4. Churn Rate (Cancellations):")
    canceled_count = accounts_df['cancellation_date'].notna().sum()
    churn_rate = (canceled_count / len(accounts_df)) * 100
    print(f"   - Canceled accounts: {canceled_count} ({churn_rate:.1f}%)")
    
    print("\n5. Modality & Study Medium Breakdown:")
    for mod, pct in (accounts_df['modality'].value_counts(normalize=True) * 100).items():
        print(f"   - Modality '{mod}': {pct:.1f}%")
    for med, pct in (accounts_df['study_medium'].value_counts(normalize=True) * 100).items():
        print(f"   - Medium '{med}': {pct:.1f}%")

    print("\n6. Occupancy & Modality Exclusivity per (Employee, Time Slot):")
    s1 = accounts_df[['emp_1', 'time_slot_1', 'modality']].rename(columns={'emp_1': 'emp_id', 'time_slot_1': 'slot_id'})
    s2 = accounts_df[['emp_2', 'time_slot_2', 'modality']].rename(columns={'emp_2': 'emp_id', 'time_slot_2': 'slot_id'})
    emp_slots = pd.concat([s1, s2])
    
    emp_slot_counts = emp_slots.groupby(['emp_id', 'slot_id']).size()
    mixed_modalities = emp_slots.groupby(['emp_id', 'slot_id'])['modality'].nunique()
    
    print(f"   - Average students per (employee, slot): {emp_slot_counts.mean():.1f}")
    print(f"   - Max total historical registrations in a single (employee, slot): {emp_slot_counts.max()}")
    print(f"   - (Employee, slot) pairs mixing online & presencial: {(mixed_modalities > 1).sum()}")
    print("="*50 + "\n")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("Starting master synthetic data generation...")
    emp_df = generate_employees()
    cust_df = generate_customers(n_customers=250)
    acc_df = generate_accounts(cust_df, emp_df)
    audit_data(acc_df)
    print("Process completed successfully! Files saved in data")