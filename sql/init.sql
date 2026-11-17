CREATE SCHEMA master;
CREATE SCHEMA transactional;

-- ##################################################################################
-- Lookup Tables: time slots; stages ordering; status; payment methods; cost centers
-- ##################################################################################

-- ##################################################################################
-- Create and populate time_slots lookup table
-- ##################################################################################
CREATE TABLE master.time_slots (
    time_slot_id SMALLSERIAL PRIMARY KEY,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week IN (1, 2, 4, 5)),
    slot_time TIME NOT NULL,
    max_capacity SMALLINT NOT NULL DEFAULT 5 CHECK (max_capacity > 0),
    
    -- Guarantees that no slots are equal
    CONSTRAINT uq_day_time UNIQUE (day_of_week, slot_time)
);

-- Automatically populates the table (Mon, Tue, Thu, Fri) x  (09h-12h and 14h-19h) with 1 hour time slots.
INSERT INTO master.time_slots (day_of_week, slot_time)
SELECT 
    d.day_of_week,
    t.slot_time::TIME
FROM 
    (VALUES (1), (2), (4), (5)) AS d(day_of_week)
CROSS JOIN 
    (
        SELECT generate_series(
            '2000-01-01 09:00'::TIMESTAMP, 
            '2000-01-01 12:00'::TIMESTAMP, 
            '1 hour'::INTERVAL
        ) AS slot_time
        UNION ALL
        SELECT generate_series(
            '2000-01-01 14:00'::TIMESTAMP, 
            '2000-01-01 19:00'::TIMESTAMP, 
            '1 hour'::INTERVAL
        ) AS slot_time
    ) AS t
ORDER BY 
    d.day_of_week, 
    t.slot_time;

-- ##################################################################################
-- Create and populate the subject table
-- ##################################################################################

CREATE TABLE master.subjects (
    subject_id CHAR(1) PRIMARY KEY,
    subject_name TEXT NOT NULL UNIQUE
);

INSERT INTO master.subjects (subject_id, subject_name) VALUES
    ('m', 'matemática'),
    ('p', 'português'),
    ('i', 'inglês'),
    ('j', 'japonês');

-- ##################################################################################
-- Create and populate the stages table
-- ##################################################################################

CREATE TABLE master.stages (
    stage_id SMALLSERIAL PRIMARY KEY,
    subject_id CHAR(1) NOT NULL REFERENCES master.subjects(subject_id),
    stage_name VARCHAR(5) NOT NULL,
    stage_order SMALLINT NOT NULL,

    -- Garantees no duplicate stages/orders in a single subject
    CONSTRAINT uq_subject_stage UNIQUE (subject_id, stage_name),
    CONSTRAINT uq_subject_order UNIQUE (subject_id, stage_order),
    CONSTRAINT uq_subject_stage_id UNIQUE (subject_id, stage_id)
);

-- Populates Mathematics (6A..2A, A..O -> 20 stages)
INSERT INTO master.stages (subject_id, stage_name, stage_order)
SELECT 'm', stage_name, stage_order
FROM unnest(ARRAY[
    '6A', '5A', '4A', '3A', '2A',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O'
]) WITH ORDINALITY AS t(stage_name, stage_order);

-- Populates Portuguese (7A..2A, AI..GII, HI, HII, II, III, J, K, L -> 27 stages)
INSERT INTO master.stages (subject_id, stage_name, stage_order)
SELECT 'p', stage_name, stage_order
FROM unnest(ARRAY[
    '7A', '6A', '5A', '4A', '3A', '2A',
    'AI', 'AII', 'BI', 'BII', 'CI', 'CII', 'DI', 'DII', 'EI', 'EII', 'FI', 'FII', 'GI', 'GII', 'HI', 'HII', 'II', 'III',
    'J', 'K', 'L'
]) WITH ORDINALITY AS t(stage_name, stage_order);

-- Populates English (7A..2A, A..O -> 21 stages)
INSERT INTO master.stages (subject_id, stage_name, stage_order)
SELECT 'i', stage_name, stage_order
FROM unnest(ARRAY[
    '7A', '6A', '5A', '4A', '3A', '2A',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O'
]) WITH ORDINALITY AS t(stage_name, stage_order);

-- Populates Japanese (4A..2A, A..L -> 15 stages)
INSERT INTO master.stages (subject_id, stage_name, stage_order)
SELECT 'j', stage_name, stage_order
FROM unnest(ARRAY[
    '4A', '3A', '2A',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L'
]) WITH ORDINALITY AS t(stage_name, stage_order);

