-- enums
CREATE TYPE user_role AS ENUM ('Employee', 'Engineer', 'Facility_Admin');
CREATE TYPE incident_priority AS ENUM ('Low', 'Medium', 'High', 'Critical');
CREATE TYPE incident_status AS ENUM ('Open', 'In-Progress', 'Blocked', 'Resolved', 'Closed');
CREATE TYPE incident_category AS ENUM ('Infrastructure', 'Equipment', 'Security', 'Software', 'Hardware', 'Other');
CREATE TYPE engineer_team AS ENUM ('Infrastructure', 'Equipment', 'Security', 'Software', 'Hardware');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(100) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    hashed_password VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'Employee'
);

CREATE TABLE engineers (
    id SERIAL PRIMARY KEY,
    is_available BOOLEAN DEFAULT TRUE,
    at_incident INTEGER,
    team engineer_team NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    status incident_status NOT NULL,
    priority incident_priority NOT NULL,
    category incident_category NOT NULL,
    is_escalated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    reported_by INTEGER NOT NULL REFERENCES users(id),
    resolved_by INTEGER REFERENCES engineers(id),
    seat_id INTEGER REFERENCES seats(id),
    incident_notes VARCHAR(120)
);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    engineer_id INTEGER NOT NULL REFERENCES engineers(id),
    incident_id INTEGER NOT NULL REFERENCES incidents(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    comments VARCHAR(250),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    incident_at INTEGER NOT NULL REFERENCES incidents(id)
);

CREATE TABLE facilities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE buildings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    facility_id INTEGER NOT NULL REFERENCES facilities(id)
);

CREATE TABLE floors (
    id SERIAL PRIMARY KEY,
    floor_number INTEGER NOT NULL,
    building_id INTEGER NOT NULL REFERENCES buildings(id)
);

CREATE TABLE seats (
    id SERIAL PRIMARY KEY,
    seat_number INTEGER,
    floor_id INTEGER NOT NULL REFERENCES floors(id)
);