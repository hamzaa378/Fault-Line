# Diagrams (renderable directly on GitHub)

These diagrams are generated from the project design. The `.mmd` sources can be edited in Mermaid Live Editor.

## System architecture

```mermaid
flowchart TD
    Browser["Next.js / React UI"] -->|"JWT REST over HTTP"| API["FastAPI service"]
    GitHub["GitHub Webhook"] -->|"Signed HMAC-SHA256"| API
    CLI["CI / Monitoring Integrations"] -->|"Authenticated event ingestion"| API
    API -->|"SQLAlchemy transactions"| DB[("PostgreSQL 16")]
    API --> Auth["Project membership + RBAC"]
    API --> EventLog["Append-only event inbox"]
    API --> CAS["Atomic versioned incident update"]
    API --> Inference["Explainable suspect scorer"]
    EventLog --> DB
    CAS --> DB
    Inference --> DB
    API --> Audit["Audit action records"]
    Audit --> DB
    Browser -.->|"15-second refresh"| API
    classDef blue fill:#24344d,stroke:#7191bd,color:#f2f4fa
    classDef purple fill:#322b55,stroke:#9f89ed,color:#f2f4fa
    class Browser,API,GitHub,CLI blue
    class Auth,EventLog,CAS,Inference,Audit purple
```

## Database ERD

```mermaid
erDiagram
    USERS ||--o{ MEMBERSHIPS : belongs
    PROJECTS ||--o{ MEMBERSHIPS : contains
    PROJECTS ||--o{ DEPLOYMENTS : records
    PROJECTS ||--o{ CODE_CHANGES : records
    PROJECTS ||--o{ INCIDENTS : tracks
    PROJECTS ||--o{ EVENTS : streams
    PROJECTS ||--o{ AUDIT_LOGS : audits
    INCIDENTS ||--o{ INCIDENT_UPDATES : has
    USERS ||--o{ INCIDENT_UPDATES : authors
    INCIDENTS ||--o{ INCIDENT_DEPLOYMENT_LINKS : associates
    DEPLOYMENTS ||--o{ INCIDENT_DEPLOYMENT_LINKS : referenced_by
    USERS {
      uuid_string id PK
      string email UK
      string name
      string password_hash
    }
    PROJECTS {
      uuid_string id PK
      string slug UK
      string name
      text description
    }
    MEMBERSHIPS {
      uuid_string id PK
      uuid_string project_id FK
      uuid_string user_id FK
      string role
    }
    DEPLOYMENTS {
      uuid_string id PK
      uuid_string project_id FK
      string version
      string service
      string status
      string commit_sha
      timestamp deployed_at
    }
    CODE_CHANGES {
      uuid_string id PK
      uuid_string project_id FK
      string sha
      string service
      json changed_files
      timestamp committed_at
    }
    INCIDENTS {
      uuid_string id PK
      uuid_string project_id FK
      string title
      string status
      string severity
      int version
      timestamp first_seen_at
      timestamp resolved_at
    }
    INCIDENT_UPDATES {
      uuid_string id PK
      uuid_string incident_id FK
      uuid_string author_id FK
      text body
      timestamp created_at
    }
    EVENTS {
      uuid_string id PK
      uuid_string project_id FK
      string source
      string external_id
      string type
      timestamp occurred_at
      timestamp received_at
      string digest
    }
    AUDIT_LOGS {
      uuid_string id PK
      uuid_string project_id FK
      uuid_string actor_id FK
      json before
      json after
    }
    INCIDENT_DEPLOYMENT_LINKS {
      uuid_string id PK
      uuid_string incident_id FK
      uuid_string deployment_id FK
      text reason
    }
```

## Incident investigation workflow

```mermaid
flowchart LR
   A["Commit / deployment / monitor alert"] --> B["Validate source + identity"]
   B --> C{"Seen before?"}
   C -->|"Exact match"| D["Acknowledge duplicate"]
   C -->|"ID collision"| E["HTTP 409 conflict"]
   C -->|"New"| F["Persist event with two clocks"]
   F --> G["Rebuild chronological timeline"]
   G --> H["Incident detected or reported"]
   H --> I["Rank recent deployments"]
   I --> J["Human triages candidates"]
   J --> K["Append findings + associate releases"]
   K --> L["Version-checked incident update"]
   L --> M{"Another user updated?"}
   M -->|"Yes"| N["409 + refresh instead of overwrite"]
   M -->|"No"| O["Commit update and audit entry"]
   O --> P["Resolve with documented remediation"]
   classDef error fill:#4c283a,color:#fbd5df,stroke:#e2798a
   class E,N error
```

