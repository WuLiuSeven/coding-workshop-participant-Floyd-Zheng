

INSERT INTO facilities (id, name) VALUES 
(1, 'Headquarters'), 
(2, 'North Campus');

INSERT INTO buildings (id, name, facility_id) VALUES 
(1, 'Main Building', 1), 
(2, 'Office Building', 2);

INSERT INTO floors (id, floor_number, building_id) VALUES 
(1, 1, 1), 
(2, 2, 1), 
(3, 1, 2);

INSERT INTO seats 
(id, seat_number, floor_id) VALUES 
(1, 101, 1), 
(2, 102, 1), 
(3, 201, 2);

INSERT INTO users (id, email, first_name, last_name, is_active, hashed_password, role) VALUES 
(1, 'admin@example.com', 'Alice', 'Admin', TRUE,'test_hash', 'Facility_Admin'), 
(2, 'engineer@example.com', 'Bob', 'Engineer', TRUE, 'test_hash', 'Engineer'), 
(3, 'employee@example.com', 'Carol', 'Employee', TRUE, 'test_hash', 'Employee');

INSERT INTO engineers (id, is_available, at_incident, team, user_id) VALUES 
(1, TRUE, NULL, 'Software' ,2);

INSERT INTO incidents (id, status, priority, category, is_escalated, reported_by, resolved_by, seat_id, incident_notes) VALUES 
(1, 'Open', 'High', 'Infrastructure', FALSE, 3, NULL, 1, 'Network outage'), 
(2, 'In-Progress', 'Medium', 'Software', FALSE, 3, NULL, 2, 'Application bug'), 
(3, 'Resolved', 'Low', 'Hardware', FALSE, 2, 1, 3, 'Monitor replaced');

INSERT INTO tickets (id, engineer_id, incident_id) VALUES 
(1, 1, 1), 
(2, 1, 2), 
(3, 1, 3);

INSERT INTO notes (id, comments, incident_at) VALUES 
(1, 'Investigating the issue.', 1), 
(2, 'Work is in progress.', 2), 
(3, 'Issue resolved successfully.', 3);



SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT MAX(id) FROM users)); 
SELECT setval(pg_get_serial_sequence('engineers', 'id'), (SELECT MAX(id) FROM engineers)); 
SELECT setval(pg_get_serial_sequence('incidents', 'id'), (SELECT MAX(id) FROM incidents)); 
SELECT setval(pg_get_serial_sequence('tickets', 'id'), (SELECT MAX(id) FROM tickets)); 
SELECT setval(pg_get_serial_sequence('notes', 'id'), (SELECT MAX(id) FROM notes)); 
SELECT setval(pg_get_serial_sequence('facilities', 'id'), (SELECT MAX(id) FROM facilities)); 
SELECT setval(pg_get_serial_sequence('buildings', 'id'), (SELECT MAX(id) FROM buildings)); 
SELECT setval(pg_get_serial_sequence('floors', 'id'), (SELECT MAX(id) FROM floors)); 
SELECT setval(pg_get_serial_sequence('seats', 'id'), (SELECT MAX(id) FROM seats));