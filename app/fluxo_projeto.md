flowchart TD
    subgraph Consumidores
        A[Sistema Consórcio]
        C[Sistema CRM]
        D[Sistema Batch]
    end

    subgraph API
        B[API Validação]
    end

    subgraph Validação
        E[Autenticação API Key]
        F[Serviço de Validação]
        G[Módulos de Validação]
        H[Regras de Decisão]
        I[Persistência]
    end

    J[(PostgreSQL)]
    K[Sistema MDM]

    %% Fluxo principal
    A --> B
    C --> B
    D --> B
    B --> E --> F
    F --> G
    F --> H
    F --> I --> J

    %% Consumo especial MDM
    K -- Acesso restrito --> B

    %% Resultados para consumidores
    B --> A
    B --> C
    B --> D

    %% Auditoria
    J -.-> L[Registros Auditáveis]