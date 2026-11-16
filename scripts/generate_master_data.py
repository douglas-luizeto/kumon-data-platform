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


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data/raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Historical Window
START_DATE = datetime.strptime("2024-07-01", "%Y-%m-%d").date()
END_DATE = datetime.strptime("2026-06-30", "%Y-%m-%d").date()

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
            "complement": random.choice([f"Apto {random.randint(101, 804)}", 
                                         f"Bloco {random.choice(['A', 'B', 'C'])} - Apto {random.randint(10, 40)}", 
                                         "Casa 2", 
                                         "Fundos"]) if random.random() < 0.4 else None,
            "district": fake.bairro(),
            "zip_code": f"25{random.randint(10000, 99999)}",
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
    
    df.to_csv(os.path.join(OUTPUT_DIR, "customers.csv", ), index=False)
    print(f"[OK] customers.csv generated with {len(df)} records.")
    return df

# ==========================================
# 3. ACCOUNTS GENERATION
# ==========================================
def generate_accounts(customers_df, employees_df):
    accounts = []
    next_kumon_id = 1001
    
    # Distribution of accounts per customer (1 to 4)
    customer_counts = np.random.choice([1, 2, 3, 4], size=len(customers_df), p=[0.65, 0.25, 0.07, 0.03])
    
    for idx, customer_id in enumerate(customers_df["customer_id"]):
        n_accounts_for_cust = customer_counts[idx]
        
        # List of individuals (students) under this guardian
        family_students = []
        
        for _ in range(n_accounts_for_cust):
            # Siblings vs. Multi-subject rule (~50% chance if a student already exists in the family)
            if family_students and random.random() < 0.50:
                # Same student (same kumon_id, name, gender, birth_date)
                student = random.choice(family_students)
                kumon_id = student["kumon_id"]
                account_name = student["account_name"]
                gender = student["gender"]
                birth_date = student["birth_date"]
            else:
                # New student (different individual)
                kumon_id = next_kumon_id
                next_kumon_id += 1
                gender = np.random.choice(['M', 'F'], p=[0.43, 0.57])
                account_name = fake.name_male() if gender == 'M' else fake.name_female()
                
                # Target age bracket sampling
                age_bracket = np.random.choice(
                    ['le_5', '6_10', '11_15', '16_18', '19_30', '31_70'],
                    p=[0.06, 0.26, 0.39, 0.17, 0.09, 0.03]
                )
                
                # Base enrollment date for age calculation
                enroll_date_tmp = START_DATE + timedelta(days=random.randint(0, (END_DATE - START_DATE).days))
                
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
                    
                student = {
                    "kumon_id": kumon_id,
                    "account_name": account_name,
                    "gender": gender,
                    "birth_date": birth_date
                }
                family_students.append(student)
                
            # Subject (`subject_id`)
            subject_id = np.random.choice(['m', 'p', 'i', 'j'], p=[0.50, 0.20, 0.13, 0.17])
            
            # Ensure the same student does not have two accounts in the same subject
            existing_subjects = [acc["subject_id"] for acc in accounts if acc["kumon_id"] == kumon_id]
            if subject_id in existing_subjects:
                available_subs = [s for s in ['m', 'p', 'i', 'j'] if s not in existing_subjects]
                if not available_subs:
                    continue
                subject_id = random.choice(available_subs)
                
            # Correlated initial stage
            stage_id = int(np.random.choice(STAGE_MAP[subject_id], p=STAGE_WEIGHTS[subject_id]))
            
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
            cancelation_date = None
            if random.random() < 0.32:
                min_cancel_date = enroll_date + timedelta(days=30)
                if min_cancel_date <= END_DATE:
                    max_days = (END_DATE - min_cancel_date).days
                    cancelation_date = min_cancel_date + timedelta(days=random.randint(0, max_days))
                    
            # Time Slots (4 days: Mon[1..10], Tue[11..20], Thu[21..30], Fri[31..40])
            # Pick a valid pair: (Mon, Thu) -> Blocks 1 and 3, or (Tue, Fri) -> Blocks 2 and 4
            pair_choice = random.choice(['seg_qui', 'ter_sex'])
            if pair_choice == 'seg_qui':
                slot_1 = random.randint(1, 10)
                slot_2 = random.randint(21, 30)
            else:
                slot_1 = random.randint(11, 20)
                slot_2 = random.randint(31, 40)
                
            # Selection of employees qualified for the subject
            eligible_emps = employees_df[employees_df[f"teaches_{subject_id}"] == True]["emp_id"].tolist()
            emp_1 = random.choice(eligible_emps)
            emp_2 = random.choice(eligible_emps) if len(eligible_emps) > 1 else emp_1
            
            accounts.append({
                "account_id": str(uuid.uuid4()),
                "kumon_id": kumon_id,
                "account_name": student["account_name"],
                "gender": student["gender"],
                "birth_date": student["birth_date"],
                "customer_id": customer_id,
                "subject_id": subject_id,
                "enroll_stage_id": stage_id,
                "enroll_date": enroll_date,
                "cancelation_date": cancelation_date,
                "time_slot_1": slot_1,
                "emp_1": emp_1,
                "time_slot_2": slot_2,
                "emp_2": emp_2,
                "monthly_fee": 300.00,
                "due_day": np.random.choice([5, 10], p=[0.70, 0.30]),
                "payment_method_id": int(np.random.choice([1, 2, 3, 4], p=[0.20, 0.40, 0.35, 0.05]))
            })
            
    df = pd.DataFrame(accounts)
    df.to_csv(os.path.join(OUTPUT_DIR, "accounts.csv"), index=False)
    print(f"[OK] accounts.csv generated with {len(df)} records.")
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
    canceled_count = accounts_df['cancelation_date'].notna().sum()
    churn_rate = (canceled_count / len(accounts_df)) * 100
    print(f"   - Canceled accounts: {canceled_count} ({churn_rate:.1f}%)")
    
    print("\n5. Average Occupancy per Time Slot (Workload):")
    slot_counts = pd.concat([accounts_df['time_slot_1'], accounts_df['time_slot_2']]).value_counts()
    print(f"   - Average students per weekly slot: {slot_counts.mean():.1f}")
    print(f"   - Maximum peak in a single slot: {slot_counts.max()} students")
    print("="*50 + "\n")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("Starting master synthetic data generation...")
    emp_df = generate_employees()
    cust_df = generate_customers(n_customers=100)
    acc_df = generate_accounts(cust_df, emp_df)
    audit_data(acc_df)
    print("Process completed successfully! Files saved in data/raw/")