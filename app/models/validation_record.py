# app/models/validation_record.py
""" Representa um registro de validação de dados.
    Este modelo foi aprimorado para ser mais genérico e flexível,
    permitindo armazenar detalhes específicos de diferentes tipos de validação
    (telefone, endereço, etc.) em um campo JSON, e incluindo campos para soft delete.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class ValidationRecord:

    id: Optional[int] = None # Opcional, será preenchido pelo banco de dados ao inserir

    # Campo para o dado de entrada original, agora mais genérico e conciso
    dado_original: str = ""
    
    # Campo para uma versão "normalizada" do dado de entrada.
    # Reflete o processo de padronização e limpeza para comparações e uso interno.
    dado_normalizado: str = ""
    
    valido: bool = False # Resultado final da validação (True/False)
    mensagem: str = "" # Mensagem explicativa do resultado da validação
    origem_validacao: str = "" # Onde a validação primária ocorreu (ex: "phonenumbers", "viacep", "fallback", "servico")
    
    # Campo para indicar o tipo de validação (crucial para generalização)
    tipo_validacao: str = "" # Ex: "phone", "email", "document", "address"

    # Detalhes específicos da validação, armazenados como um dicionário JSONB.
    validation_details: Dict[str, Any] = field(default_factory=dict)
    
    data_validacao: datetime = field(default_factory=datetime.now) # Timestamp da validação
    
    app_name: Optional[str] = None # Nome da aplicação que chamou o serviço
    client_identifier: Optional[str] = None # Identificador do cliente (CPF, CNPJ, etc.)
    regra_codigo: Optional[str] = None # O código da regra de negócio aplicada

    # --- Campos para Soft Delete ---
    is_deleted: bool = False    # Indica se o registro está logicamente deletado
    deleted_at: Optional[datetime] = None # Timestamp da deleção lógica