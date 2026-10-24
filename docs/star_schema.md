erDiagram
    %% Dimensions
    dim_employee {
        int employee_key PK
        int employee_id
        string name
    }
    dim_department {
        int department_id PK
        string department_name
    }
    dim_date {
        int date_key PK
        date calendar_date
    }
    dim_team {
        int team_id PK
        string team_name
    }

    %% Facts
    fact_payroll {
        int employee_key FK
        int date_key FK
        int department_id FK
        float amount
    }
    
    fact_task {
        int team_id FK
        int sprint_id FK
        int assignee_employee_id FK
    }

    %% Relationships
    dim_employee ||--o{ fact_payroll : "Filters by employee_key"
    dim_department ||--o{ fact_payroll : "Filters by department_id"
    dim_date ||--o{ fact_payroll : "Filters by date_key"
    
    dim_team ||--o{ fact_task : "Filters by team_id"