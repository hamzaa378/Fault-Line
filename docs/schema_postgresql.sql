-- Faultline PostgreSQL 16 initial schema (generated from current SQLAlchemy models).
-- Application startup uses Base.metadata.create_all(); use this file for review / fresh installs only.
-- For future upgrades introduce versioned Alembic migrations.

CREATE TABLE projects (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	description TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
);

CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	password_hash TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE code_changes (
	id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	sha VARCHAR(64) NOT NULL, 
	title VARCHAR(250) NOT NULL, 
	author VARCHAR(120) NOT NULL, 
	service VARCHAR(100) NOT NULL, 
	changed_files JSON NOT NULL, 
	committed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_project_sha UNIQUE (project_id, sha), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE deployments (
	id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	version VARCHAR(100) NOT NULL, 
	environment VARCHAR(30) NOT NULL, 
	service VARCHAR(100) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	commit_sha VARCHAR(64) NOT NULL, 
	actor VARCHAR(120) NOT NULL, 
	deployed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE events (
	id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	external_id VARCHAR(150) NOT NULL, 
	type VARCHAR(30) NOT NULL, 
	summary VARCHAR(300) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	entity_type VARCHAR(40), 
	entity_id VARCHAR(36), 
	details JSON NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_event_idempotency UNIQUE (project_id, source, external_id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE incidents (
	id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	title VARCHAR(250) NOT NULL, 
	description TEXT NOT NULL, 
	service VARCHAR(100) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	assigned_to_id VARCHAR(36), 
	first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	resolution TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_to_id) REFERENCES users (id)
);

CREATE TABLE memberships (
	id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_project_member UNIQUE (project_id, user_id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE audit_logs (
	id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	incident_id VARCHAR(36), 
	actor_id VARCHAR(36), 
	action VARCHAR(80) NOT NULL, 
	before JSON NOT NULL, 
	after JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(incident_id) REFERENCES incidents (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE incident_deployment_links (
	id VARCHAR(36) NOT NULL, 
	incident_id VARCHAR(36) NOT NULL, 
	deployment_id VARCHAR(36) NOT NULL, 
	reason TEXT NOT NULL, 
	linked_by_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_incident_deployment UNIQUE (incident_id, deployment_id), 
	FOREIGN KEY(incident_id) REFERENCES incidents (id) ON DELETE CASCADE, 
	FOREIGN KEY(deployment_id) REFERENCES deployments (id) ON DELETE CASCADE, 
	FOREIGN KEY(linked_by_id) REFERENCES users (id)
);

CREATE TABLE incident_updates (
	id VARCHAR(36) NOT NULL, 
	incident_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	body TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(incident_id) REFERENCES incidents (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_code_changes_project_id ON code_changes (project_id);
CREATE INDEX ix_deployments_project_id ON deployments (project_id);
CREATE INDEX idx_deploy_project_time ON deployments (project_id, deployed_at);
CREATE INDEX idx_event_project_occurrence ON events (project_id, occurred_at);
CREATE INDEX ix_events_project_id ON events (project_id);
CREATE INDEX ix_incidents_project_id ON incidents (project_id);
CREATE INDEX idx_incident_project_seen ON incidents (project_id, first_seen_at);
CREATE INDEX ix_memberships_project_id ON memberships (project_id);
CREATE INDEX ix_memberships_user_id ON memberships (user_id);
CREATE INDEX ix_audit_logs_project_id ON audit_logs (project_id);
CREATE INDEX ix_audit_logs_incident_id ON audit_logs (incident_id);
CREATE INDEX ix_incident_deployment_links_deployment_id ON incident_deployment_links (deployment_id);
CREATE INDEX ix_incident_deployment_links_incident_id ON incident_deployment_links (incident_id);
CREATE INDEX ix_incident_updates_incident_id ON incident_updates (incident_id);