-- ##################################################################################
-- Create and populate the student status table
-- ##################################################################################

CREATE TABLE master.status (
    status_id VARCHAR(2) PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT
);

INSERT INTO master.status (status_id, status_name, description) VALUES
    ('N', 'Novo', 'Matrícula no mês de referência (primeira competência)'),
    ('IT', 'Transferência Interna', 'Matrícula oriunda de transferência a partir de outra unidade'),
    ('EO', 'Multi', 'Matrícula de aluno corrente em outra disciplina'),
    ('C', 'Corrente', 'Matrícula ativa com frequência e entrega regular no mês'),
    ('A', 'Ausente', 'Matrícula cancelada no mês de referência'),
    ('OT', 'Transferência Externa', 'Matrícula cancelada por razão de transferência para outra unidade'),
    ('CL', 'Concluinte', 'Matrícula encerrada por conclusão do estágio final da disciplina no mês anterior ao mês de referência');

-- ##################################################################################
-- Create and populate the payment methods table
-- ##################################################################################

CREATE TABLE master.payment_methods (
    payment_method_id SMALLSERIAL PRIMARY KEY,
    method_name TEXT UNIQUE NOT NULL,
    -- e.g. payment is received D+30
    settlement_days SMALLINT NOT NULL DEFAULT 0 CHECK (settlement_days >= 0),
    fee_fixed NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (fee_fixed >= 0),
    fee_pct NUMERIC(6, 4) NOT NULL DEFAULT 0 CHECK (fee_pct >= 0 AND fee_pct <= 100.0)
);

INSERT INTO master.payment_methods (method_name, settlement_days, fee_fixed, fee_pct) VALUES
    ('Boleto', 1, 2.49, 0.0000),
    ('Boleto-Pix', 0, 0.99, 0.0000),
    ('Pix', 0, 0.00, 0.0000),
    ('Dinheiro', 0, 0.00, 0.0000);

-- ##################################################################################
-- Create and populate the cost centers table
-- ##################################################################################

CREATE TABLE master.cost_centers (
    cost_center_id SMALLSERIAL PRIMARY KEY,
    cost_center_name TEXT NOT NULL UNIQUE,
    flow_type VARCHAR(3) NOT NULL CHECK (flow_type IN ('IN', 'OUT')),
    -- NULL for revenue
    cost_nature TEXT CHECK (cost_nature IN ('Fixed', 'Variable', 'Tax', 'Financial')),
    description TEXT,

    CONSTRAINT chk_nature_only_for_out CHECK (
        (flow_type = 'IN' AND cost_nature IS NULL) OR
        (flow_type = 'OUT' AND cost_nature IS NOT NULL)
    )
);

INSERT INTO master.cost_centers (cost_center_name, flow_type, cost_nature, description) VALUES
    -- Revenue (IN)
    ('Mensalidades', 'IN', NULL, 'Receita recorrente das disciplinas matriculadas'),
    ('Taxas de Matrícula', 'IN', NULL, 'Receita de adesão de novos alunos'),
    ('Outras Receitas', 'IN', NULL, 'Rendimentos financeiros, vendas avulsas ou reembolsos'),

    -- Variable costs and taxes (OUT)
    ('Royalties e Taxas Franqueadora', 'OUT', 'Variable', 'Repasse percentual sobre faturamento e materiais'),
    ('Tarifas Bancárias e Meios de Pagamento', 'OUT', 'Variable', 'Taxas de emissão de boleto, maquininha e manutenção de conta'),
    ('Impostos', 'OUT', 'Tax', 'DAS / Simples Nacional e tributos municipais'),

    -- Fixed costs (OUT)
    ('Folha de Pagamento e Encargos', 'OUT', 'Fixed', 'Salários de auxiliares, encargos trabalhistas e benefícios'),
    ('Benefícios de Funcionários', 'OUT', 'Fixed', 'Vale-transporte, vale-alimentação, seguro e bonificações'),
    ('Aluguel e Condomínio', 'OUT', 'Fixed', 'Locação do imóvel comercial e taxas condominiais'),
    ('Utilidades e Telecom', 'OUT', 'Fixed', 'Energia elétrica, água, internet e telefonia'),
    ('Marketing e Aquisição', 'OUT', 'Fixed', 'Tráfego pago, panfletagem, eventos locais e material promocional'),
    ('Material de Escritório e Limpeza', 'OUT', 'Fixed', 'Suprimentos administrativos, papelaria, limpeza e copa'),
    ('Manutenção e Equipamentos', 'OUT', 'Fixed', 'Reparos prediais, ar-condicionado, móveis e TI'),
    ('Serviços Terceirizados', 'OUT', 'Fixed', 'Contabilidade, assessoria jurídica e softwares de gestão'),

    -- Financial (OUT)
    ('Dívidas e Encargos Financeiros', 'OUT', 'Financial', 'Parcelas de empréstimos, financiamentos e juros bancários');

