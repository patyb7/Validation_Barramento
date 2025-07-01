# app/services/validation_processing_service.py

from datetime import datetime, timedelta, timezone
from app.models.validation_record import ValidationRecord
from app.models.qualificacao_pendente import QualificacaoPendente
from app.database.repositories.validation_record_repository import ValidationRecordRepository
from app.database.repositories.qualification_repository import QualificationRepository
from app.models.invalidos_qualificados import InvalidosQualificados # Se for usar

class ValidationProcessingService:
    def __init__(self,
                 validation_repo: ValidationRecordRepository,
                 qualification_repo: QualificationRepository):
        self.validation_repo = validation_repo
        self.qualification_repo = qualification_repo

    async def processar_resultado_validacao(self, validacao_original: ValidationRecord):
        # Aqui você pode ter a "lógica de validação" real ou simplesmente assumir que
        # validacao_original.is_valido e validacao_original.status_qualificacao já foram definidos
        # por algum validador anterior.

        if validacao_original.status_qualificacao == "UNQUALIFIED":
            print(f"Registro {validacao_original.id} está UNQUALIFIED. Movendo para pendências.")

            # Opcional: Atualizar o ValidationRecord original (se você tiver um campo como is_pending_revalidation)
            # validacao_original.is_pending_revalidation = True
            # await self.validation_repo.update(validacao_original)

            # Cria um novo registro em QualificacaoPendente
            nova_pendencia = QualificacaoPendente(
                validation_record_id=validacao_original.id,
                client_identifier=validacao_original.client_identifier,
                validation_type=validacao_original.tipo_validacao,
                status_motivo="Dado não qualificado na validação inicial, requer revalidação.",
                attempt_count=0,
                scheduled_next_attempt_at=datetime.now(timezone.utc) + timedelta(days=1)
            )
            await self.qualification_repo.create_pendente(nova_pendencia)
            print(f"Registro {validacao_original.id} movido para qualificacoes_pendentes.")

        elif validacao_original.is_valido:
            print(f"Registro {validacao_original.id} é VÁLIDO. Status: {validacao_original.status_qualificacao}.")
            # Lógica para dados VÁLIDOS, como:
            # - Marcar como Golden Record (se for o caso)
            # - Notificar outros serviços
            # - Gravar em outras tabelas de dados qualificados

        else: # Assumindo que is_valido é False e não é UNQUALIFIED (ou seja, é inválido definitivo)
            print(f"Registro {validacao_original.id} é INVÁLIDO. Status: {validacao_original.status_qualificacao}.")
            # Lógica para dados INVÁLIDOS definitivos, como:
            # - Criar um registro em InvalidosQualificados
            # arquivado_invalido = InvalidosQualificados(
            #     validation_record_id=validacao_original.id,
            #     client_identifier=validacao_original.client_identifier,
            #     reason_for_invalidation=validacao_original.mensagem, # Ou um motivo mais específico
            # )
            # await self.qualification_repo.create_invalido_qualificado(arquivado_invalido)
            # print(f"Registro {validacao_original.id} arquivado como inválido qualificado.")