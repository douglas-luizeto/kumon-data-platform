CREATE SCHEMA master;
CREATE SCHEMA transactional;

-- ##################################################################################
-- Lookup Tables: time slots for scheduling; stage names x ordering for each subject
-- ##################################################################################

-- Create and populate time_slots lookup table
CREATE TABLE master.time_slots (
    time_slot_id SMALLSERIAL PRIMARY KEY,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week IN (2, 3, 5, 6)),
    slot_time TIME NOT NULL,
    
    -- Garantees that no slots are equal
    CONSTRAINT uq_day_time UNIQUE (day_of_week, slot_time)
);

-- Automatically populates the table (Mon, Tue, Thu, Fri) x  (09h-12h and 14h-19h) with 1 hour time slots.
INSERT INTO master.time_slots (day_of_week, slot_time)
SELECT 
    d.day_of_week,
    t.slot_time::TIME
FROM 
    (VALUES (2), (3), (5), (6)) AS d(day_of_week)
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

-- Create and populate the subject table
CREATE TABLE master.subjects (
    subject_id CHAR(1) PRIMARY KEY,
    subject_name TEXT NOT NULL UNIQUE
);

INSERT INTO master.subjects (subject_id, subject_name) VALUES
    ('m', 'Matemática'),
    ('p', 'Português'),
    ('i', 'Inglês'),
    ('j', 'Japonês');

-- Create and populate the stages table
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
-- Master Data Tables
-- ##################################################################################

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
    kumon_id INT PRIMARY KEY,
    account_name TEXT NOT NULL,
    birth_date DATE NOT NULL CHECK (birth_date <= CURRENT_DATE AND birth_date > '1900-01-01'),
    customer_id UUID NOT NULL REFERENCES master.customers(customer_id),
    subject_id CHAR(1) NOT NULL,
    enroll_stage_id SMALLINT,

    -- account status    
    enroll_date DATE NOT NULL CHECK (enroll_date <= CURRENT_DATE),
    cancelation_date DATE,

    -- interaction parameters
    time_slot_1 SMALLINT NOT NULL REFERENCES master.time_slots(time_slot_id),
    time_slot_2 SMALLINT REFERENCES master.time_slots(time_slot_id),

    -- finantial parameters
    monthly_fee DECIMAL(8,2) NOT NULL CHECK (monthly_fee >= 0),
    due_day smallint NOT NULL DEFAULT 5 CHECK (due_date IN (5, 10, 15, 20, 25, 30)),
    default_payment_method TEXT NOT NULL DEFAULT 'Boleto' CHECK (default_payment_method IN ('Boleto', 'Dinheiro', 'Pix')),

    CONSTRAINT chk_enroll_after_birth CHECK (enroll_date > birth_date),
    CONSTRAINT chk_cancel_after_enroll CHECK (cancelation_date >= enroll_date),
    CONSTRAINT chk_diffente_time_slots CHECK (time_slot_1 != time_slot_2),
    CONSTRAINT fk_account_subject_stage 
        FOREIGN KEY (subject_id, enroll_stage_id) 
        REFERENCES master.stages (subject_id, stage_id)
);

-- #########################
-- Transactional tables
-- #########################

CREATE TABLE transactional.payments (
    payment_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES master.customer(customer_id),
    payment_date DATE NOT NULL,
    amount DECIMAL(8,2) NOT NULL,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('Boleto', 'Dinheiro', 'Pix'))
);

CREATE TABLE transactional.interactions (
    interaction_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES master.accounts(account_id),
    -- expected_date DATE NOT NULL CHECK (expected_date <= CURRENT_DATE),

    -- start_ts TIMESTAMP,
    -- end_ts TIMESTAMP CHECK (end_ts < NOW()),
    -- rescheduled BOOLEAN DEFAULT FALSE,

    -- constraints


);