-- ##################################################################################
-- Master Data Tables: employees, customers, accounts
-- ##################################################################################

CREATE TABLE master.employees (
    emp_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    emp_name TEXT NOT NULL,
    employee_type TEXT NOT NULL DEFAULT 'Auxiliar',
    
    teaches_m BOOLEAN NOT NULL DEFAULT FALSE,
    teaches_p BOOLEAN NOT NULL DEFAULT FALSE,
    teaches_i BOOLEAN NOT NULL DEFAULT FALSE,
    teaches_j BOOLEAN NOT NULL DEFAULT FALSE,

    phone1 VARCHAR(15) NOT NULL CHECK (phone1 ~ '^[0-9]{10,15}$'),
    phone2 VARCHAR(15) CHECK (phone2 ~ '^[0-9]{10,15}$'),
    email TEXT,

    salary NUMERIC(8,2) NOT NULL CHECK (salary >= 0),

    contract_start DATE NOT NULL,
    contract_end DATE,

    CONSTRAINT chk_contract_end_after_start CHECK (contract_start <= contract_end)
);

CREATE TABLE master.customers (
    -- identification
    customer_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    cpf VARCHAR(11) UNIQUE CHECK (cpf ~ '^[0-9]{11}$'), 
    customer_name TEXT NOT NULL,

    -- contact info
    email TEXT,
    phone1 VARCHAR(15) NOT NULL CHECK (phone1 ~ '^[0-9]{10,15}$'),
    phone2 VARCHAR(15) CHECK (phone2 ~ '^[0-9]{10,15}$'),

    -- address
    street TEXT,
    address_number TEXT,
    complement TEXT,
    district TEXT,
    zip_code VARCHAR(8) CHECK (zip_code ~ '^[0-9]{8}$'),
    city TEXT,
    state VARCHAR(2),
    country TEXT DEFAULT 'Brasil'
);

CREATE TABLE master.accounts (
    -- identification
    account_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    kumon_id INT NOT NULL,
    account_name TEXT NOT NULL,
    birth_date DATE NOT NULL CHECK (birth_date <= CURRENT_DATE AND birth_date > '1900-01-01'),
    gender CHAR(1) NOT NULL CHECK (gender IN ('M', 'F')),
    customer_id UUID NOT NULL REFERENCES master.customers(customer_id), 
    subject_id CHAR(1) NOT NULL,
    initial_stage_id SMALLINT NOT NULL,

    -- account status    
    enroll_date DATE NOT NULL CHECK (enroll_date <= CURRENT_DATE),
    cancellation_date DATE,

    -- study modality
    modality TEXT NOT NULL DEFAULT 'presencial' CHECK (modality IN ('presencial', 'online')),
    study_medium TEXT NOT NULL DEFAULT 'papel' CHECK (study_medium IN ('papel', 'tablet')),

    -- interaction parameters
    time_slot_1 SMALLINT NOT NULL REFERENCES master.time_slots(time_slot_id),
    emp_1 UUID NOT NULL REFERENCES master.employees(emp_id),
    
    time_slot_2 SMALLINT REFERENCES master.time_slots(time_slot_id),
    emp_2 UUID REFERENCES master.employees(emp_id),

    -- financial parameters
    monthly_fee NUMERIC(8,2) NOT NULL CHECK (monthly_fee >= 0),
    due_day SMALLINT NOT NULL DEFAULT 5 CHECK (due_day IN (5, 10, 15, 20, 25, 30)),
    default_payment_method_id SMALLINT NOT NULL REFERENCES master.payment_methods(payment_method_id),

    CONSTRAINT uq_kumon_id_subject_id UNIQUE (kumon_id, subject_id),
    CONSTRAINT chk_enroll_after_birth CHECK (enroll_date > birth_date),
    CONSTRAINT chk_cancel_after_enroll CHECK (cancellation_date >= enroll_date),
    CONSTRAINT chk_different_time_slots CHECK (time_slot_1 != time_slot_2),
    CONSTRAINT chk_emp2_time_slot2 CHECK ((time_slot_2 IS NULL) = (emp_2 IS NULL)),
    CONSTRAINT fk_account_subject_stage 
        FOREIGN KEY (subject_id, initial_stage_id) 
        REFERENCES master.stages (subject_id, stage_id)
);

-- ##################################################################################
-- Transactional tables: financial, tuition, account interactions and performance 
-- ##################################################################################

CREATE TABLE transactional.financial_transactions (
    transaction_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    cost_center_id SMALLINT NOT NULL REFERENCES master.cost_centers(cost_center_id),
    payment_method_id SMALLINT NOT NULL REFERENCES master.payment_methods(payment_method_id),
    
    competence_date DATE NOT NULL, 
    transaction_date DATE NOT NULL,
    amount NUMERIC(10,2) NOT NULL CHECK (amount > 0), 
    description TEXT
);

CREATE TABLE transactional.tuition_payments (
    transaction_id UUID PRIMARY KEY REFERENCES transactional.financial_transactions(transaction_id),
    customer_id UUID NOT NULL REFERENCES master.customers(customer_id),
    reference_month DATE NOT NULL CHECK (EXTRACT(DAY FROM reference_month) = 1),
    due_date DATE NOT NULL
);

CREATE TABLE transactional.interactions (
    interaction_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES master.accounts(account_id),
    expected_date DATE NOT NULL,
    expected_time_slot_id SMALLINT NOT NULL REFERENCES master.time_slots(time_slot_id),
   
    rescheduled_from_id UUID UNIQUE REFERENCES transactional.interactions(interaction_id),
    is_justified_absence BOOLEAN NOT NULL DEFAULT FALSE,

    start_ts TIMESTAMPTZ,
    end_ts TIMESTAMPTZ CHECK (end_ts <= NOW()),

    days_studied_since_last SMALLINT CHECK (days_studied_since_last >= 0),
    -- Indicates whether exercises were corrected or not
    did_corrections BOOLEAN,
    study_quality TEXT CHECK (study_quality IN ('baixa', 'média', 'alta')),

    behavior_tags TEXT[],

    CONSTRAINT uq_account_expected_slot UNIQUE (account_id, expected_date, expected_time_slot_id),
    CONSTRAINT chk_valid_expected_day_of_week CHECK (EXTRACT(dow FROM expected_date) IN (1,2,4,5)),
    CONSTRAINT chk_not_self_rescheduled CHECK (interaction_id != rescheduled_from_id),
    CONSTRAINT chk_attendance_metrics_consistency CHECK (
        -- scenario: student is absent
        (
            start_ts IS NULL 
            AND end_ts IS NULL 
            AND days_studied_since_last IS NULL 
            AND did_corrections IS NULL
            AND study_quality IS NULL
            AND behavior_tags IS NULL
        )
        OR
        -- scenario: student is present
        (
            start_ts IS NOT NULL 
            AND end_ts IS NOT NULL 
            AND end_ts >= start_ts
            AND expected_date <= CURRENT_DATE
            AND (start_ts AT TIME ZONE 'America/Sao_Paulo')::DATE = expected_date
            AND is_justified_absence = FALSE
            AND days_studied_since_last IS NOT NULL
            AND did_corrections IS NOT NULL
            AND study_quality IS NOT NULL
        )
    )
);

CREATE TABLE transactional.monthly_performance (
    performance_id SERIAL PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES master.accounts(account_id),
    reference_month DATE NOT NULL CHECK (EXTRACT(DAY FROM reference_month) = 1),
    
    final_stage_id SMALLINT NOT NULL REFERENCES master.stages(stage_id),
    final_lesson_number SMALLINT NOT NULL CHECK (
        final_lesson_number >= 10 
        AND final_lesson_number <= 200 
        AND final_lesson_number % 10 = 0
    ),
    sheets_completed SMALLINT NOT NULL CHECK (sheets_completed >= 0),

    status_id VARCHAR(2) NOT NULL DEFAULT 'C' REFERENCES master.status(status_id),
    
    -- Idempotency: one record per month
    CONSTRAINT uq_account_month UNIQUE (account_id, reference_month)
);